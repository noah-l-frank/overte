"""Closed warm Pico Chat catalog, new original release proof and final archive."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import math
import re
import uuid

from adapters.chat_actor_files import COMMAND,RESULT
from adapters.chat_journey.evidence_archive import ChatArchiveCatalog,ChatEvidenceArchive
from adapters.chat_journey.script_source import identity as code_identity
from adapters.chat_journey.source_chunks import ChatSourceChunks,digest
from adapters.native_feature_observation import fresh,need,number
from adapters.native_chat_view import measured_keyboard
from adapters.normal_feature_state import PrivateFeatureState
from adapters.pico4.chat_application_close import birth
from adapters.restart_inputs import validate_native_restart
from adapters.script_journey.history import same
from feature_journeys.phase_fixture import PhaseFixtureReader,validate as phase_packet

VERSION=3


class PicoChatArchivePlan:
    """Capture admitted original file descriptions BEFORE the old PID stops.

    The final extension admits only the same warm application's fully consumed
    successor histories and its original closed actor-file receipt. No pathname
    scan is used to discover or adopt journals; scans only reject extra paths.
    """
    def __init__(self,parent):
        self.parent=parent;self.catalog=ChatArchiveCatalog(hold_files=False);self.archive=None
        self.adapter,self.target=parent.adapter,parent.target
        self.state,self.ui=self.adapter._script_paths(self.target)
        self.key=self.state.stem.removeprefix('normal-script-state-');need(re.fullmatch('[0-9a-f]{32}',self.key))
        self.peer_directory=parent.peer.files_store.path.parent
        try:
            parent.guard();parent.cleanup_admission.original();parent.dispatcher.audit()
            need(parent.previous['phase']=='caches-retired' and parent.previous['completedSteps']==26
                and parent.erase.previous['phase']=='complete' and parent.cache_release.previous['phase']=='caches-quiet'
                and set(parent.dispatcher.children)=={'normal','peer','distant','background','mixer','no-replay'})
            parent.cache_release.authority();parent.input_close.authority()
            # Every child has a completed original dispatcher proof, and its
            # current root must be the same original warm owner, never a
            # selected unrelated ready-looking journal.
            for kind,owner in parent.dispatcher.children.items():
                need(not getattr(owner,'failed',False) and same(owner.store.read(),owner.previous))
                proofs=[row for row in parent.dispatcher.proofs if row['kind']==kind]
                need(proofs)
                if kind=='normal':
                    owner.chunks.verify();need(owner.base['phase']=='ready' and owner.base['attempts'][-1]['phase']=='observed')
                elif kind=='peer':need(all(row['phase']=='received' for row in owner.previous['attempts']))
                elif kind=='background':owner.closed_history()
                elif kind=='mixer':need(owner.previous['phase'] in ('online','recovery-observed'))
                else:need(owner.previous['phase']=='complete')
                self.add_owner(owner)
            for role in (*parent.initial,*parent.roles,*parent.after,*parent.cache_release.roles):self.add_role(role)
            for owner in (parent.profile,parent.input_close,parent.erase,parent.cleanup_admission,parent.flow,parent.dispatcher,parent.cache_release):self.add_owner(owner)
            self.add(parent.input_close.input.store,parent.input_close.input.disk)
            for cache in parent.cache_release.caches:
                cache.validate();self.add_owner(cache);self.add(cache.capture.owner.store,cache.capture.owner.owned())
            # The separate publisher must have independently acquired all 26
            # original fixture stages. Historical reconstruction performs no
            # publication, target input or new effect observation.
            self.witness=self.historical_witness()
            for role in (self.witness.initial_samples,self.witness.samples):self.add_role(role)
            self.add_owner(self.witness)
            # Last _scripts access: subsequent process/source factories MUST
            # keep these actual old-PID host contexts untouched.
            manager=self.adapter._scripts(self.target)
            value=manager.store.read();need(value is not None and same(value['binding'],parent.binding)
                and value['sourceKind']=='scripts' and value['source'] is None and not value['loadAttempted']
                and not any(value[key] for key in ('managerOwned','dialogOwned')))
            self.add(manager.store,value)
            ui=PrivateFeatureState(self.ui);value=ui.read()
            if value is not None:
                need(value['processIdentity']==parent.binding['processIdentity'] and value['bridgeId']==parent.binding['sessionId']
                    and all(value[key]==parent.binding[key] for key in ('sourceRevision','artifactSha256')))
                self.add(ui,value)
            self.add(parent.store,parent.previous);self.catalog.verify_all()
            self.pre_stop_inventory()
        except BaseException:self.catalog.close_host();raise

    def add(self,store,expected):
        side='peer' if store.path.parent==self.peer_directory else 'primary'
        need(store.path.parent==(self.peer_directory if side=='peer' else self.state.parent))
        self.catalog.add(side+'/'+store.path.name,store,expected)

    def add_owner(self,owner):
        need(same(owner.store.read(),owner.previous));self.add(owner.store,owner.previous)
        history=getattr(owner,'history',None)
        # Background/Dispatcher.history are validated decoding methods, not
        # immutable files. Dispatcher still owns its separate actual chunks.
        if callable(history):history=None
        if history is None:history=getattr(owner,'chunks',None)
        if history is not None:
            need(type(history) is ChatSourceChunks);history.verify()
            for index in range(len(history.identities)):
                store=history.store(index);self.add(store,store.read())

    def add_role(self,role):
        need(role.frames and role.base['phase']=='ready');role.history.verify()
        self.add_owner(role);self.add_owner(role.script_source)

    def historical_witness(self):
        from adapters.chat_journey.witness import ChatWitness
        p=self.parent;peer=p.peer.reader()
        code=self.adapter._chat_script_source(self.target,p.source.run,role='actor',source_lock=p.lock,witness=True)
        initial=self.adapter._chat_cache_absence(self.target,p.source.run,peer,p.peer.binding,role='actor',stage='initial',
            source_lock=p.lock,peer_lock=p.peer.lock,witness=True,script_source=code)
        # Separate fresh reader instances restore only their original immutable
        # histories; they do not reuse the already-restored initial readers.
        samples=self.adapter._chat_samples(self.target,p.source.run,p.peer.reader(),p.peer.binding,role='actor',
            source_lock=p.lock,peer_lock=p.peer.lock,witness=True,pending_capture=True,script_source=code)
        source=PhaseFixtureReader(p.source.client,p.source.run,'chat',epoch_ms=p.source.epoch_ms,monotonic=p.source.monotonic)
        witness=ChatWitness(source,samples,p.flow.store,self.adapter._chat_witness_store(self.target),initial_samples=initial,monotonic=p.native.monotonic)
        need(len(witness.rows)==26 and all(row['phase']=='published' and row['ticket']==original['ticket']
            for row,original in zip(witness.rows,p.flow.rows)))
        return witness

    def pre_stop_inventory(self):
        # This exact known reader root must remain mutable for the new
        # process's independent peer queries. Admit only the original consumed
        # owner here; finish() catalogs its actual final closed original bytes.
        p=self.parent;files=p.cache_release.files;value=files._owned()
        need(files.original is p.peer.files and files.store.path==p.peer.files_store.path
            and value['pending'] is None and not value['closing'] and not value['removed']
            and value['request'] is not None and value['request']['operation']=='inspect'
            and value['result'] is not None and value['result']['retired']
            and value['request']['commandId']==value['result']['commandId'])
        self.inventory({row['store'].path for row in self.catalog.rows.values()}|{files.store.path})

    def inventory(self,expected):
        actual=set()
        for path in self.state.parent.iterdir():
            name=path.name
            if name in (self.state.name,self.ui.name) or name.startswith('chat-') and (name.endswith('-'+self.key+'.json')
                or '-'+self.key+'.json.frame-' in name):
                if path==self.adapter._chat_archive_retirement_store(self.target).path:continue
                actual.add(path)
        for path in self.peer_directory.iterdir():
            if path.name!='script-sources.lock':actual.add(path)
        need(actual==expected)

    def finish(self,application):
        p=self.parent
        need(application is p.application_close and application.previous['phase']=='released' and not application.failed
            and application.release is p.cache_release and same(application.store.read(),application.previous))
        self.catalog.verify_all();application.authority();application.ipc_absent()
        for role in application.roles:self.add_role(role)
        self.add_owner(application);self.add(application.inputs.store,application.inputs.read())
        self.catalog.rows['primary/'+application.inputs.store.path.name]['retire']=lambda check:application.inputs.retire(application.new_binding,application.sources[1],before_discard=check)
        self.add(p.peer.files_store,application.closed)
        ui=self.adapter._chat_postrestart_store(self.target,'ui');value=ui.read()
        if value is not None:
            need(value['processIdentity']==application.new_binding['processIdentity'] and value['bridgeId']==application.new_binding['sessionId']);self.add(ui,value)
        guard=ChatArchiveReleaseSource(application,fresh_phase_final=True)
        metadata=dict(picoChatArchivePlanVersion=VERSION,runId=p.source.run,oldBinding=p.binding,newBinding=application.new_binding,
            peerBinding=p.peer.binding,peerOriginBasis='native-configured-metadata-only',
            oldNative=application.inputs.read()['oldNative'],newNative=application.inputs.read()['newNative'],
            originalProfile=application.profile['original'],cleanupSha256=digest(guard.expected),parentSha256=digest(p.previous),applicationSha256=digest(application.previous))
        directory=self.state.parent/('chat-evidence-'+self.key+'-'+p.source.run)
        self.archive=ChatEvidenceArchive(self.catalog,directory,self.adapter._chat_archive_retirement_store(self.target),metadata,guard,self.inventory,
            unlink_fence=ChatArchiveUnlinkFence(guard))
        return self.archive.retire()

    def close_host(self):
        return self.archive.close_host() if self.archive is not None else self.catalog.close_host()


class ChatArchiveReleaseSource:
    """New original sources even after old flow/child journals are archived.

    The independent PhaseFixtureReader is pinned to the exact archived cleanup
    activation. It cannot admit a different current ticket, source or candidate.
    No cache creation, old script-manager access or peer query is permitted.
    """
    def __init__(self,application,*,fresh_phase_final=False):
        need(type(fresh_phase_final) is bool);self.fresh_phase_final=fresh_phase_final
        self.app=application;self.role=application.roles[0];self.expected=deepcopy(application.fence.original())
        original=application.fence.source
        self.phase=PhaseFixtureReader(original.client,original.run,'chat',epoch_ms=original.epoch_ms,monotonic=original.monotonic)
        self.last=None;self.started=None
        self.selection=code_identity(**self.code_arguments(self.role.script_source.frames[-1]))

    def code_arguments(self,frame):
        return dict(before=frame['before'],scripts=frame['scripts'],after=frame['after'],pid=self.role.primary.pid,epoch=frame['after']['capturedEpochMs'])

    def files_absent(self):
        files=self.app.release.files;original=files.original
        original._check_source()
        need(files.fd_owner.closed and not original._exists(COMMAND) and not original._exists(RESULT)
            and files.released({key:self.app.closed['result']['stamp'][key] for key in ('device','inode')}) is True)

    def final(self,proof,*,expected_cursors=None):
        need(self.last is not None and same(proof,self.last));self.files_absent();app=self.app
        readers=(self.role.primary,self.role.view,self.role.lifecycle,self.role.script_source.roots,self.role.script_source.scripts,*app.sources[1:])
        for reader in readers:need(reader.guard() is not False)
        if expected_cursors is not None:need(same(expected_cursors,self.cursors()))
        need(same(proof,self.last))
        measured=app.now();epoch=self.role.primary.clock_ms();phase_epoch=self.phase.epoch_ms();ended=app.now()
        need(number(measured,self.started,self.started+1.5) and number(ended,measured,self.started+1.5))
        oldest=min(proof[key]['capturedEpochMs'] for key in ('primary','view','native','absence','profile'))
        oldest=min(oldest,proof['compiledChat']['before']['requestedEpochMs'],proof['profile']['settings']['capturedEpochMs'],proof['profile']['view']['capturedEpochMs'])
        fresh(oldest,epoch);need(epoch-oldest+math.ceil((ended-measured)*1000)<=1500)
        phase_packet(proof['phase'],run=app.run_id,area='chat',request=proof['phase']['requestId'],epoch=phase_epoch,previous=self.expected)
        need(phase_epoch-proof['phase']['capturedEpochMs']+math.ceil((ended-measured)*1000)<=1500)

    def current_phase(self,proof):
        # A new HTTP phase response is only input authority. Native facts and
        # their original deadlines remain the exact already selected packet.
        self.final(proof)
        current=self.phase.read(self.expected)['status']
        need(current['active'] and same(current['activations'],self.expected['activations']))
        current=deepcopy(current);self.final(proof)
        phase_packet(current,run=self.app.run_id,area='chat',request=current['requestId'],epoch=self.phase.epoch_ms(),previous=self.expected)
        self.final(proof);return current

    def cursors(self):
        # Reject a newer accepted observation or mutation of a reader's
        # retained facts while an unlink uses an older selected frame.
        role=self.role;app=self.app
        fields=('instance','sequence','captured','captured_epoch','source','engines','lifecycle','last',
            'keyboard_instance','keyboard_sequence')
        # RestartInputs.retire performs one further original native read. Its
        # sequence may advance, but the actual native birth/lifecycle must not.
        return deepcopy([{key:getattr(reader,key) for key in fields if hasattr(reader,key)
            and not (reader is app.sources[1] and key=='sequence')} for reader in
            (role.primary,role.view,role.script_source.roots,role.script_source.scripts,*app.sources[1:])])

    def __call__(self,original=None):
        if original is not None:
            if self.fresh_phase_final:self.current_phase(original)
            else:self.final(original)
            return original
        app=self.app;self.started=app.now();self.files_absent()
        current=self.phase.read(self.expected)['status'];need(current['active'] and same(current['activations'],self.expected['activations']))
        code=self.role.script_source;before=code.roots.read(code.roots.last['sequence'])
        scripts=code.scripts.read(code.scripts.sequence,require_effects=True,require_code_identity=True,require_load_history=True,require_membership=True)
        after=code.roots.read(before['sequence']);compiled=dict(before=before,scripts=scripts,after=after)
        need(same(code_identity(**self.code_arguments(compiled)),self.selection))
        primary=self.role.primary.perform(app.run_id,'inspect');view=self.role.view.read(app.run_id)
        native=app.sources[1].read(app.sources[1].sequence);absence=app.sources[2].require_absent(app.io.pid);profile=app.sources[3].read(app.run_id)
        need(primary['chatVersion']==3 and same(primary['source'],self.role.frames[-1]['primary']['source'])
            and same(view['source']['storage'],self.role.frames[-1]['view']['source']['storage'])
            and view['instance']==profile['view']['instance'] and not view['source']['ui']['present']
            and not view['source']['editorFocused'] and not view['source']['editorHasDraft'] and not measured_keyboard(view['source']['keyboard'])
            and same(profile['current'],app.profile['original']) and native['instance']==absence['instance']==before['instance']
            and same(native['lifecycle'],self.role.frames[-1]['lifecycle']['lifecycle']))
        validate_native_restart(app.inputs.read()['oldNative'] if app.inputs.store.read() is not None else app.old_birth,birth(native))
        result=deepcopy(dict(primary=primary,view=view,native=native,absence=absence,profile=profile,compiledChat=compiled,phase=current))
        self.last=deepcopy(result);self.final(result);return result


class ChatArchiveUnlinkFence:
    """At most 16 unlinks/250 ms using the same original source acquisition.

    The 250-ms window begins when that acquisition completes; its original
    1.5-s host/native deadlines still include the complete acquisition. Every
    actual unlink has a NEW independent phase query after its final intent.
    Only prepare() before that intent may acquire a new source. Any failure
    retains the original pending token and makes this warm fence unusable.
    """
    def __init__(self,guard):
        need(type(guard) is ChatArchiveReleaseSource and guard.fresh_phase_final)
        self.guard=guard;self.proof=None;self.snapshot=None;self.started=self.epoch=None
        self.uses=0;self.pending=None;self.failed=False

    def clocks(self):
        measured=self.guard.app.now();epoch=self.guard.role.primary.clock_ms();ended=self.guard.app.now()
        need(number(ended,measured,measured+1.5));return measured,epoch,ended

    def window(self):
        measured,epoch,ended=self.clocks()
        need(number(measured,self.started,self.started+.250) and number(ended,measured,self.started+.250)
            and number(epoch,self.epoch,self.epoch+250) and epoch-self.epoch+math.ceil((ended-measured)*1000)<=250)

    def prepare(self):
        try:
            need(not self.failed and self.pending is None)
            now,epoch,ended=self.clocks()
            expired=self.proof is None or self.uses>=16 or now-self.started>=.250 or epoch-self.epoch>=250
            if expired:
                self.proof=deepcopy(self.guard());self.guard.final(self.proof)
                self.snapshot=self.guard.cursors();self.started,self.epoch,_ended=self.clocks();self.uses=0
            self.guard.final(self.proof,expected_cursors=self.snapshot);self.window()
            need(same(self.snapshot,self.guard.cursors()))
            token=dict(archiveUnlinkFenceVersion=1,requestId=uuid.uuid4().hex,sourceSha256=digest(self.proof),
                sourceSequence=self.proof['compiledChat']['after']['sequence'],windowUse=self.uses+1)
            self.pending=deepcopy(token);result=deepcopy(token)
            self.guard.final(self.proof,expected_cursors=self.snapshot);self.window();return result
        except Exception:self.failed=True;raise

    def check(self,token):
        try:
            need(not self.failed and self.pending is not None and same(token,self.pending)
                and digest(self.proof)==token['sourceSha256'] and same(self.snapshot,self.guard.cursors()))
            self.window();self.guard.current_phase(self.proof)
            need(same(self.snapshot,self.guard.cursors()))
            self.window();self.guard.final(self.proof,expected_cursors=self.snapshot)
        except Exception:self.failed=True;raise

    def complete(self,token):
        try:
            need(not self.failed and self.pending is not None and same(token,self.pending) and digest(self.proof)==token['sourceSha256'])
            self.guard.final(self.proof,expected_cursors=self.snapshot);self.window()
            self.uses+=1;self.pending=None
        except Exception:self.failed=True;raise
