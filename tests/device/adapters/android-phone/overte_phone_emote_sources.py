"""Durable per-role original Emote acquisition; no action or effect verdict.

Interrupted reads retain responsibility. Historical replay restores source
cursors only; every successful read obtains new native/UI/fixture originals.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import time

from adapters.emote_rig_measurements import source,continuation
from adapters.emote_admission import executable,world,policy as admission_policy
from adapters.native_feature_observation import exact,fresh,integer,need,number,validate as native_packet
from adapters.native_animation_history import accept as animation_history
from adapters.native_script_roots import validate as roots_packet
from adapters.native_script_observation import NativeScriptObservation,validate as script_packet
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.normal_ui import NativeUIError
from adapters.token_emote_ui import snapshot
from feature_journeys.contract import identifier
from feature_journeys.phase_fixture import PhaseFixtureReader,validate as phase_packet
from overte_phone_emote_controls import validate as widget_packet
from overte_phone_emote_originals import PhoneEmoteOriginals,MAX_FRAMES,BLOCK
from overte_phone_graphics_samples import restore_native,restore_ui
from overte_phone_script_history import pack,unpack,same
from overte_phone_script_lock import PhoneScriptSourceLock

VERSION=4
LIMIT=MAX_FRAMES
MAX_SEGMENTS=16


def source_name(role,segment):
    need(role in ('primary','actor') and integer(segment,0,MAX_SEGMENTS-1))
    return 'phone-emote-'+role+'-sources'+('-segment-'+str(segment) if segment else '')+'.json'


class EmotePhaseChanged(NativeUIError):
    """A fully retained original acquisition crossed an actual fixture phase."""


class PhoneEmoteSources:
    def __init__(self,adapter,selector,phase,role,lock,*,artifact_root,monotonic=time.monotonic,segment=0,admission=None):
        need(isinstance(phase,PhaseFixtureReader) and phase.area=='emotes'
            and role in ('primary','actor') and isinstance(lock,PhoneScriptSourceLock) and callable(monotonic))
        path=adapter.state_path(selector);need(lock.path==path.with_name('phone-script-sources.lock'));lock.assert_held()
        self.adapter,self.selector,self.phase,self.role,self.lock=adapter,selector,phase,role,lock
        self.monotonic=monotonic;self.run=identifier(phase.run);self.historical=False
        self.segment=segment;self.predecessor=None;self.prior_store=None;self.prior_header=None
        _ui,_service,binding,self.guard,_installed=adapter.normal_feature_runtime(selector,read_only=True)
        self.binding=deepcopy(context(binding));self.pid=int(self.binding['processIdentity'].split(':')[0]);need(integer(self.pid,1))
        self.store=PrivateFeatureState(path.with_name(source_name(role,segment)))
        self.previous=self.store.read();self.frames=[];self.failed=False
        original_policy=self.previous.get('admissionPolicy') if self.previous is not None and self.previous.get('emoteSourcesVersion')==VERSION else None
        self.admission=None if admission is None and original_policy is None else admission_policy(original_policy if admission is None else admission)
        self.artifact_root=Path(artifact_root)
        self.state=dict(phase='ready',revision=0,manifests=[],pending=None)
        self.originals=PhoneEmoteOriginals(self.artifact_root,self.binding,self.run,self.role,self.guard,self.storage_intent,monotonic=self.monotonic)
        if segment:
            self.prior_store=PrivateFeatureState(path.with_name(source_name(role,segment-1)));self.prior_header=self.prior_store.read()
            need(self.prior_header is not None and self.prior_header.get('role')==role)
            prior_policy=self.prior_header.get('admissionPolicy') if self.prior_header.get('emoteSourcesVersion')==VERSION else None
            if self.admission is None and self.previous is None and prior_policy is not None:self.admission=admission_policy(prior_policy)
            need(same(self.admission,prior_policy)) # Never downgrade or silently upgrade an unchecked predecessor.
            prior_state,prior_frames=self.archive(self.prior_header,phase=phase,artifact_root=self.artifact_root,binding=self.binding,
                guard=self.guard,monotonic=self.monotonic)
            need(prior_state['phase']=='ready' and prior_state['pending'] is None and bool(prior_frames)
                and prior_frames[-1]['group']['native']['animation']['overrideActive'] is False)
            self.predecessor=prior_frames[-1];self.prior_manifest=deepcopy(prior_state['manifests'][-1])
            self.prior_reference=deepcopy(self.originals.manifest(self.prior_manifest)[-1]);self.predecessor_bound()
        if self.previous is not None:
            try:self.state,self.frames=self.decode(self.previous)
            except (KeyError,TypeError,ValueError,OSError):
                raise NativeUIError('Original Emote source journal is invalid') from None
            if self.frames and self.predecessor is not None:
                self.validate_frame(self.frames[0],self.predecessor);self.segment_start(self.frames[0]['group']['native'])

    def segment_start(self,packet):
        if self.predecessor is not None and self.role=='primary':
            need(packet['animation']['overrideActive'] is False and packet['animation']['history']['callSequence']==
                self.predecessor['group']['native']['animation']['history']['callSequence'])

    def predecessor_bound(self):
        if self.predecessor is None:return
        self.lock.assert_held();need(self.guard() is not False and same(self.prior_store.read(),self.prior_header))
        references=self.originals.manifest(self.prior_manifest);need(same(references[-1],self.prior_reference))
        original=self.originals.read(self.originals.expand(self.prior_reference));need(same(original,self.predecessor))

    def configuration_bound(self):
        need(same(self.store.read(),self.previous))
        if self.previous is not None:
            need(same(self.previous.get('admissionPolicy'),self.admission)
                and self.previous['emoteSourcesVersion']==(VERSION if self.admission is not None else 3))

    def decode(self,value):
        version=value.get('emoteSourcesVersion') if type(value) is dict else None
        exact(value,{'emoteSourcesVersion','runId','fixtureUrl','role','binding','artifactRoot','payload'}|({'admissionPolicy'} if version==VERSION else set()))
        need(type(version) is int and version in (3,VERSION) and (self.admission is not None)==(version==VERSION)
            and value['runId']==self.run and value['fixtureUrl']==self.phase.fixture_url and value['role']==self.role
            and same(context(value['binding']),self.binding) and value['artifactRoot']==str(self.artifact_root))
        if version==VERSION:need(same(value['admissionPolicy'],self.admission))
        rows=unpack(value['payload']);need(len(rows)==1);state=rows[0]
        exact(state,{'phase','revision','manifests','pending'})
        need(state['phase'] in ('ready','reading') and integer(state['revision'],0,LIMIT))
        frames=self.originals.restore(state['manifests'],state['revision'])
        # Existing Script history validation owns immutable module/code/load/
        # manager transitions. It issues no transport calls during replay.
        replay=NativeScriptObservation(lambda *_:need(False),lambda:need(False),lambda:need(False),lambda:need(False),self.pid)
        self.replay_scripts(replay,frames)
        previous=None;animation=None
        for frame in frames:
            self.validate_frame(frame,previous);previous=frame
            packet=frame['group']['native']
            animation=animation_history(animation,packet['animation']['rigId'],packet['animation']['history'])
        if state['phase']=='ready':need(state['pending'] is None)
        else:
            pending=state['pending'];exact(pending,{'startedEpochMs','role','revision','original','manifest'})
            need(state['revision']<LIMIT and integer(pending['startedEpochMs'],1) and pending['role']==self.role
                and type(pending['revision']) is int and pending['revision']==state['revision'])
            if pending['original'] is not None:
                self.originals.original(pending['original']);need(pending['original']['index']==state['revision']+1)
            if pending['manifest'] is not None:
                item=pending['manifest'];exact(item,{'emoteManifestVersion','reference','phase'})
                need(type(item['emoteManifestVersion']) is int and item['emoteManifestVersion']==1 and item['phase'] in ('planned','saved')
                    and pending['original'] is not None and pending['original']['phase']=='saved')
                self.originals.manifest_reference(item['reference'])
                need(item['reference']['block']==state['revision']//BLOCK+1 and item['reference']['count']==state['revision']%BLOCK+1)
        return deepcopy(state),deepcopy(frames)

    @classmethod
    def archive(cls,value,*,phase,artifact_root,binding,guard,monotonic=time.monotonic,predecessor=None):
        """Historical files only; no runtime, transport or usable live owner.

        The caller guards actual candidate/process authority before and after
        the bounded local replay. This does not create fresh product facts.
        """
        need(isinstance(phase,PhaseFixtureReader) and phase.area=='emotes' and type(value) is dict
            and value.get('role') in ('primary','actor') and callable(guard) and callable(monotonic))
        scope=object.__new__(cls);scope.phase,scope.run,scope.role=phase,identifier(phase.run),value['role']
        scope.binding=deepcopy(context(binding));scope.pid=int(scope.binding['processIdentity'].split(':')[0]);need(integer(scope.pid,1))
        scope.admission=None if value.get('emoteSourcesVersion')!=VERSION else admission_policy(value['admissionPolicy'])
        scope.artifact_root=Path(artifact_root);scope.monotonic=monotonic
        scope.originals=PhoneEmoteOriginals(scope.artifact_root,scope.binding,scope.run,scope.role,guard,
            lambda *_args:need(False),monotonic=monotonic)
        state,frames=scope.decode(value)
        if predecessor is not None:
            need(predecessor.get('role')==value['role'] and same(predecessor.get('admissionPolicy'),value.get('admissionPolicy')))
            prior,previous=cls.archive(predecessor,phase=phase,artifact_root=artifact_root,binding=binding,guard=guard,monotonic=monotonic)
            need(prior['phase']=='ready' and prior['pending'] is None and previous
                and previous[-1]['group']['native']['animation']['overrideActive'] is False)
            if frames:
                scope.validate_frame(frames[0],previous[-1])
                if value['role']=='primary':
                    need(frames[0]['group']['native']['animation']['overrideActive'] is False
                        and frames[0]['group']['native']['animation']['history']['callSequence']==
                            previous[-1]['group']['native']['animation']['history']['callSequence'])
        return deepcopy((state,frames))

    @staticmethod
    def replay_scripts(reader,frames):
        # Extend through the existing original packet validator and pure native
        # history state machine. Its ordinary <=512-frame batch API stays intact.
        # No transport, callback, expected facts or clock replacement is involved.
        need(isinstance(reader,NativeScriptObservation) and reader.ios is False and len(frames)<=LIMIT)
        reader.restore_history([])
        for frame in frames:PhoneEmoteSources.advance_script(reader,frame)

    @staticmethod
    def advance_script(reader,frame):
        value=frame['group']['script'];script_packet(value,identifier(value.get('requestId')),reader.pid,value.get('capturedEpochMs'))
        need(reader.instance in (None,value['instance']) and value['sequence']>reader.sequence
            and value['capturedEpochMs']>=reader.captured_epoch)
        transition=reader._history_transition(value,require_effects=True,require_code_identity=True,require_load_history=True,require_membership=True)
        reader._commit_history(value,transition)

    def replay_animation(self,frames):
        previous=None
        for frame in frames:
            packet=frame['group']['native']
            native_packet(packet,identifier(packet.get('requestId')),self.pid,packet.get('capturedEpochMs'),
                require_animation=True,require_animation_history=True)
            need(packet['animation']['history']['historyVersion']==2)
            previous=animation_history(previous,packet['animation']['rigId'],packet['animation']['history'])
        return previous

    def storage_intent(self,kind,value):
        need(self.state['phase']=='reading' and kind in ('original','manifest'))
        pending=self.state['pending'];old=pending[kind]
        if kind=='original':
            self.originals.original(value);need(value['index']==self.state['revision']+1)
            if old is None:need(value['phase']=='planned')
            else:
                need(value['phase']=={'planned':'opened','opened':'saved'}.get(old['phase'])
                    and all(same(value[key],old[key]) for key in value if key not in ('phase','file'))
                    and (old['phase']=='planned' or same(old['file'],value['file'])))
        else:
            exact(value,{'emoteManifestVersion','reference','phase'})
            need(type(value['emoteManifestVersion']) is int and value['emoteManifestVersion']==1
                and pending['original'] is not None and pending['original']['phase']=='saved')
            self.originals.manifest_reference(value['reference'])
            need(value['reference']['block']==self.state['revision']//BLOCK+1 and value['reference']['count']==self.state['revision']%BLOCK+1)
            need(value['phase']=='planned' if old is None else old['phase']=='planned' and value['phase']=='saved'
                and same(old['reference'],value['reference']))
        pending[kind]=deepcopy(value);self.save()

    def validate_frame(self,frame,previous=None,*,closed=False):
        exact(frame,{'group','ui','widgets','phaseBefore','phaseAfter','hostEpochMs','epochMs'}|({'probe'} if self.admission is not None else set()))
        need(integer(frame['epochMs'],1) and number(frame['hostEpochMs'],1,1e15))
        selected,current,_urls=source(frame['group'],self.pid,frame['epochMs'])
        if self.admission is not None:
            _selected,probe_engine,_proof=executable(frame['group'],pid=self.pid,epoch=frame['epochMs'],probe_url=self.admission['probeUrl'])
            top=max(row['compiledEpochMs'] for row in probe_engine['compiled']['compilations'] if row['resourceName']==self.admission['probeUrl']
                and row['sha256']==probe_engine['code']['sha256'])
            world(frame['probe'],self.admission,epoch=frame['epochMs'],after_epoch=top,
                after_sequence=0 if previous is None else previous['probe']['sampleSequence']-1)
            if previous is not None:
                need(frame['probe']['sampleEpochMs']>=previous['probe']['sampleEpochMs'])
                if frame['probe']['sampleSequence']==previous['probe']['sampleSequence']:need(same(frame['probe'],previous['probe']))
        ui=snapshot(frame['ui']);widgets=frame['widgets']
        widget_packet(widgets,identifier(widgets.get('commandId')),self.pid,frame['epochMs'])
        expected=dict(emoteControlsVersion=1,open=ui['open'],ready=widgets['ready'],controls=widgets['controls'],scope=dict(
            instance=widgets['instance'],generation=widgets['generation'],sequence=widgets['lastCommandSequence'],
            sourceSequence=widgets['sourceSequence'],elapsedMs=widgets['elapsedMs'],capturedEpochMs=widgets['capturedEpochMs'],processId=widgets['processId']))
        need(same(ui,expected) and widgets['capturedEpochMs']>=frame['group']['rootsAfter']['capturedEpochMs'])
        before,after=frame['phaseBefore'],frame['phaseAfter']
        phase_packet(before,run=self.run,area='emotes',request=before['requestId'],epoch=frame['hostEpochMs'],
            previous=previous['phaseAfter'] if previous else None)
        phase_packet(after,run=self.run,area='emotes',request=after['requestId'],epoch=frame['hostEpochMs'],previous=before)
        need(before['active'] is (not closed) and before['activations']
            and after['active'] is (not closed) and after['activations'])
        if closed:
            need(before['activations'][-1]['stimulus']==dict(verb='cleanup',inputs={})
                and same(before['activations'],after['activations'])
                and current['animation']['overrideActive'] is False and ui['open'] is False and not ui['controls'])
        activation=before['activations'][-1]
        need(frame['group']['rootsBefore']['requestedEpochMs']>=activation['activatedEpochMs'])
        if previous is not None:
            need(frame['epochMs']>=previous['epochMs'] and frame['hostEpochMs']>=previous['hostEpochMs'])
            old=previous['group'];continuation(old['native'],current,self.pid)
            root=frame['group']['rootsBefore']
            roots_packet(root,dict(schemaVersion=1,commandId=root['commandId'],action='feature-script-roots-observe'),
                self.pid,frame['epochMs'],previous=old['rootsAfter'])
            previous_selected,_native,_urls=source(old,self.pid,previous['epochMs'])
            need(same(selected,previous_selected))
            left,right=previous['ui']['scope'],ui['scope']
            need(all(left[k]==right[k] for k in ('instance','generation','processId'))
                and right['sourceSequence']>left['sourceSequence'] and right['sequence']>=left['sequence']
                and right['elapsedMs']>=left['elapsedMs'] and right['capturedEpochMs']>=left['capturedEpochMs'])
        return activation['ticket']==after['activations'][-1]['ticket']

    def save(self):
        need(getattr(self,'historical',False) is False)
        try:
            self.lock.assert_held();need(not self.failed and self.guard() is not False);self.configuration_bound()
            self.state['revision']=len(self.frames)
            value=dict(emoteSourcesVersion=VERSION if self.admission is not None else 3,runId=self.run,fixtureUrl=self.phase.fixture_url,role=self.role,
                binding=self.binding,artifactRoot=str(self.artifact_root),payload=pack([self.state]))
            if self.admission is not None:value['admissionPolicy']=deepcopy(self.admission)
            self.store.write(value,self.previous);need(same(self.store.read(),value));self.previous=deepcopy(value)
        except Exception:
            self.failed=True
            if same(self.store.read(),self.previous):
                if self.previous is not None:self.state,self.frames=self.decode(self.previous)
                else:self.state,self.frames=dict(phase='ready',revision=0,manifests=[],pending=None),[]
            raise

    def failure_archive(self,value):
        """Verify retained failed-read originals; never a completed measurement."""
        exact(value,{'emoteSourceFailureArchiveVersion','segment','header','predecessorHeader',
            'originalDiagnostic','manifestDiagnostic','cleanup'})
        need(type(value['emoteSourceFailureArchiveVersion']) is int and value['emoteSourceFailureArchiveVersion'] in (1,2)
            and integer(value['segment'],0,MAX_SEGMENTS-1))
        self.lock.assert_held();started=self.monotonic();need(number(started,0,1e15) and self.guard() is not False)
        state,frames=self.archive(value['header'],phase=self.phase,artifact_root=self.artifact_root,
            binding=self.binding,guard=self.guard,monotonic=self.monotonic)
        need(value['header']['role']==self.role and same(value['header'].get('admissionPolicy'),self.admission)
            and state['phase']=='reading' and state['pending'] is not None)
        historical=object.__new__(type(self));historical.__dict__=self.__dict__.copy()
        historical.previous,historical.state,historical.frames=deepcopy(value['header']),state,frames
        historical.historical=True;historical.predecessor=None
        prior=value['predecessorHeader']
        if value['segment']==0:need(prior is None)
        else:
            need(prior is not None and prior.get('role')==self.role and same(prior.get('admissionPolicy'),self.admission))
            old,previous=self.archive(prior,phase=self.phase,artifact_root=self.artifact_root,
                binding=self.binding,guard=self.guard,monotonic=self.monotonic)
            need(old['phase']=='ready' and previous and not previous[-1]['group']['native']['animation']['overrideActive'])
            historical.predecessor=previous[-1]
            if frames:historical.validate_frame(frames[0],previous[-1]);historical.segment_start(frames[0]['group']['native'])
        cleanup=value['cleanup'];phase_packet(cleanup,run=self.run,area='emotes',request=cleanup['requestId'],epoch=cleanup['capturedEpochMs'])
        need(cleanup['active'] is (value['emoteSourceFailureArchiveVersion']==1) and cleanup['activations']
            and cleanup['activations'][-1]['stimulus']==dict(verb='cleanup',inputs={}))
        if frames:
            old=frames[-1]['phaseAfter'];rows=cleanup['activations'];prior_rows=old['activations']
            need(cleanup['instance']==old['instance'] and cleanup['createdEpochMs']==old['createdEpochMs']
                and len(rows)>=len(prior_rows) and same(rows[:len(prior_rows)],prior_rows))
        pending=state['pending'];original=pending['original'];diagnostic=None
        if original is not None:
            diagnostic=self.originals.diagnostic(original)
            if original['phase']=='saved':
                frame=self.originals.read(original)
                historical.validate_frame(frame,frames[-1] if frames else historical.predecessor)
                if not frames:historical.segment_start(frame['group']['native'])
                replay=NativeScriptObservation(lambda *_:need(False),lambda:need(False),lambda:need(False),lambda:need(False),self.pid)
                self.replay_scripts(replay,frames+[frame]);self.replay_animation(frames+[frame])
        need(same(diagnostic,value['originalDiagnostic']))
        manifest=pending['manifest'];observed=None
        if manifest is not None:
            ref=manifest['reference'];store=PrivateFeatureState(self.originals.manifest_path(ref));present=store.read() is not None
            need(present or manifest['phase']=='planned')
            if present:
                entries=self.originals.manifest(ref);need(same(entries[-1],self.originals.compact(original)))
                expected=[] if len(entries)==1 else self.originals.manifest(state['manifests'][-1])
                need(same(entries[:-1],expected))
            observed=dict(present=present)
        need(same(observed,value['manifestDiagnostic']))
        self.lock.assert_held();need(self.guard() is not False)
        end=self.monotonic();need(number(end,started,1e15) and end-started<5)
        return deepcopy(value)

    def transfer_failed(self,retain,*,retained=None,provider_retired=False):
        """Transfer a readonly failed acquisition during actual cleanup only.

        Retention preserves all complete/partial files and the original reading
        header. Clearing pending does not add a source frame or report success.
        """
        need(getattr(self,'historical',False) is False and not self.failed and callable(retain) and type(provider_retired) is bool)
        started=self.monotonic();need(number(started,0,1e15));clock=started
        def bound():
            nonlocal clock
            self.lock.assert_held();need(self.guard() is not False);self.configuration_bound();self.predecessor_bound()
            now=self.monotonic();need(number(now,clock,1e15) and now-started<5);clock=now
        bound();need(self.previous is not None and (self.state['phase']=='reading' or retained is not None and self.state['phase']=='ready'))
        state,frames=self.decode(self.previous);need(same(state,self.state) and same(frames,self.frames))
        cleanup=self.phase.status();bound()
        need(cleanup['active'] is (not provider_retired) and cleanup['activations']
            and cleanup['activations'][-1]['stimulus']==dict(verb='cleanup',inputs={}))
        if retained is None:
            pending=self.state['pending'];original=pending['original'];manifest=pending['manifest']
            original_diagnostic=None if original is None else self.originals.diagnostic(original)
            manifest_diagnostic=None
            if manifest is not None:
                present=PrivateFeatureState(self.originals.manifest_path(manifest['reference'])).read() is not None
                manifest_diagnostic=dict(present=present)
            value=dict(emoteSourceFailureArchiveVersion=2 if provider_retired else 1,segment=self.segment,header=deepcopy(self.previous),
                predecessorHeader=deepcopy(self.prior_header),originalDiagnostic=original_diagnostic,
                manifestDiagnostic=manifest_diagnostic,cleanup=cleanup)
        else:
            value=deepcopy(retained);self.failure_archive(value)
            need(value['segment']==self.segment and same(value['predecessorHeader'],self.prior_header))
            expected=deepcopy(value['header'])
            if self.state['phase']=='ready':
                rows=unpack(expected['payload']);rows[0].update(phase='ready',pending=None);expected['payload']=pack(rows)
            need(same(expected,self.previous))
            prior=value['cleanup'];need(prior['instance']==cleanup['instance'] and prior['createdEpochMs']==cleanup['createdEpochMs']
                and same(prior['activations'],cleanup['activations']))
        self.failure_archive(value);bound();need(retain(deepcopy(value)) is not False);bound()
        self.failure_archive(value);bound();final=self.phase.status();bound()
        need(final['active'] is (not provider_retired) and final['activations'][-1]['ticket']==cleanup['activations'][-1]['ticket']
            and final['activations'][-1]['stimulus']==dict(verb='cleanup',inputs={}))
        if self.state['phase']=='reading':
            self.state.update(phase='ready',pending=None);self.save();bound()
        return deepcopy(value)

    def recover_complete(self):
        """Commit an interrupted complete original; never deliver it as fresh.

        Reads lost before complete owned bytes remain unresolved. This method
        acquires no native/UI/fixture source and never repeats an input.
        """
        need(getattr(self,'historical',False) is False and not self.failed)
        started=self.monotonic();need(number(started,0,1e15));clock=started
        def bound():
            nonlocal clock
            self.lock.assert_held();need(self.guard() is not False);self.configuration_bound();self.predecessor_bound()
            now=self.monotonic();need(number(now,clock,1e15) and now-started<5);clock=now
        bound();need(self.state['phase']=='reading' and self.state['pending'] is not None)
        state,frames=self.decode(self.previous);need(same(state,self.state) and same(frames,self.frames))
        pending=self.state['pending'];original=pending['original']
        need(original is not None and original['phase'] in ('opened','saved'))
        frame=self.originals.read(original);bound()
        self.validate_frame(frame,self.frames[-1] if self.frames else self.predecessor)
        if not self.frames:self.segment_start(frame['group']['native'])
        replay=NativeScriptObservation(lambda *_:need(False),lambda:need(False),lambda:need(False),lambda:need(False),self.pid)
        self.replay_scripts(replay,self.frames+[frame]);self.replay_animation(self.frames+[frame]);bound()
        if original['phase']=='opened':
            original=deepcopy(original);original['phase']='saved';self.storage_intent('original',original);bound()
        ref=self.originals.compact(original);manifest=pending['manifest']
        if manifest is None:manifests=self.originals.append(self.state['manifests'],ref)
        else:
            entries=self.originals.manifest(manifest['reference']);need(same(entries[-1],ref))
            prior=[] if len(entries)==1 else self.originals.manifest(self.state['manifests'][-1])
            need(same(entries[:-1],prior))
            if manifest['phase']=='planned':self.storage_intent('manifest',dict(manifest,phase='saved'))
            manifests=deepcopy(self.state['manifests'])
            if len(entries)>1:manifests.pop()
            manifests.append(deepcopy(manifest['reference']))
        bound();self.frames.append(deepcopy(frame));self.state.update(phase='ready',manifests=manifests,pending=None)
        self.save();bound()

    def read(self):
        return self._read()

    def _read(self,*,closed=False):
        need(getattr(self,'historical',False) is False and type(closed) is bool)
        self.lock.assert_held();need(not self.failed and self.state['phase']=='ready' and (closed or len(self.frames)<LIMIT) and self.guard() is not False)
        self.configuration_bound()
        started=previous=self.monotonic();need(number(started,0,1e15))
        def bound():
            nonlocal previous
            self.lock.assert_held();need(self.guard() is not False)
            now=self.monotonic();need(number(now,previous,1e15) and now-started<5);previous=now
        self.predecessor_bound();bound()
        last=self.frames[-1] if self.frames else self.predecessor
        old=last['group'] if last else None
        roots=self.adapter._script_roots(self.selector,read_only=True)
        scripts=self.adapter._script_execution_observer(self.selector,read_only=True)
        native=self.adapter._native_feature_observer(self.selector,read_only=True)
        ui=self.adapter._emote_controls(self.selector,lambda *_:need(False),read_only=True).io
        need(roots.pid==scripts.pid==native.pid==ui.pid==self.pid and native.ios is False and scripts.ios is False)
        if old:
            history=([self.predecessor] if self.predecessor is not None else [])+self.frames
            roots.restore(old['rootsAfter'])
            if self.predecessor is None:self.replay_scripts(scripts,self.frames)
            else:
                self.replay_scripts(scripts,[self.predecessor])
                for original in self.frames:self.advance_script(scripts,original)
            restore_native(native,old['native']);native.animation_history=self.replay_animation(history)
            native.rig=old['native']['animation']['rigId']
            native.rig_sequence=old['native']['animation']['evaluationSequence']
            restore_ui(ui,last['widgets'],widget_packet)
        # Persist responsibility before any actual observation request. A lost
        # dispatch/result may not disappear through object reconstruction.
        epoch_local=self.monotonic();epoch=native.clock_ms();need(integer(epoch,1))
        if not closed:
            self.state.update(phase='reading',pending=dict(startedEpochMs=epoch,role=self.role,revision=len(self.frames),original=None,manifest=None));self.save()
        bound()
        host_started=self.phase.epoch_ms();need(number(host_started,1,1e15))
        phase_started=self.monotonic();bound()
        if closed:
            need(last is not None)
            status=self.phase.status(last['phaseAfter'])
            need(not status['active'] and same(status['activations'],last['phaseAfter']['activations'])
                and status['activations'][-1]['stimulus']==dict(verb='cleanup',inputs={}))
            phase=dict(status=status)
        else:phase=self.phase.read(last['phaseAfter'] if last else None)
        bound()
        before=roots.read(roots.last['sequence'] if roots.last else 0);bound()
        script=scripts.read(scripts.sequence,require_effects=True,require_code_identity=True,require_load_history=True,require_membership=True);bound()
        packet=native.read(native.sequence,require_animation=True,require_animation_history=True);bound()
        if not self.frames:self.segment_start(packet)
        after=roots.read(before['sequence']);bound()
        visual=ui.capture();bound();widgets=deepcopy(ui.original_packet)
        probe=None
        if self.admission is not None:
            with self.adapter.existing_input_session(self.selector):probe=self.adapter.invoke(self.selector,'probe.snapshot',{})
            bound()
        final=self.phase.status(phase['status']);bound()
        device_epoch=native.clock_ms();host_epoch=self.phase.epoch_ms();bound()
        frame=dict(group=dict(rootsBefore=before,script=script,native=packet,rootsAfter=after),ui=visual,widgets=widgets,
            phaseBefore=phase['status'],phaseAfter=final,hostEpochMs=host_epoch,epochMs=device_epoch)
        if self.admission is not None:frame['probe']=deepcopy(probe)
        stable=self.validate_frame(frame,last,closed=closed);bound()
        fresh(before['requestedEpochMs'],device_epoch)
        # Frozen external clocks cannot conceal late sequential acquisition.
        need(max(device_epoch-before['requestedEpochMs'],epoch-before['requestedEpochMs']+(previous-epoch_local)*1000)<=1500
            and max(host_epoch-phase['status']['capturedEpochMs'],
                host_started-phase['status']['capturedEpochMs']+(previous-phase_started)*1000)<=1500)
        if not closed:
            original=self.originals.write(len(self.frames)+1,frame);bound()
            manifests=self.originals.append(self.state['manifests'],original);bound()
            self.frames.append(deepcopy(frame));self.state.update(phase='ready',manifests=manifests,pending=None);self.save();bound()
        # Durability/guard work is part of delivery time, too. Accepted packets
        # remain historical if a slow final write prevents a fresh return.
        delivered_epoch=native.clock_ms();delivered_host=self.phase.epoch_ms();bound()
        self.predecessor_bound();bound()
        need(integer(delivered_epoch,device_epoch) and number(delivered_host,host_epoch,1e15)
            and max(delivered_epoch-before['requestedEpochMs'],epoch-before['requestedEpochMs']+(previous-epoch_local)*1000)<=1500
            and max(delivered_host-phase['status']['capturedEpochMs'],
                host_started-phase['status']['capturedEpochMs']+(previous-phase_started)*1000)<=1500)
        if not stable:raise EmotePhaseChanged('Original Emote sources crossed the active input phase; no current facts returned')
        if closed:self.closed_anchor=(epoch_local,epoch,host_started,phase_started,native.clock_ms)
        return deepcopy(frame)


    @classmethod
    def closed_archive(cls,value,*,phase,role,segment,artifact_root,binding,guard,monotonic=time.monotonic):
        """Validate retained pending/complete originals, never produce facts."""
        started=monotonic();need(number(started,0,1e15));clock=started
        def bound():
            nonlocal clock
            need(guard() is not False);now=monotonic();need(number(now,clock,1e15) and now-started<5);clock=now
        bound();exact(value,{'emoteClosedSourceVersion','role','segment','phase','sourceHeader','predecessorHeader','frame'})
        need(type(value['emoteClosedSourceVersion']) is int and value['emoteClosedSourceVersion']==1
            and role in ('primary','actor') and value['role']==role and integer(segment,0,MAX_SEGMENTS-1)
            and type(value['segment']) is int and value['segment']==segment
            and value['phase'] in ('reading','complete') and (value['frame'] is None)==(value['phase']=='reading')
            and (value['predecessorHeader'] is None)==(value['segment']==0))
        header=value['sourceHeader'];need(type(header) is dict and header.get('role')==value['role'])
        state,frames=cls.archive(header,phase=phase,artifact_root=artifact_root,binding=binding,guard=bound,
            monotonic=monotonic,predecessor=value['predecessorHeader'])
        need(state['phase']=='ready' and state['pending'] is None and frames)
        previous=frames[-1]
        need(previous['ui']['open'] is False and not previous['ui']['controls']
            and previous['group']['native']['animation']['overrideActive'] is False)
        for key in ('phaseBefore','phaseAfter'):
            need(previous[key]['activations'][-1]['stimulus']==dict(verb='cleanup',inputs={}))
        if value['frame'] is not None:
            scope=object.__new__(cls);scope.phase,scope.run,scope.role=phase,phase.run,value['role']
            scope.binding=deepcopy(context(binding));scope.pid=int(scope.binding['processIdentity'].split(':')[0])
            scope.admission=None if header['emoteSourcesVersion']==3 else admission_policy(header['admissionPolicy'])
            need(scope.validate_frame(value['frame'],previous,closed=True)
                and same(value['frame']['phaseBefore']['activations'],previous['phaseAfter']['activations']))
            # Replaying the current Script/animation packet restores and checks
            # the actual prior managers, load histories, roots and Rig cursors.
            replay=NativeScriptObservation(lambda *_:need(False),lambda:need(False),lambda:need(False),lambda:need(False),scope.pid)
            cls.replay_scripts(replay,frames);cls.advance_script(replay,value['frame']);scope.replay_animation(frames+[value['frame']])
        bound();return deepcopy(value)

    def closed_delivery(self,value):
        need(getattr(self,'historical',False) is False and hasattr(self,'closed_anchor'))
        self.lock.assert_held();need(self.guard() is not False);self.configuration_bound();self.predecessor_bound()
        started,epoch,host,phase_started,clock=self.closed_anchor
        current=self.phase.status(value['phaseAfter']);need(not current['active'])
        now,host_now,end=clock(),self.phase.epoch_ms(),self.monotonic()
        floor=value['group']['rootsBefore']['requestedEpochMs'];provider=value['phaseBefore']['capturedEpochMs']
        need(number(end,started,1e15) and end-started<5 and integer(now,value['epochMs']) and number(host_now,value['hostEpochMs'],1e15)
            and max(now-floor,epoch-floor+(end-started)*1000)<=1500
            and max(host_now-provider,host-provider+(end-phase_started)*1000)<=1500)

    def read_closed(self,retain):
        """Acquire new readonly facts after closure into the parent's archive.

        The mandatory callback retains a pending packet before native requests,
        then the exact completed packet. Existing active-only source controls,
        original files, manifests and timestamps are never changed.
        """
        need(getattr(self,'historical',False) is False and callable(retain));self.lock.assert_held()
        need(not self.failed and self.previous is not None and self.state['phase']=='ready')
        started=previous=self.monotonic();need(number(started,0,1e15))
        def bound():
            nonlocal previous
            need(self.guard() is not False);self.configuration_bound();self.predecessor_bound()
            now=self.monotonic();need(number(now,previous,1e15) and now-started<5);previous=now
        bound()
        value=dict(emoteClosedSourceVersion=1,role=self.role,segment=self.segment,phase='reading',
            sourceHeader=deepcopy(self.previous),predecessorHeader=deepcopy(self.prior_header),frame=None)
        def archive():return self.closed_archive(value,phase=self.phase,role=self.role,segment=self.segment,
            artifact_root=self.artifact_root,binding=self.binding,guard=bound,monotonic=self.monotonic)
        archive();bound()
        status=self.phase.status(self.frames[-1]['phaseAfter']);need(not status['active']
            and same(status['activations'],self.frames[-1]['phaseAfter']['activations']))
        need(retain(deepcopy(value)) is not False);bound()
        frame=self._read(closed=True);value.update(phase='complete',frame=frame)
        archive();need(retain(deepcopy(value)) is not False);bound();result=deepcopy(value)
        self.closed_delivery(frame);bound();return result
