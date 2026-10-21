"""Durable per-role original Emote acquisition; no action or effect verdict.

Interrupted reads retain responsibility. Historical replay restores source
cursors only; every successful read obtains new native/UI/fixture originals.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import time

from adapters.emote_rig_measurements import source,continuation
from adapters.native_feature_observation import exact,fresh,integer,need,number
from adapters.native_script_roots import validate as roots_packet
from adapters.native_script_observation import NativeScriptObservation
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.normal_ui import NativeUIError
from adapters.token_emote_ui import snapshot
from feature_journeys.contract import identifier
from feature_journeys.phase_fixture import PhaseFixtureReader,validate as phase_packet
from overte_phone_emote_controls import validate as widget_packet
from overte_phone_graphics_samples import restore_native,restore_ui
from overte_phone_script_history import pack,unpack,same
from overte_phone_script_lock import PhoneScriptSourceLock

VERSION=1
LIMIT=128


class EmotePhaseChanged(NativeUIError):
    """A fully retained original acquisition crossed an actual fixture phase."""


class PhoneEmoteSources:
    def __init__(self,adapter,selector,phase,role,lock,*,monotonic=time.monotonic):
        need(isinstance(phase,PhaseFixtureReader) and phase.area=='emotes'
            and role in ('primary','actor') and isinstance(lock,PhoneScriptSourceLock) and callable(monotonic))
        path=adapter.state_path(selector);need(lock.path==path.with_name('phone-script-sources.lock'));lock.assert_held()
        self.adapter,self.selector,self.phase,self.role,self.lock=adapter,selector,phase,role,lock
        self.monotonic=monotonic;self.run=identifier(phase.run)
        _ui,_service,binding,self.guard,_installed=adapter.normal_feature_runtime(selector,read_only=True)
        self.binding=deepcopy(context(binding));self.pid=int(self.binding['processIdentity'].split(':')[0]);need(integer(self.pid,1))
        self.store=PrivateFeatureState(path.with_name('phone-emote-'+role+'-sources.json'))
        self.previous=self.store.read();self.frames=[]
        self.state=dict(phase='ready',revision=0,transcript=pack([]),pending=None)
        if self.previous is not None:
            try:self.state,self.frames=self.decode(self.previous)
            except (KeyError,TypeError,ValueError):
                raise NativeUIError('Original Emote source journal is invalid') from None

    def decode(self,value):
        exact(value,{'emoteSourcesVersion','runId','fixtureUrl','role','binding','payload'})
        need(type(value['emoteSourcesVersion']) is int and value['emoteSourcesVersion']==VERSION
            and value['runId']==self.run and value['fixtureUrl']==self.phase.fixture_url and value['role']==self.role
            and same(context(value['binding']),self.binding))
        rows=unpack(value['payload']);need(len(rows)==1);state=rows[0]
        exact(state,{'phase','revision','transcript','pending'})
        need(state['phase'] in ('ready','reading') and integer(state['revision'],0,LIMIT))
        frames=unpack(state['transcript']);need(len(frames)==state['revision'])
        # Existing Script history validation owns immutable module/code/load/
        # manager transitions. It issues no transport calls during replay.
        replay=NativeScriptObservation(lambda *_:need(False),lambda:need(False),lambda:need(False),lambda:need(False),self.pid)
        replay.restore_history([frame['group']['script'] for frame in frames])
        previous=None
        for frame in frames:
            self.validate_frame(frame,previous);previous=frame
        if state['phase']=='ready':need(state['pending'] is None)
        else:
            exact(state['pending'],{'startedEpochMs','role','revision'})
            need(integer(state['pending']['startedEpochMs'],1) and state['pending']['role']==self.role
                and type(state['pending']['revision']) is int and state['pending']['revision']==state['revision'])
        return deepcopy(state),deepcopy(frames)

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
        try:
            self.lock.assert_held();need(self.guard() is not False and same(self.store.read(),self.previous))
            self.state['revision']=len(self.frames);self.state['transcript']=pack(self.frames)
            value=dict(emoteSourcesVersion=VERSION,runId=self.run,fixtureUrl=self.phase.fixture_url,role=self.role,
                binding=self.binding,payload=pack([self.state]))
            self.store.write(value,self.previous);need(same(self.store.read(),value));self.previous=deepcopy(value)
        except Exception:
            if same(self.store.read(),self.previous):
                if self.previous is not None:self.state,self.frames=self.decode(self.previous)
                else:self.state,self.frames=dict(phase='ready',revision=0,transcript=pack([]),pending=None),[]
            raise

    def read(self):
        self.lock.assert_held();need(self.state['phase']=='ready' and len(self.frames)<LIMIT and self.guard() is not False)
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
            roots.restore(old['rootsAfter']);scripts.restore_history([frame['group']['script'] for frame in self.frames])
            restore_native(native,old['native']);native.rig=old['native']['animation']['rigId']
            native.rig_sequence=old['native']['animation']['evaluationSequence']
            restore_ui(ui,last['widgets'],widget_packet)
        # Persist responsibility before any actual observation request. A lost
        # dispatch/result may not disappear through object reconstruction.
        epoch=native.clock_ms();need(integer(epoch,1))
        self.state.update(phase='reading',pending=dict(startedEpochMs=epoch,role=self.role,revision=len(self.frames)));self.save();bound()
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
        need(max(device_epoch-before['requestedEpochMs'],epoch-before['requestedEpochMs']+(previous-started)*1000)<=1500
            and max(host_epoch-phase['status']['capturedEpochMs'],
                host_started-phase['status']['capturedEpochMs']+(previous-phase_started)*1000)<=1500)
        self.frames.append(deepcopy(frame));self.state.update(phase='ready',pending=None);self.save();bound()
        # Durability/guard work is part of delivery time, too. Accepted packets
        # remain historical if a slow final write prevents a fresh return.
        delivered_epoch=native.clock_ms();delivered_host=self.phase.epoch_ms();bound()
        need(integer(delivered_epoch,device_epoch) and number(delivered_host,host_epoch,1e15)
            and max(delivered_epoch-before['requestedEpochMs'],epoch-before['requestedEpochMs']+(previous-started)*1000)<=1500
            and max(delivered_host-phase['status']['capturedEpochMs'],
                host_started-phase['status']['capturedEpochMs']+(previous-phase_started)*1000)<=1500)
        if not stable:raise EmotePhaseChanged('Original Emote sources crossed the active input phase; no current facts returned')
        return deepcopy(frame)
