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

from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState
from overte_phone_script_history import canonical,same
from overte_phone_snapshots_history_pass import SnapshotHistoryReadPass,signature
from overte_phone_snapshots_role import _UNPINNED,role_state,_restore_history_files
from overte_phone_snapshots_evidence import SnapshotsOriginals


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


class SnapshotConstructorHistoryPass(SnapshotHistoryReadPass):
    """Reuse original byte/PNG/binary receipts without adopting a current fact."""
    @classmethod
    def prepare(cls,feature,role,*,expected_role=_UNPINNED,previous_phase=None):
        f=feature;f.lock.assert_held();need(role in ('primary','actor'))
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
        if (f.state['phase'] not in ('baseline','active') or f.state['current'] is not None or f.state['handoff'] is not None
                or state['phase']!='ready' or state['pending'] is not None or state['sequence']==0):return None
        f.bound();phase=f.phase.status(previous_phase)
        if previous_phase is not None:_same_phase(phase,previous_phase)
        need(phase['active'] and phase['activations'])
        if phase['activations'][-1]['stimulus']['verb']=='cleanup':return None
        return cls(f,role,store,header,state,phase,before)

    def __init__(self,feature,role,store,header,state,phase,role_signature):
        f=feature;f.lock.assert_held()
        self.feature,self.role_name,self.role_store=f,role,store
        self.role_header,self.state,self.phase=deepcopy(header),deepcopy(state),deepcopy(phase)
        self.feature_store=f.store;self.feature_header=deepcopy(f.previous)
        self.root,self.run,self.configuration=f.root,f.run,deepcopy(f.config)
        self.binding=deepcopy(f.binding);self.feature_state_sha256=_digest(f.state)
        self.scope=getattr(f.adapter,'_existing_input_scope',None);need(type(self.scope) is dict)
        self.scope_value=deepcopy(self.scope);self.process,self.thread=os.getpid(),threading.get_ident()
        self.paths=(self.feature_store.path,self.role_store.path)
        self.signatures=(signature(self.feature_store.path),role_signature)
        self.prepared=dict(feature=self.feature_header,role=self.role_header,state=self.state,phase=self.phase,
            binding=self.binding,configuration=self.configuration,featureStateSha256=self.feature_state_sha256)
        self.prepared_sha256=_digest(self.prepared)
        self.closed=self.started=self.replaying=False
        self.finished=self.claimed=self.read_claimed=False
        self.frames=self.digest=self.attached=None
        self.baseline=self.baseline_digest=None
        self.files={};self.file_seal=self.file_seal_sha256=None
        self._headers();self._memory()

    def _headers(self):
        f=self.feature
        need(not self.closed and os.getpid()==self.process and threading.get_ident()==self.thread
            and f.store is self.feature_store and (f.store.path,self.role_store.path)==self.paths
            and f.root==self.root and f.run==self.run and f.role==self.role_name=='primary'
            and same(f.config,self.configuration) and same(f.binding,self.binding)
            and same(f.previous,self.feature_header)
            and getattr(f.adapter,'_existing_input_scope',None) is self.scope and same(self.scope,self.scope_value)
            and _digest(self.prepared)==self.prepared_sha256)
        for store,expected,pinned in zip((self.feature_store,self.role_store),(self.feature_header,self.role_header),self.signatures):
            need(signature(store.path)==pinned and same(store.read(),expected) and signature(store.path)==pinned)
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
        f.bound()
        if role is not None:role.bound()
        _same_phase(f.phase.status(self.phase),self.phase)
        # Target/phase callbacks can change a graph or file. Recheck after
        # every such callback, before a constructor or current read escapes.
        self._headers();self._memory(verify_graph=verify_graph);self._verify_files()
        need(f.state['phase'] in ('baseline','active') and f.state['current'] is None and f.state['handoff'] is None)
        return True

    def before_load(self):
        try:
            need(not self.claimed);return self._qualification(verify_graph=False)
        except BaseException:self.close();raise

    def after_load(self):
        try:
            need(not self.claimed);return self._qualification(verify_graph=False)
        except BaseException:self.close();raise

    def frames_for(self,role):
        try:
            self.feature.lock.assert_held();need(not self.claimed and not self.closed and self.frames is not None)
            self._headers();self._memory();self._verify_files()
            need(role.feature is self.feature and role.role==self.role_name and role.store.path==self.role_store.path
                and same(role.previous,self.role_header) and same(role.state,self.state) and not role._host_publication)
            self.claimed=True;self.attached=role;return self.frames
        except BaseException:self.close();raise

    def constructor_header(self,role):
        """Reject a changed first constructor read before adopting its state."""
        try:
            self.feature.lock.assert_held();need(not self.claimed and self.started and self.digest is not None)
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

    def before_read(self,role):
        try:
            need(self.finished and not self.read_claimed and self.attached is role)
            self._qualification(role);self.read_claimed=True;return True
        except BaseException:self.close();raise

    def close(self):
        # A shared actual graph belongs to the finished role until its own
        # facade disposal. Drop references only; never clear nested DTOs.
        self.closed=True;self.replaying=False;self.frames=None;self.attached=None;self.baseline=None
