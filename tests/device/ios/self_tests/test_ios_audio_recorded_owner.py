"""Real recording-owner WAL/locks/original files; modeled UIKit/audio/fixture.

No microphone, PCM, acoustics, iOS process or installed binary is exercised.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from copy import deepcopy
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
import uuid
from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import pack,unpack
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.phase_fixture import PhaseFixtureReader
from feature_journeys.witness import Client
from ios.adapters.audio_recorded_owner import IOSAudioRecordedOwner
from ios.adapters.normal_audio import IOSAudioIO
from ios.self_tests.test_ios_create_files import BINDING
from self_tests.test_native_feature_observation import Boundary as NativeBoundary
from self_tests.test_recorded_preview_history import voice,event
from self_tests.test_token_audio_ui import AudioBoundary

RUN='1'*32


class Model(AudioBoundary):
    def __init__(self):
        super().__init__();self.instance=str(uuid.UUID(self.instance));self.position=.6
        self.native=NativeBoundary();self.owner=None;self.counter=0;self.inputs=0;self.loss=False;self.ignore=False
        self.recorded=voice([],cycle=0,started=0);self.active_verb='record-start';self.ticket='2'*32
        self.activations=[];self.phase_sequence=0;self.add_phase(self.active_verb,self.ticket)
        self.changed=False;self.corrupt_ui=False;self.native_instance='a'*32

    def epoch(self):return 5000000+int(round(self.clock*1000))
    def native_epoch(self):return 20000+int(round(self.clock*1000))
    def tick(self):self.clock+=.001
    def add_phase(self,verb,ticket):
        self.active_verb,self.ticket=verb,ticket
        self.activations.append(dict(sequence=len(self.activations)+1,ticket=ticket,activatedEpochMs=self.epoch(),stimulus=dict(verb=verb,inputs={})))
    def capture(self):
        self.tick();self.counter+=1
        self.owner.query_intent(dict(schemaVersion=1,commandId='ios-'+uuid.uuid4().hex,action='normal-ui-input',operation='observe'))
        value=super().capture();value.pop('generation')
        value.update(schemaVersion=1,frameSpace='qt-window-logical',processId=42,sampleEpochMs=self.native_epoch(),elapsedMs=int(self.clock*1000),lastSequence=self.inputs,tabletShown=True)
        for row in value['controls']:
            row.update(token=str(uuid.UUID(row['token'])),focused=False,frame=dict(x=10,y=10,width=100,height=40))
        if self.corrupt_ui:value['processId']=43
        return value
    def original(self,identifier,token):
        row=next(row for row in self.capture()['controls'] if row['id']==identifier)
        need(row['token']==token and row['inputReady'] and row['enabled'])
        need(self.owner.state['pending']['inputs'][-1]['identifier']==identifier)
    def activate(self,identifier,*,token):
        self.original(identifier,token);self.inputs+=1;self.actions.append(identifier)
        if self.ignore:return
        need(identifier=='audio.record')
        self.tick()
        if self.active:
            self.active=False;self.phase='cancelled'
            events=self.recorded['events']+[event(self.recorded['events'][-1]['eventSequence']+1,'cancelled',96000,epoch=self.native_epoch())]
            self.recorded=voice(events,cycle=self.cycle,started=self.recorded['startedEpochMs'])
        else:
            self.active=True;self.phase='capturing';self.cycle+=1
            seq=self.recorded['events'][-1]['eventSequence']+1 if self.recorded['events'] else 1
            self.recorded=voice([event(seq,'capturing',96000,epoch=self.native_epoch())],cycle=self.cycle,started=self.native_epoch())
        if self.loss:raise NativeUIError('Explicit model lost the ordinary input return after delivery')
    def send_native(self,command):
        self.owner.query_intent(command);self.tick();self.native.send(command)
        value=self.native.sample;value.update(processId=42,capturedEpochMs=self.native_epoch(),requestedEpochMs=self.native_epoch(),instance=self.native_instance,animation={})
        value.pop('animationFence');value['audio']=dict(recording=False,muted=self.muted,recordedVoice=deepcopy(self.recorded))
    def reader(self):
        from adapters.native_feature_observation import NativeFeatureObservation
        return NativeFeatureObservation(self.send_native,lambda:json.dumps(self.native.sample),self.native_epoch,self.guard,42,
            ios=True,monotonic=lambda:self.clock,sleep=self.sleep)
    def guard(self):return not self.changed
    def client(self):
        outer=self
        class PhaseBoundary(Client):
            def request(self,path,value=None,method=None,*,phase_nonce=None,**_kwargs):
                need(path=='/runs/'+RUN+'/phase' and phase_nonce is not None);outer.phase_sequence+=1
                return dict(fixturePhaseVersion=1,instance='3'*32,sequence=outer.phase_sequence,requestId=phase_nonce,
                    runId=RUN,area='audio',capturedEpochMs=outer.epoch(),active=True,createdEpochMs=5000000,retiredEpochMs=None,activations=deepcopy(outer.activations))
        return PhaseBoundary('https://controlled.invalid/feature-fixture/v1','r'*64)
    def io(self):
        return IOSAudioIO(SimpleNamespace(capture=self.capture,native=self,
            ui=SimpleNamespace(click_with_token=lambda locator,token:self.activate(locator.value.split('OverteNavigation.')[1],token=token))))


class AudioRecordedOwnerTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name);self.root.chmod(0o700);self.store=PrivateFeatureState(self.root/'ios-audio-recorded-owner.json')
        self.lock=ScriptSourceLock(self.root/'script-feature-sources.lock');self.model=Model()
    @contextmanager
    def owner(self):
        m=self.model;failure=None
        with self.lock.held():
            try:
                owner=IOSAudioRecordedOwner(self.store,self.root,BINDING,RUN,self.lock,m.guard,native=m.reader(),io=m.io(),
                    phase=PhaseFixtureReader(m.client(),RUN,'audio',epoch_ms=m.epoch,monotonic=lambda:m.clock),
                    epoch_ms=m.epoch,monotonic=lambda:m.clock,sleep=m.sleep)
                m.owner=owner;yield owner
            except BaseException as original:failure=original
        if failure is not None:raise failure
    def start(self):
        with self.owner() as owner:return owner.act(self.model.ticket,'record-start')
    def cancel_phase(self):self.model.add_phase('record-cancel','4'*32)

    def test_normal_start_reconstruction_cancel_preserves_native_history_and_quiet_originals(self):
        started=self.start();self.assertTrue(started['state']['recording']);self.assertEqual(24000,started['state']['recordedFrames'])
        self.cancel_phase()
        with self.owner() as owner:
            actual=owner.act(self.model.ticket,'record-cancel');self.assertEqual('cancelled',actual['state']['phase'])
            self.assertEqual(0,actual['state']['bufferedFrames']);self.assertEqual(2,len(owner.state['operations']))
            references=deepcopy(owner.state['records']);fixture_url=owner.fixture_url
        self.assertEqual(['audio.record','audio.record'],self.model.actions)
        queries=self.model.counter;inputs=self.model.inputs
        with self.lock.held():
            archived=IOSAudioRecordedOwner.archive(self.store,self.root,BINDING,RUN,self.lock,fixture_url)
            self.assertEqual(references,archived.state['records'])
            self.assertEqual('cancelled',archived.original(references[-1])['originals']['native']['audio']['recordedVoice']['event']['phase'])
        self.assertEqual(queries,self.model.counter);self.assertEqual(inputs,self.model.inputs)

    def test_lost_start_return_is_resolved_by_new_originals_without_resending(self):
        self.model.loss=True
        with self.owner() as owner,self.assertRaises(NativeUIError):owner.act(self.model.ticket,'record-start')
        self.assertEqual(1,self.model.inputs);self.model.loss=False
        with self.owner() as owner:
            self.assertIsNotNone(owner.state['pending']);actual=owner.act(self.model.ticket,'record-start')
            self.assertTrue(actual['state']['recording']);self.assertIsNone(owner.state['pending'])
        self.assertEqual(1,self.model.inputs)

    def test_ignored_start_remains_owned_and_reconstruction_never_replays_it(self):
        self.model.ignore=True
        with self.owner() as owner,self.assertRaises(NativeUIError):owner.act(self.model.ticket,'record-start')
        self.assertEqual(1,self.model.inputs)
        with self.owner() as owner:
            with self.assertRaises(NativeUIError):owner.act(self.model.ticket,'record-start')
            self.assertIsNotNone(owner.state['pending'])
        self.assertEqual(1,self.model.inputs)

    def test_lost_cancel_return_reconstruction_requires_independent_cancelled_quiet_samples(self):
        self.start();self.cancel_phase();self.model.loss=True
        with self.owner() as owner,self.assertRaises(NativeUIError):owner.act(self.model.ticket,'record-cancel')
        self.model.loss=False
        with self.owner() as owner:
            actual=owner.act(self.model.ticket,'record-cancel');self.assertEqual('cancelled',actual['state']['phase'])
        self.assertEqual(2,self.model.inputs)

    def test_changed_candidate_blocks_any_input_and_wrong_ticket_cannot_relabel_history(self):
        with self.owner() as owner:
            with self.assertRaises((NativeUIError,ValueError)):owner.act('5'*32,'record-start')
            self.model.changed=True
            with self.assertRaises(NativeUIError):owner.act(self.model.ticket,'record-start')
        self.assertEqual(0,self.model.inputs)

    def test_missing_original_fails_pure_reconstruction(self):
        self.start()
        with self.owner() as owner:
            reference=owner.state['records'][0];path=owner.frames.path(owner.frames.expand(reference));fixture_url=owner.fixture_url
        path.unlink()
        with self.lock.held(),self.assertRaises((NativeUIError,OSError)):
            IOSAudioRecordedOwner.archive(self.store,self.root,BINDING,RUN,self.lock,fixture_url)

    def test_original_clock_birth_change_refuses_cancel_before_any_new_input(self):
        self.start();self.cancel_phase();self.model.native_instance='b'*32
        with self.owner() as owner,self.assertRaises(NativeUIError):owner.act(self.model.ticket,'record-cancel')
        self.assertEqual(1,self.model.inputs)

    def test_retimed_native_event_prefix_refuses_cancel_before_any_new_input(self):
        self.start();self.cancel_phase()
        self.model.recorded['events'][0]['publishedEpochMs']+=1
        self.model.recorded['event']=deepcopy(self.model.recorded['events'][-1])
        with self.owner() as owner,self.assertRaises(NativeUIError):owner.act(self.model.ticket,'record-cancel')
        self.assertEqual(1,self.model.inputs)

    def test_ignored_cancel_stays_pending_after_reconstruction_without_second_input(self):
        self.start();self.cancel_phase();self.model.ignore=True
        with self.owner() as owner,self.assertRaises(NativeUIError):owner.act(self.model.ticket,'record-cancel')
        self.assertEqual(2,self.model.inputs)
        with self.owner() as owner:
            with self.assertRaises(NativeUIError):owner.act(self.model.ticket,'record-cancel')
            self.assertIsNotNone(owner.state['pending'])
        self.assertEqual(2,self.model.inputs)

    def test_lost_owner_metadata_cannot_hide_existing_original_carriers(self):
        self.start();original=self.store.read();self.store.discard(original);queries=self.model.counter
        with self.assertRaises(NativeUIError):
            with self.owner():pass
        self.assertEqual(queries,self.model.counter);self.assertEqual(1,self.model.inputs)

    def test_completed_cancel_without_both_retained_quiet_originals_fails_pure_decode(self):
        self.start();self.cancel_phase()
        with self.owner() as owner:
            owner.act(self.model.ticket,'record-cancel');fixture_url=owner.fixture_url
        original=self.store.read();changed=deepcopy(original);state=unpack(changed['payload'])[0]
        state['operations'][-1]['quiet']=state['operations'][-1]['quiet'][-1:];changed['payload']=pack([state])
        self.store.write(changed,original)
        with self.lock.held(),self.assertRaises(NativeUIError):
            IOSAudioRecordedOwner.archive(self.store,self.root,BINDING,RUN,self.lock,fixture_url)

    def test_requested_sleep_without_measured_quiet_does_not_qualify_cancel(self):
        self.start();self.cancel_phase()
        with self.owner() as owner:
            # Normal TokenAudioUI.cancel keeps its genuine modeled stable UI
            # wait. Suppress only this owner's independent quiet-window wait.
            owner.sleep=lambda _seconds:None
            with self.assertRaises(NativeUIError):owner.act(self.model.ticket,'record-cancel')
            self.assertGreaterEqual(len(owner.state['records']),5)
            durable=unpack(self.store.read()['payload'])[0]
            self.assertIsNone(durable['pending']['after']);self.assertEqual([],durable['pending']['quiet'])
        with self.owner() as owner:
            self.assertIsNotNone(owner.state['pending']);self.assertEqual(2,self.model.inputs)


if __name__=='__main__':unittest.main()
