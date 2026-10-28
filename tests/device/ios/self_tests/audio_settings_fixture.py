"""Typed Audio/Qt producer model over actual input codecs and private files."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json,uuid
from pathlib import Path
from types import SimpleNamespace
from adapters.native_feature_observation import NativeFeatureObservation,need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.phase_fixture import PhaseFixtureReader
from ios.adapters import audio_settings_source as settings
from ios.adapters.audio_recorded_owner import IOSAudioRecordedOwner
from ios.adapters.audio_settings_sources import AudioSettingsSources
from ios.adapters.audio_settings_owner import AudioSettingsOwner
from ios.adapters.normal_audio import IOSAudioIO
from ios.adapters.normal_input import observation
from ios.self_tests.test_ios_audio_recorded_owner import Model,RUN
from ios.self_tests.test_ios_create_files import BINDING
from self_tests.test_token_audio_ui import AudioBoundary
from self_tests.test_native_feature_observation import Boundary as NativeBoundary
from self_tests.test_recorded_preview_history import voice
from adapters.normal_ui import NativeUIError


class Domain(AudioBoundary):
    def __init__(self):
        super().__init__();self.changed=False;self.owner=None;self.ignore=False;self.loss=False;self.inputs=0;self.queries=[];self.raw='';self.sequence=0
        self.native=NativeBoundary();self.position=.6;self.mixer={key:0.0 for key in settings.MIXER_NUMBERS}
        self.script={key:False for key in settings.SCRIPT_BOOLS};self.script['settingsLoaded']=True
        self.script.update({key:0.0 for key in settings.SCRIPT_NUMBERS});self.script['inputVolume']=1.0
        self.script['persisted']={key:False for key in settings.PERSISTED_BOOLS};self.script['persisted'].update({key:0.0 for key in settings.PERSISTED_NUMBERS})
        self.client={key:False for key in settings.CLIENT_BOOLS};self.mutate=None
    def tick(self):self.clock+=.001
    def epoch(self):return 5000000+round(self.clock*1000)
    def native_epoch(self):return 20000+round(self.clock*1000)
    def stamp(self):self.tick();return dict(epochMs=self.native_epoch(),monotonicMs=round(self.clock*1000))
    def guard(self):return not self.changed
    def source(self):
        script=deepcopy(self.script);script['hmdContext']=self.hmd;script['mutedHmd' if self.hmd else 'mutedDesktop']=self.muted
        client=dict(self.client,muted=self.muted,localEcho=self.echo,voiceActive=self.active)
        return dict(iosAudioSettingsReadVersion=1,nativeHmd=self.hmd,scriptBefore=deepcopy(script),scriptAfter=deepcopy(script),
            clientBefore=deepcopy(client),clientAfter=deepcopy(client),mixerBefore=deepcopy(self.mixer),mixerAfter=deepcopy(self.mixer))
    def send_settings(self,query):
        self.queries.append(deepcopy(query));self.sequence+=1;before=self.stamp();data=self.source();after=self.stamp()
        packet=dict(iosAudioSettingsVersion=1,requestId=query['commandId'],runId=query['runId'],instance='a'*32,sequence=self.sequence,processId=42,
            clockDomain='native-main-ios-audio-settings',clockBefore=before,clockAfter=after,lifecycle=dict(backgrounds=0,activations=1,launches=1),source=data,
            **{key:False for key in settings.UNAVAILABLE})
        if self.mutate:self.mutate(packet)
        self.raw=json.dumps(packet)
    def reader(self):return settings.IOSAudioSettings(self.send_settings,lambda:self.raw,self.native_epoch,self.guard,42,monotonic=lambda:self.clock,sleep=self.sleep)
    def send_native(self,query):
        self.tick();self.native.send(query);value=self.native.sample
        value.update(instance='a'*32,processId=42,capturedEpochMs=self.native_epoch(),requestedEpochMs=self.native_epoch(),animation={})
        value.pop('animationFence',None);value['audio']=dict(recording=False,muted=self.muted,recordedVoice=voice([],cycle=0,started=0))
    def native_reader(self):return NativeFeatureObservation(self.send_native,lambda:json.dumps(self.native.sample),self.native_epoch,self.guard,42,ios=True,monotonic=lambda:self.clock,sleep=self.sleep)
    def capture(self):
        self.tick()
        if self.owner is not None and self.owner.state['pending'] is not None:self.owner.query_intent(dict(schemaVersion=1,commandId='ios-'+uuid.uuid4().hex,action='normal-ui-input',operation='observe'))
        value=super().capture();value.pop('generation');value['instance']=str(uuid.UUID(value['instance']))
        value.update(schemaVersion=1,frameSpace='qt-window-logical',processId=42,sampleEpochMs=self.native_epoch(),elapsedMs=round(self.clock*1000),lastSequence=self.inputs,tabletShown=True)
        for row in value['controls']:row.update(token=str(uuid.UUID(row['token'])),focused=False,frame=dict(x=10,y=10,width=100,height=40))
        return observation(value,42,self.native_epoch())
    def activate(self,identifier,*,token):
        row=next(row for row in self.capture()['controls'] if row['id']==identifier);need(row['token']==token and row['inputReady'])
        need(self.owner.state['pending']['input'] is not None);self.inputs+=1;self.actions.append(identifier)
        if not self.ignore:
            if identifier=='audio.mute':self.muted=not self.muted
            elif identifier=='audio.live-echo':self.echo=not self.echo
            else:raise AssertionError(identifier)
        if self.loss:raise NativeUIError('Declared lost ordinary input return after delivery')
    def scroll(self,identifier,direction,*,token):
        row=next(row for row in self.capture()['controls'] if row['id']==identifier);need(row['token']==token and self.owner.state['pending']['navigation'])
        self.actions.append('scroll-'+direction);self.position=0.0 if direction=='up' else .6
    def io(self):
        return IOSAudioIO(SimpleNamespace(capture=self.capture,
            native=SimpleNamespace(scroll=lambda direction,token:self.scroll('audio.scrollbar',direction,token=token)),
            ui=SimpleNamespace(click_with_token=lambda locator,token:self.activate(locator.value.split('OverteNavigation.')[1],token=token))))


class Fixture:
    def __init__(self,root):
        self.root=Path(root);self.lock=ScriptSourceLock(self.root/'script-feature-sources.lock');self.held=self.lock.held();self.held.__enter__()
        self.domain=Domain();m=Model()
        self.parent=IOSAudioRecordedOwner(PrivateFeatureState(self.root/'ios-audio-recorded-owner.json'),self.root,BINDING,RUN,self.lock,m.guard,
            native=m.reader(),io=m.io(),phase=PhaseFixtureReader(m.client(),RUN,'audio',epoch_ms=m.epoch,monotonic=lambda:m.clock),epoch_ms=m.epoch,monotonic=lambda:m.clock,sleep=m.sleep)
        m.owner=self.parent;d=self.domain
        self.source=dict(binding=deepcopy(BINDING),check=d.guard,clock_source=d.native_reader(),observer=SimpleNamespace(audio_settings=lambda clock_source:d.reader()))
        self.sources=AudioSettingsSources(PrivateFeatureState(self.root/'ios-audio-settings-source-owner.json'),self.parent,self.source,epoch_ms=d.epoch,monotonic=lambda:d.clock)
        self.owner=AudioSettingsOwner(PrivateFeatureState(self.root/'ios-audio-settings-restore.json'),self.sources,d.io(),sleep=d.sleep);d.owner=self.owner
    def close(self):self.held.__exit__(None,None,None)
