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

VERSION=3
LIMIT=MAX_FRAMES


class EmotePhaseChanged(NativeUIError):
    """A fully retained original acquisition crossed an actual fixture phase."""


class PhoneEmoteSources:
    def __init__(self,adapter,selector,phase,role,lock,*,artifact_root,monotonic=time.monotonic):
        need(isinstance(phase,PhaseFixtureReader) and phase.area=='emotes'
            and role in ('primary','actor') and isinstance(lock,PhoneScriptSourceLock) and callable(monotonic))
        path=adapter.state_path(selector);need(lock.path==path.with_name('phone-script-sources.lock'));lock.assert_held()
        self.adapter,self.selector,self.phase,self.role,self.lock=adapter,selector,phase,role,lock
        self.monotonic=monotonic;self.run=identifier(phase.run);self.historical=False
        _ui,_service,binding,self.guard,_installed=adapter.normal_feature_runtime(selector,read_only=True)
        self.binding=deepcopy(context(binding));self.pid=int(self.binding['processIdentity'].split(':')[0]);need(integer(self.pid,1))
        self.store=PrivateFeatureState(path.with_name('phone-emote-'+role+'-sources.json'))
        self.previous=self.store.read();self.frames=[];self.failed=False
        self.artifact_root=Path(artifact_root)
        self.state=dict(phase='ready',revision=0,manifests=[],pending=None)
        self.originals=PhoneEmoteOriginals(self.artifact_root,self.binding,self.run,self.role,self.guard,self.storage_intent,monotonic=self.monotonic)
        if self.previous is not None:
            try:self.state,self.frames=self.decode(self.previous)
            except (KeyError,TypeError,ValueError,OSError):
                raise NativeUIError('Original Emote source journal is invalid') from None

    def decode(self,value):
        exact(value,{'emoteSourcesVersion','runId','fixtureUrl','role','binding','artifactRoot','payload'})
        need(type(value['emoteSourcesVersion']) is int and value['emoteSourcesVersion']==VERSION
            and value['runId']==self.run and value['fixtureUrl']==self.phase.fixture_url and value['role']==self.role
            and same(context(value['binding']),self.binding) and value['artifactRoot']==str(self.artifact_root))
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
    def archive(cls,value,*,phase,artifact_root,binding,guard,monotonic=time.monotonic):
        """Historical files only; no runtime, transport or usable live owner.

        The caller guards actual candidate/process authority before and after
        the bounded local replay. This does not create fresh product facts.
        """
        need(isinstance(phase,PhaseFixtureReader) and phase.area=='emotes' and type(value) is dict
            and value.get('role') in ('primary','actor') and callable(guard) and callable(monotonic))
        scope=object.__new__(cls);scope.phase,scope.run,scope.role=phase,identifier(phase.run),value['role']
        scope.binding=deepcopy(context(binding));scope.pid=int(scope.binding['processIdentity'].split(':')[0]);need(integer(scope.pid,1))
        scope.artifact_root=Path(artifact_root);scope.monotonic=monotonic
        scope.originals=PhoneEmoteOriginals(scope.artifact_root,scope.binding,scope.run,scope.role,guard,
            lambda *_args:need(False),monotonic=monotonic)
        return deepcopy(scope.decode(value))

    @staticmethod
    def replay_scripts(reader,frames):
        # Extend through the existing original packet validator and pure native
        # history state machine. Its ordinary <=512-frame batch API stays intact.
        # No transport, callback, expected facts or clock replacement is involved.
        need(isinstance(reader,NativeScriptObservation) and reader.ios is False and len(frames)<=LIMIT)
        reader.restore_history([])
        for frame in frames:
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

    def validate_frame(self,frame,previous=None):
        exact(frame,{'group','ui','widgets','phaseBefore','phaseAfter','hostEpochMs','epochMs'})
        need(integer(frame['epochMs'],1) and number(frame['hostEpochMs'],1,1e15))
        selected,current,_urls=source(frame['group'],self.pid,frame['epochMs'])
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
        need(before['active'] and before['activations'] and after['active'] and after['activations'])
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
            self.lock.assert_held();need(not self.failed and self.guard() is not False and same(self.store.read(),self.previous))
            self.state['revision']=len(self.frames)
            value=dict(emoteSourcesVersion=VERSION,runId=self.run,fixtureUrl=self.phase.fixture_url,role=self.role,
                binding=self.binding,artifactRoot=str(self.artifact_root),payload=pack([self.state]))
            self.store.write(value,self.previous);need(same(self.store.read(),value));self.previous=deepcopy(value)
        except Exception:
            self.failed=True
            if same(self.store.read(),self.previous):
                if self.previous is not None:self.state,self.frames=self.decode(self.previous)
                else:self.state,self.frames=dict(phase='ready',revision=0,manifests=[],pending=None),[]
            raise

    def read(self):
        need(getattr(self,'historical',False) is False)
        self.lock.assert_held();need(not self.failed and self.state['phase']=='ready' and len(self.frames)<LIMIT and self.guard() is not False)
        started=previous=self.monotonic();need(number(started,0,1e15))
        def bound():
            nonlocal previous
            self.lock.assert_held();need(self.guard() is not False)
            now=self.monotonic();need(number(now,previous,1e15) and now-started<5);previous=now
        last=self.frames[-1] if self.frames else None
        old=last['group'] if last else None
        roots=self.adapter._script_roots(self.selector,read_only=True)
        scripts=self.adapter._script_execution_observer(self.selector,read_only=True)
        native=self.adapter._native_feature_observer(self.selector,read_only=True)
        ui=self.adapter._emote_controls(self.selector,lambda *_:need(False),read_only=True).io
        need(roots.pid==scripts.pid==native.pid==ui.pid==self.pid and native.ios is False and scripts.ios is False)
        if old:
            roots.restore(old['rootsAfter']);self.replay_scripts(scripts,self.frames)
            restore_native(native,old['native']);native.animation_history=self.replay_animation(self.frames)
            native.rig=old['native']['animation']['rigId']
            native.rig_sequence=old['native']['animation']['evaluationSequence']
            restore_ui(ui,last['widgets'],widget_packet)
        # Persist responsibility before any actual observation request. A lost
        # dispatch/result may not disappear through object reconstruction.
        epoch_local=self.monotonic();epoch=native.clock_ms();need(integer(epoch,1))
        self.state.update(phase='reading',pending=dict(startedEpochMs=epoch,role=self.role,revision=len(self.frames),original=None,manifest=None));self.save();bound()
        host_started=self.phase.epoch_ms();need(number(host_started,1,1e15))
        phase_started=self.monotonic();bound()
        phase=self.phase.read(last['phaseAfter'] if last else None);bound()
        before=roots.read(roots.last['sequence'] if roots.last else 0);bound()
        script=scripts.read(scripts.sequence,require_effects=True,require_code_identity=True,require_load_history=True,require_membership=True);bound()
        packet=native.read(native.sequence,require_animation=True,require_animation_history=True);bound()
        after=roots.read(before['sequence']);bound()
        visual=ui.capture();bound();widgets=deepcopy(ui.original_packet)
        final=self.phase.status(phase['status']);bound()
        device_epoch=native.clock_ms();host_epoch=self.phase.epoch_ms();bound()
        frame=dict(group=dict(rootsBefore=before,script=script,native=packet,rootsAfter=after),ui=visual,widgets=widgets,
            phaseBefore=phase['status'],phaseAfter=final,hostEpochMs=host_epoch,epochMs=device_epoch)
        stable=self.validate_frame(frame,last);bound()
        fresh(before['requestedEpochMs'],device_epoch)
        # Frozen external clocks cannot conceal late sequential acquisition.
        need(max(device_epoch-before['requestedEpochMs'],epoch-before['requestedEpochMs']+(previous-epoch_local)*1000)<=1500
            and max(host_epoch-phase['status']['capturedEpochMs'],
                host_started-phase['status']['capturedEpochMs']+(previous-phase_started)*1000)<=1500)
        original=self.originals.write(len(self.frames)+1,frame);bound()
        manifests=self.originals.append(self.state['manifests'],original);bound()
        self.frames.append(deepcopy(frame));self.state.update(phase='ready',manifests=manifests,pending=None);self.save();bound()
        # Durability/guard work is part of delivery time, too. Accepted packets
        # remain historical if a slow final write prevents a fresh return.
        delivered_epoch=native.clock_ms();delivered_host=self.phase.epoch_ms();bound()
        need(integer(delivered_epoch,device_epoch) and number(delivered_host,host_epoch,1e15)
            and max(delivered_epoch-before['requestedEpochMs'],epoch-before['requestedEpochMs']+(previous-epoch_local)*1000)<=1500
            and max(delivered_host-phase['status']['capturedEpochMs'],
                host_started-phase['status']['capturedEpochMs']+(previous-phase_started)*1000)<=1500)
        if not stable:raise EmotePhaseChanged('Original Emote sources crossed the active input phase; no current facts returned')
        return deepcopy(frame)
