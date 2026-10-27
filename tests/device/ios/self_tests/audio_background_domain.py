"""Actual installed OS/CAS codecs; declared recording, SDK and clocks."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from types import SimpleNamespace
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.phase_fixture import PhaseFixtureReader
from ios.adapters.audio_recorded_owner import IOSAudioRecordedOwner
from ios.adapters.audio_runtime import IOSAudioRuntime
from ios.adapters.appium_adapter import AppiumAdapter
from ios.self_tests.test_ios_script_runtime import IOSScriptRuntimeTests
from ios.self_tests.test_ios_audio_recorded_owner import Model,RUN
from self_tests.test_recorded_preview_history import voice,event

TICKET='7'*32


class AudioBackgroundDomain:
    def __init__(self,case,*,pages=False,prepare_recording=True):
        self.fixture=IOSScriptRuntimeTests();self.fixture.setUp();case.addCleanup(self.fixture.doCleanups)
        self.f=self.fixture.f;self.root=self.f.root;self.m=Model();self.m.muted=False
        if pages:
            from ios.self_tests.audio_page_cycle_domain import AudioPageCycleDomain
            self.m=AudioPageCycleDomain(self.root);self.m.automatic=False
            if prepare_recording:self.m.add_phase('open','3'*32)
        self.runtime=IOSAudioRuntime(self.f.adapter);source=self.runtime._sources('test-only');self.binding=source['binding']
        self.lock=ScriptSourceLock(self.root/'script-feature-sources.lock');case.enterContext(self.lock.held())
        self.inputs=[];self.reads=0;self.fault=None;self.native_blocked=False
        self.lifecycle=dict(backgrounds=0,activations=1,launches=1)
        model_send=self.m.send_native
        def send(command):
            case.assertTrue(self.f.process['foreground']);case.assertFalse(self.native_blocked)
            self.reads+=1;model_send(command);self.m.native.sample['lifecycle']=deepcopy(self.lifecycle)
        self.m.send_native=send
        self.m.guard=lambda:source['check']() is not False
        self.store=PrivateFeatureState(self.root/'ios-audio-recorded-owner.json')
        m=self.m
        parent=IOSAudioRecordedOwner(self.store,self.root,self.binding,RUN,self.lock,m.guard,native=m.reader(),io=m.io(),
            phase=PhaseFixtureReader(m.client(),RUN,'audio',epoch_ms=m.epoch,monotonic=lambda:m.clock),
            epoch_ms=m.epoch,monotonic=lambda:m.clock,sleep=m.sleep)
        m.owner=parent;self.parent=parent
        if prepare_recording:
            if pages:parent.act(m.ticket,'open');m.add_phase('record-start','4'*32)
            parent.act(m.ticket,'record-start');self.parent_bytes=self.store.path.read_bytes()
            m.add_phase('background-resume',TICKET)
        def sources(_selector):
            case.assertTrue(self.f.process['foreground']);case.assertFalse(self.native_blocked)
            source['check']()
            # Real runtime calls create separate normal/native source objects.
            # Model those per-factory callbacks without replacing the parent's
            # owner or forwarding child queries into a parent observation WAL.
            class Normal:
                observe_intent=None
                def capture(self):
                    previous=m.owner;m.owner=SimpleNamespace(query_intent=self.observe_intent)
                    try:return m.capture()
                    finally:m.owner=previous
            normal=Normal();native=m.reader();original_send=native.send
            def raw_send(command):
                previous=m.owner;m.owner=SimpleNamespace(query_intent=lambda _:None)
                try:return original_send(command)
                finally:m.owner=previous
            native.send=raw_send
            return dict(binding=self.binding,clock_source=native,native=normal,
                client=self.fixture.client,session='test-only',check=m.guard)
        self.runtime._sources=sources
        execute=self.fixture.client.execute
        def os_input(session,operation,values):
            if operation=='mobile: queryAppState':return 4 if self.f.process and self.f.process['foreground'] else 3
            if operation not in ('mobile: backgroundApp','mobile: activateApp'):return execute(session,operation,values)
            self.inputs.append(operation);state=PrivateFeatureState(self.root/'ios-audio-background.json').read()
            from adapters.script_feature.history import unpack
            current=unpack(state['payload'])[0]
            case.assertEqual('background-issued' if operation.endswith('backgroundApp') else 'foreground-issued',current['phase'])
            if operation=='mobile: backgroundApp':
                if self.fault!='ignored-home':
                    self.f.process['foreground']=False;self.lifecycle['backgrounds']+=1;m.tick()
                    if self.fault!='capture-retained':
                        old=m.recorded;m.active=False;m.phase='cancelled'
                        reason='microphone-muted' if self.fault=='wrong-error' else 'backgrounded'
                        m.recorded=voice(old['events']+[event(old['events'][-1]['eventSequence']+1,'cancelled',
                            old['events'][-1]['capturedBytes'],epoch=m.native_epoch(),error=reason)],cycle=m.cycle,started=old['startedEpochMs'])
            else:
                if self.fault!='ignored-activation':self.f.process['foreground']=True;self.lifecycle['activations']+=1;m.tick()
                if self.fault=='native-counters':self.lifecycle.update(backgrounds=0,activations=1)
                if self.fault=='restart':self.lifecycle['launches']+=1
            if self.fault==('lost-home' if operation.endswith('backgroundApp') else 'lost-activation'):
                raise OSError('Declared lost ordinary OS return')
            return True
        self.fixture.client.execute=os_input
        self.f.adapter.query_app_state=AppiumAdapter.query_app_state.__get__(self.f.adapter,type(self.f.adapter))
        self.owner=self.reopen() if prepare_recording else None

    def reopen(self):
        m=self.m
        owner=self.runtime.background_owner('test-only',RUN,self.lock,m.client(),epoch_ms=m.epoch,monotonic=lambda:m.clock,sleep=m.sleep)
        self.owner=owner;return owner
