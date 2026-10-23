"""One-use original-file replay before an ordinary Primary role constructor.

Only actual immutable history is read outside the source lock. Current target
factories, all continuity-floor replay and both final qualifications stay locked.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import io
import os
from _pickle import Pickler
import threading

from adapters.native_feature_observation import need,number
from adapters.normal_feature_state import PrivateFeatureState
from overte_phone_script_history import canonical,same
from overte_phone_snapshots_history_pass import SnapshotHistoryReadPass,signature
from overte_phone_snapshots_role import (_UNPINNED,role_state,_restore_history_files,
    validate_read_ready_slot,validate_read_ready_slot_owner)
from overte_phone_snapshots_evidence import SnapshotsOriginals
from overte_phone_snapshot_system_context import SnapshotSystemContext
from overte_phone_snapshot_documents_ui import SnapshotDocumentContext


def _digest(value):return hashlib.sha256(canonical(value)).hexdigest()


class _GraphPickler(Pickler):
    def reducer_override(self,value):
        raise TypeError('Custom objects are not private JSON originals')


def graph_digest(value):
    """Hash only a same-call graph, without reductions or a payload reader.

    Memo-free encoding preserves builtin scalar/container types and ignores
    external or internal alias counts. Cycles and custom objects fail closed.
    This encoding never supplies a persistent original or a source digest.
    """
    with io.BytesIO() as stream:
        encoder=_GraphPickler(stream,protocol=4);encoder.fast=True;encoder.dump(value)
        return hashlib.sha256(stream.getbuffer()).hexdigest()


def _same_phase(status,previous):
    need(status['active'] and status['activations'])
    for key in ('fixturePhaseVersion','instance','runId','area','createdEpochMs','retiredEpochMs','activations','active'):
        need(same(status[key],previous[key]))


def _callable_identity(value):
    return (getattr(value,'__self__',None),getattr(value,'__func__',value))


def _same_callable(value,expected):
    actual=_callable_identity(value)
    return all(a is b for a,b in zip(actual,expected))


def passive_scope(feature):
    """Check the existing passive scope; grant no new SDK or UI authority."""
    f=feature;handoff=f.state['handoff'];need(type(handoff) is dict)
    scope=f._system_scope
    expected=SnapshotDocumentContext if 'snapshotDocumentResolutionVersion' in handoff['resolution'] else SnapshotSystemContext
    need(type(scope) is expected and same(scope.binding,f.binding) and same(scope.chooser,handoff['resolution'])
        and _same_callable(scope.guard,(scope,SnapshotSystemContext.guard))
        and _same_callable(f.guard,_callable_identity(scope.guard))
        and _same_callable(scope.authority,_callable_identity(f.header_authority))
        and all(callable(getattr(scope,key,None)) for key in ('observe_binding','current_component','authority','monotonic'))
        and (scope.last_clock is None or number(scope.last_clock,0,1e15)))
    return scope


class SnapshotConstructorHistoryPass(SnapshotHistoryReadPass):
    """Reuse original byte/PNG/binary receipts without adopting a current fact."""
    @classmethod
    def prepare(cls,feature,role,*,expected_role=_UNPINNED,previous_phase=None,cleanup=False,passive=False):
        f=feature;f.lock.assert_held();need(role in ('primary','actor') and type(cleanup) is bool
            and type(passive) is bool and not (cleanup and passive))
        if role!='primary' or f.role!='primary':return None
        store=PrivateFeatureState(f.store.path.with_name('phone-snapshots-'+role+'-originals.json'))
        try:before=signature(store.path)
        except FileNotFoundError:before=None
        header=store.read()
        if expected_role is not _UNPINNED:need(same(header,expected_role))
        if header is None:
            need(before is None and not store.path.exists())
            # A lost known journal is not permission to forget its originals.
            need(not any(f.root.glob('emote-frame-snapshots-'+f.run+'-'+role+'-*.json'))
                and not any(f.root.glob('emote-index-snapshots-'+f.run+'-'+role+'-*.json'))
                and not any(f.root.glob('snapshots-'+f.run+'-'+role+'-*.png'))
                and not any(f.root.glob('snapshots-file-'+f.run+'-'+role+'-*.bin'))
                and not any(f.root.glob('snapshots-'+role+'-transfer-*'))
                and not os.path.lexists(store.path.with_name('phone-snapshots-'+role+'-files-observer.json')))
            return None
        need(signature(store.path)==before)
        state=role_state(header,f.binding,f.run,role)
        if (f.state['phase'] not in (('cleaned',) if cleanup else ('baseline','active')) or f.state['current'] is not None
                or (f.state['handoff'] is None if passive else f.state['handoff'] is not None)
                or state['phase']!='ready' or state['pending'] is not None or state['sequence']==0):return None
        if passive:
            system=passive_scope(f);system_pin=cls._system_snapshot(system)
            factory=_callable_identity(f.adapter._snapshot_system_context)
            feature_store=f.store;feature_header=deepcopy(f.previous);feature_signature=signature(feature_store.path)
            feature_state=_digest(f.state);configuration=deepcopy(f.config);binding=deepcopy(f.binding)
            sdk_scope=getattr(f.adapter,'_existing_input_scope',None);need(type(sdk_scope) is dict)
            sdk_value=deepcopy(sdk_scope)
            need(same(feature_store.read(),feature_header) and signature(feature_store.path)==feature_signature)
        f.bound();phase=f.phase.status(previous_phase)
        if previous_phase is not None:_same_phase(phase,previous_phase)
        need(phase['active'] and phase['activations'])
        if cleanup:f.cleanup_observe_phase(phase,previous_phase)
        elif phase['activations'][-1]['stimulus']['verb']=='cleanup':return None
        if passive:
            need(passive_scope(f) is system and _same_callable(f.adapter._snapshot_system_context,factory))
            cls._system_matches(system,system_pin)
            need(f.store is feature_store and same(f.previous,feature_header) and _digest(f.state)==feature_state
                and same(f.config,configuration) and same(f.binding,binding)
                and getattr(f.adapter,'_existing_input_scope',None) is sdk_scope and same(sdk_scope,sdk_value)
                and signature(feature_store.path)==feature_signature and same(feature_store.read(),feature_header)
                and signature(feature_store.path)==feature_signature)
        return cls(f,role,store,header,state,phase,before,cleanup=cleanup,passive=passive)

    def __init__(self,feature,role,store,header,state,phase,role_signature,*,cleanup=False,passive=False):
        f=feature;f.lock.assert_held()
        self.feature,self.role_name,self.role_store=f,role,store
        self.cleanup,self.passive=cleanup,passive
        self.role_header,self.state,self.phase=deepcopy(header),deepcopy(state),deepcopy(phase)
        self.feature_store=f.store;self.feature_header=deepcopy(f.previous)
        self.root,self.run,self.configuration=f.root,f.run,deepcopy(f.config)
        self.binding=deepcopy(f.binding);self.feature_state_sha256=_digest(f.state)
        self.scope=getattr(f.adapter,'_existing_input_scope',None);need(type(self.scope) is dict)
        self.scope_value=deepcopy(self.scope);self.process,self.thread=os.getpid(),threading.get_ident()
        self.paths=(self.feature_store.path,self.role_store.path)
        self.signatures=(signature(self.feature_store.path),role_signature)
        self.prepared=dict(feature=self.feature_header,role=self.role_header,state=self.state,phase=self.phase,
            binding=self.binding,configuration=self.configuration,featureStateSha256=self.feature_state_sha256,cleanup=cleanup,passive=passive)
        self.prepared_sha256=_digest(self.prepared)
        self.closed=self.started=self.replaying=False
        self.finished=self.claimed=self.read_claimed=False
        self.frames=self.digest=self.attached=None
        self.baseline=self.baseline_digest=None
        self.files={};self.file_seal=self.file_seal_sha256=None
        self.system_scope=self.system_pin=self.system_factory=None
        self.rebind_open=self.rebound=False
        self.own_slot=False;self.slot_intent=None
        if passive:
            self.system_factory=_callable_identity(f.adapter._snapshot_system_context)
            self._pin_system(passive_scope(f))
        self._headers();self._memory()

    def _pin_system(self,scope):
        self.system_scope=scope
        self.system_pin=self._system_snapshot(scope)

    @staticmethod
    def _system_snapshot(scope):
        return dict(binding=deepcopy(scope.binding),chooser=deepcopy(scope.chooser),clock=scope.last_clock,
            callbacks={key:_callable_identity(getattr(scope,key)) for key in ('observe_binding','current_component','authority','monotonic')})

    @staticmethod
    def _system_matches(scope,pin):
        need(same(scope.binding,pin['binding']) and same(scope.chooser,pin['chooser'])
            and all(_same_callable(getattr(scope,key),value) for key,value in pin['callbacks'].items())
            and _same_callable(scope.guard,(scope,SnapshotSystemContext.guard))
            and (pin['clock'] is None or number(scope.last_clock,pin['clock'],1e15)))

    def _system_headers(self,*,current=True):
        if not self.passive:return
        f=self.feature;scope=self.system_scope;pin=self.system_pin
        need(_same_callable(f.adapter._snapshot_system_context,self.system_factory))
        self._system_matches(scope,pin)
        if current:need(passive_scope(f) is scope)
        pin['clock']=scope.last_clock

    def _headers(self,*,check_system=True,_slot_owner=None):
        f=self.feature
        need(not self.closed and os.getpid()==self.process and threading.get_ident()==self.thread
            and f.store is self.feature_store and (f.store.path,self.role_store.path)==self.paths
            and f.root==self.root and f.run==self.run and f.role==self.role_name=='primary'
            and same(f.config,self.configuration) and same(f.binding,self.binding)
            and type(self.cleanup) is bool and self.cleanup is self.prepared['cleanup']
            and type(self.passive) is bool and self.passive is self.prepared['passive'] and not (self.cleanup and self.passive)
            and same(f.previous,self.feature_header)
            and getattr(f.adapter,'_existing_input_scope',None) is self.scope and same(self.scope,self.scope_value)
            and _digest(self.prepared)==self.prepared_sha256)
        role_header,role_signature=(self.role_header,self.signatures[1]) if _slot_owner is None else _slot_owner
        for store,expected,pinned in zip((self.feature_store,self.role_store),(self.feature_header,role_header),(self.signatures[0],role_signature)):
            need(signature(store.path)==pinned and same(store.read(),expected) and signature(store.path)==pinned)
        self._system_headers(current=check_system)
        return True

    def _memory(self,*,verify_graph=True):
        need(_digest(self.feature.state)==self.feature_state_sha256
            and same(role_state(self.role_header,self.binding,self.run,self.role_name),self.state))
        if self.digest is not None and verify_graph:
            need(type(self.frames) is list and graph_digest(self.frames)==self.digest)
        if self.baseline_digest is not None:
            need(type(self.baseline) is dict and graph_digest(self.baseline)==self.baseline_digest)
        if self.attached is not None:self._reader(self.attached,verify_graph=verify_graph)
        return True

    def _reader(self,role,*,verify_graph=True):
        need(role.feature is self.feature and role.role==self.role_name and role.store.path==self.role_store.path
            and same(role.previous,self.role_header) and same(role.state,self.state)
            and not role._host_publication)
        if verify_graph and role.frames is not self.frames:need(graph_digest(role.frames)==self.digest)

    def guard(self):
        need(self.feature.lock._owner is None and self.started)
        return self._headers()

    def read(self):
        try:
            need(not self.started and not self.closed and self.feature.lock._owner is None)
            self.started=True;self.guard();self._memory();self.replaying=True
            try:
                frames=_restore_history_files(self.feature,self.role_name,self.state,self.guard,receipts=self)
                f=self.feature
                host=SnapshotsOriginals(f.root,f.binding,f.run,'primary',self.guard,lambda *_:need(False),kind='snapshots-input')
                read,manifest=host.read,host.manifest
                host.read=lambda value:self.read_original(read,host.path,value)
                host.manifest=lambda value:self.read_original(manifest,host.manifest_path,value)
                inputs=host.restore(f.state['inputs'],f.state['inputSequence'])
                self.baseline=f.baseline_original(inputs)
                self.baseline_digest=graph_digest(self.baseline)
            finally:self.replaying=False
            self.guard();self._memory()
            self.frames=frames;self.digest=graph_digest(frames)
            self.file_seal=tuple(self.files.items());self.file_seal_sha256=self._files_digest(self.file_seal)
            self.guard();self._memory(verify_graph=False);return self.digest
        except BaseException:self.close();raise

    def _qualification(self,role=None,*,verify_graph=True):
        f=self.feature;f.lock.assert_held();need(self.started and self.digest is not None)
        self._headers();self._memory(verify_graph=False);self._verify_files()
        # The role guard already performs the complete feature guard before
        # comparing its own owner. Keep one actual guard at this boundary.
        if role is not None:role.bound()
        else:f.bound()
        status=f.phase.status(self.phase);_same_phase(status,self.phase)
        if self.cleanup:f.cleanup_observe_phase(status,self.phase)
        # Target/phase callbacks can change a graph or file. Recheck after
        # every such callback, before a constructor or current read escapes.
        self._headers();self._memory(verify_graph=verify_graph);self._verify_files()
        need(f.state['phase'] in (('cleaned',) if self.cleanup else ('baseline','active'))
            and f.state['current'] is None and (f.state['handoff'] is not None if self.passive else f.state['handoff'] is None))
        return True

    def before_load(self):
        try:
            need(not self.claimed and not self.rebind_open and not self.rebound)
            self._qualification(verify_graph=False)
            self.rebind_open=self.passive;return True
        except BaseException:self.close();raise

    def after_load(self):
        try:
            need(not self.claimed)
            if self.passive:
                need(self.rebind_open and not self.rebound)
                self._headers(check_system=False);self._memory(verify_graph=False);self._verify_files()
                old=self.system_scope;new=passive_scope(self.feature)
                need(new is not old and same(new.binding,self.system_pin['binding']) and same(new.chooser,self.system_pin['chooser']))
                new_pin=self._system_snapshot(new)
                need(old.guard() is True and new.guard() is True)
                need(number(new.last_clock,old.last_clock,1e15))
                # The recreated scope has fresh factory callbacks. The factory
                # and original SDK session, descriptors and old callbacks must
                # still match after the last actual SDK query.
                self._headers(check_system=False);self._memory(verify_graph=False);self._verify_files()
                self._system_matches(new,new_pin)
                need(passive_scope(self.feature) is new)
                self._pin_system(new);self.rebind_open=False;self.rebound=True
            return self._qualification(verify_graph=False)
        except BaseException:self.close();raise

    def frames_for(self,role):
        try:
            self.feature.lock.assert_held();need(not self.claimed and not self.closed and self.frames is not None)
            need(not self.passive or self.rebound and not self.rebind_open)
            self._headers();self._memory();self._verify_files()
            need(role.feature is self.feature and role.role==self.role_name and role.store.path==self.role_store.path
                and same(role.previous,self.role_header) and same(role.state,self.state) and not role._host_publication)
            self.claimed=True;self.attached=role;return self.frames
        except BaseException:self.close();raise

    def constructor_header(self,role):
        """Reject a changed first constructor read before adopting its state."""
        try:
            self.feature.lock.assert_held();need(not self.claimed and self.started and self.digest is not None)
            need(not self.passive or self.rebound and not self.rebind_open)
            self._headers();self._memory(verify_graph=False)
            need(role.feature is self.feature and role.role==self.role_name and role.store.path==self.role_store.path
                and same(role.previous,self.role_header))
            return True
        except BaseException:self.close();raise

    def original(self):
        """Return a defensive baseline only inside this admitted constructor."""
        try:
            f=self.feature;f.lock.assert_held()
            need(not self.closed and self.claimed and not self.finished and not self.read_claimed
                and self.attached is not None and self.baseline is not None)
            f.bound();self._headers();self._memory(verify_graph=False);self._verify_files()
            value=deepcopy(self.baseline)
            f.bound()
            # The last native callback may mutate a private graph or owner.
            self._headers();self._memory(verify_graph=False);self._verify_files()
            need(graph_digest(value)==self.baseline_digest)
            return value
        except BaseException:self.close();raise

    def finish_constructor(self,role):
        try:
            need(self.claimed and not self.finished and self.attached is role)
            self._qualification(role);self.finished=True;return True
        except BaseException:self.close();raise

    def acknowledge_own_slot(self,role,old_header,frame):
        """Extend this token only for its one normally archived ready slot."""
        try:
            f=self.feature;f.lock.assert_held()
            need(self.cleanup and not self.passive and self.finished and not self.read_claimed and not self.own_slot
                and self.attached is role and same(old_header,self.role_header))
            slot=validate_read_ready_slot(frame,f.run,phase=self.phase)
            need(same(slot['preparedRoleHeader'],old_header)
                and slot['preparedRoleSequence']==self.state['sequence']
                and same(self.slot_intent,dict(frameSha256=_digest(frame),slotId=slot['slotId'],oldHeader=old_header)))
            header=deepcopy(role.previous);state=role_state(header,self.binding,self.run,'primary')
            owner=(header,signature(self.role_store.path));count=self.state['sequence']
            need(state['phase']=='ready' and state['pending'] is None and state['sequence']==count+1)
            def pure(*,graph=False):
                self._headers(_slot_owner=owner);self._verify_files()
                need(_digest(f.state)==self.feature_state_sha256 and role.feature is f and role.role=='primary'
                    and role.store.path==self.role_store.path and same(role.previous,header) and same(role.state,state)
                    and not role._host_publication and len(role.frames)==count+1 and same(role.frames[-1],frame))
                if self.baseline_digest is not None:need(graph_digest(self.baseline)==self.baseline_digest)
                if graph:need(graph_digest(role.frames[:count])==self.digest)
                return True
            pure(graph=True)
            validate_read_ready_slot_owner(f,header,frame,pure)
            host=SnapshotsOriginals(f.root,f.binding,f.run,'primary',pure,lambda *_:need(False),kind='snapshots')
            new_files={}
            def receipt(read,path,value):
                actual=path(value);before=signature(actual);result=read(value)
                need(signature(actual)==before)
                if actual in self.files:need(self.files[actual]==before)
                new_files[actual]=before;return result
            reference=state['manifests'][-1]
            entries=receipt(host.manifest,host.manifest_path,reference)
            need(same(receipt(host.read,host.path,host.expand(entries[-1])),frame))
            f.bound();role.bound();status=f.phase.status(self.phase);_same_phase(status,self.phase)
            f.cleanup_observe_phase(status,self.phase)
            pure(graph=True)
            for path,value in new_files.items():need(signature(path)==value)
            # Only the verified own CAS append advances the sealed authority.
            self.role_header,self.state=header,deepcopy(state)
            self.signatures=(self.signatures[0],owner[1])
            self.prepared.update(role=self.role_header,state=self.state)
            self.prepared_sha256=_digest(self.prepared)
            self.frames=role.frames;self.digest=graph_digest(self.frames)
            self.files.update(new_files);self.file_seal=tuple(self.files.items());self.file_seal_sha256=self._files_digest(self.file_seal)
            self.own_slot=True;self.slot_intent=None;self._headers();self._memory();self._verify_files();return True
        except BaseException:self.close();raise

    def before_slot_cas(self,role,frame):
        """Keep the prior owner metadata through the first actual slot save."""
        self.feature.lock.assert_held()
        need(self.cleanup and self.finished and not self.read_claimed and not self.own_slot and self.slot_intent is None and self.attached is role
            and same(role.previous,self.role_header) and role.state['sequence']==self.state['sequence']
            and role.state['phase']=='reading' and same(role.state['manifests'],self.state['manifests'])
            and same(role.state['pending'],dict(original=None,manifest=None,image=None,binaries=[],retirement=None,frame=None,work=frame)))
        self._headers();self._verify_files()
        need(_digest(self.feature.state)==self.feature_state_sha256 and graph_digest(role.frames)==self.digest
            and graph_digest(self.baseline)==self.baseline_digest)
        slot=validate_read_ready_slot(frame,self.run,phase=self.phase)
        need(same(slot['preparedRoleHeader'],self.role_header))
        self.slot_intent=dict(frameSha256=_digest(frame),slotId=slot['slotId'],oldHeader=deepcopy(self.role_header))
        return True

    def before_read(self,role):
        try:
            need(self.finished and not self.read_claimed and self.attached is role)
            self._qualification(role);self.read_claimed=True;return True
        except BaseException:self.close();raise

    def close(self):
        # A shared actual graph belongs to the finished role until its own
        # facade disposal. Drop references only; never clear nested DTOs.
        self.closed=True;self.replaying=False;self.frames=None;self.attached=None;self.baseline=None
        self.system_scope=self.system_pin=self.system_factory=None;self.rebind_open=False;self.slot_intent=None
