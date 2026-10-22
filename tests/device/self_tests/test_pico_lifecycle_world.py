"""Real owner/readers/session over explicit original native/physics boundaries."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[3]))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from adapters.native_feature_observation import need
from adapters.normal_ui import NativeUIError
from adapters.pico4.lifecycle_world import PicoLifecycleWorld,MOVE
from adapters.script_journey.history import unpack
from adapters.script_journey.lock import ScriptSourceLock
from openxr_input.adapter_session import PicoOpenXrAdapterSession,AdapterSessionError
from self_tests.test_pico_lifecycle_back import BINDING
from self_tests.test_pico_lifecycle_source import Boundary as UiBoundary,editor,RUN
from self_tests.test_pico_lifecycle_drive import Boundary as DriveBoundary
from self_tests.test_pico_lifecycle_gesture import Boundary as GestureBoundary,event,sample,proof,native_status
from self_tests.test_pico_openxr_adapter_session import FakeTransport


class Native:
    def __init__(self):
        self.clock=0.;self.alive=True;self.ui=UiBoundary();self.ui.rows=[];self.ui.raised=False;self.ui.shown=False
        self.drive=DriveBoundary();self.axes=GestureBoundary();self.axis_frame=1;self.changed=None;self.layer={}
        self.original_send=self.axes.send
        def axes(request):
            self.axes.clock=self.clock;self.axis_frame+=1
            self.axes.source.update(frameSequence=self.axis_frame,frameEpochMs=self.epoch(),frameElapsedMs=round(self.clock*1000))
            self.original_send(request)
        self.axes.send=axes
        original=self.ui.send
        def ui(request):original(request);self.ui.value['capturedEpochMs']=self.epoch()
        self.ui.send=ui
        original_drive=self.drive.send
        def drive(request):self.drive.clock=self.clock;original_drive(request)
        self.drive.send=drive
    def epoch(self):return 20000+round(self.clock*1000)
    def sleep(self,seconds):
        self.clock+=seconds
        if self.changed:self.changed(self)
    def sources(self):
        result=self.ui.source(),self.axes.reader(),self.drive.reader()
        for source in result:
            source.clock_ms=self.epoch;source.guard=lambda:self.alive;source.monotonic=lambda:self.clock;source.sleep=self.sleep
        return result
    def create(self):self.ui.rows=[editor()];self.ui.raised=self.ui.shown=True
    def retire(self):
        self.ui.rows[0].update(fieldAlive=False,pageAlive=False,attached=False,visible=False,focused=False,current=False,text='')
        self.ui.raised=False;self.ui.home=True # Original context remains alive.
    def publish(self,kind,y,identity):
        self.clock+=.001;self.axis_frame+=1
        row=event(kind,len(self.axes.source['events'])+1,identity,y,proof(self.layer))
        row.update(frameSequence=self.axis_frame,occurredEpochMs=self.epoch(),elapsedMs=round(self.clock*1000))
        self.axes.source['events'].append(row);self.axes.source.update(current=sample(y),known=True,activeGesture=identity if y else '')


class Transport(FakeTransport):
    def __init__(self,native,path):super().__init__();self.native,self.path=native,path;self.fail=None;self.before=None;self.consume=True
    def stage(self,envelope,profile):
        state=unpack(json.loads(self.path.read_text())['payload'])[0];attempt=state['attempts'][-1]
        assert attempt['phase']=='enveloped' and attempt['envelope']==envelope
        if self.before:self.before(state,envelope)
        result=super().stage(envelope,profile)
        self.native.layer=native_status()|dict(acceptedNonce=envelope['sessionNonce'],acceptedSequence=envelope['sequence'],
            vectorAppliedSequence=envelope['sequence'],activeCommandId=envelope['commands'][0]['id'],
            updatedEpochMs=self.native.epoch(),leftThumbstickAppliedY=MOVE['strength'])
        if self.consume:
            self.native.publish('started',MOVE['strength'],format(len(self.envelopes)+100,'032x'))
            if not self.native.ui.raised:
                self.native.drive.source['driveKeys'][2]=self.native.drive.source['rawDriveKeys'][2]=MOVE['strength']
                self.native.drive.source['feetPosition']=[1,2,3.5]
        if self.fail=='grant':raise AdapterSessionError('Explicit uncertain native grant')
        return result
    def read_status(self,**kwargs):
        result=super().read_status(**kwargs);result.update(updatedEpochMs=self.native.epoch())
        if self.fail=='ack' and kwargs.get('expected_sequence'):raise AdapterSessionError('Explicit lost response')
        if self.fail=='neutral' and kwargs.get('expected_sequence') is None:result['state']='error'
        return result
    def cleanup(self):
        super().cleanup()
        if not self.native.layer:return
        self.native.layer.update(state='neutral',enabled=False,detail='grant-absent',activeCommandId='',updatedEpochMs=self.native.epoch())
        if self.fail!='axis-neutral':self.native.publish('neutral',0,self.native.axes.source['activeGesture'])
        self.native.drive.source['driveKeys'][2]=self.native.drive.source['rawDriveKeys'][2]=0
        if self.fail=='release':raise AdapterSessionError('Explicit lost release response')


class LifecycleWorldTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory(prefix='lifecycle-world-');self.root=Path(self.temporary.name);self.root.chmod(0o700)
        self.path=self.root/'world.json';self.native=Native();self.transport=Transport(self.native,self.path)
        self.session=PicoOpenXrAdapterSession(self.transport,'explicit-world-target',self.root);self.session.begin(BINDING['processIdentity'])
    def tearDown(self):self.temporary.cleanup()
    def owner(self,binding=BINDING):
        return PicoLifecycleWorld(*self.native.sources(),self.session,self.path,RUN,binding,lambda:self.native.alive,
            ScriptSourceLock(self.root/'script-sources.lock'),monotonic=lambda:self.native.clock,sleep=self.native.sleep)
    def started(self):
        owner=self.owner();self.assertEqual(0,owner.prepare()['worldAttempts']);self.native.create();return owner
    def test_two_actual_consumed_gestures_remain_separate_from_editor_blocked_and_actual_avatar_movement(self):
        owner=self.started();blocked=owner.world_input()
        self.assertEqual((1,[],0.),(blocked['worldAttempts'],blocked['heldInputs'],blocked['worldDisplacement']))
        first=deepcopy(blocked['originals']['gesture']['source']['events'][-1]);self.assertEqual('quiet',self._release(owner))
        self.native.retire();self.native.ui.shown=False;moved=owner.world_input()
        self.assertEqual(2,moved['worldAttempts']);self.assertEqual(['forward'],moved['heldInputs'])
        self.assertEqual(dict(x=0,y=0,z=.5),moved['positionDelta']);self.assertEqual(.5,moved['worldDisplacement'])
        self.assertTrue(moved['originals']['ui']['source']['editors'][0]['contextAlive'])
        self.assertEqual(first,moved['originals']['gesture']['source']['events'][1]);self.assertEqual('quiet',self._release(owner))
        self.assertEqual(2,len(self.transport.envelopes));self.assertEqual(2,self.transport.cleanup_count);self.assertTrue(self.path.exists())
        self.assertEqual(2,self.owner().reconcile()['worldAttempts'])
    def _release(self,owner):
        result=owner.release();self.assertEqual([],result['heldInputs'])
        return unpack(json.loads(self.path.read_text())['payload'])[0]['attempts'][-1]['phase']
    def test_ack_without_original_client_consumption_never_counts_and_cannot_be_repeated(self):
        owner=self.started();self.transport.consume=False
        with self.assertRaises(NativeUIError):owner.world_input()
        self.assertEqual('enveloped',owner.state['attempts'][0]['phase']);self.assertEqual(1,len(self.transport.envelopes))
        with self.assertRaises(NativeUIError):self.owner().reconcile()
        with self.assertRaises(NativeUIError):self.owner().world_input()
        self.assertEqual(1,len(self.transport.envelopes));self.assertTrue(self.path.exists())
    def test_lost_ack_restores_original_counter_without_resending_input(self):
        owner=self.started();self.transport.fail='ack'
        with self.assertRaises(NativeUIError):owner.world_input()
        self.transport.fail=None;restored=self.owner();self.assertEqual(1,restored.reconcile()['worldAttempts'])
        self.assertEqual('quiet',self._release(restored));self.assertEqual(1,len(self.transport.envelopes))
    def test_uncertain_grant_is_observable_but_cannot_be_adopted_for_release(self):
        owner=self.started();self.transport.fail='grant'
        with self.assertRaises(NativeUIError):owner.world_input()
        self.transport.fail=None;restored=self.owner();self.assertEqual(1,restored.reconcile()['worldAttempts'])
        with self.assertRaises(NativeUIError):restored.release()
        self.assertEqual(0,self.transport.cleanup_count);self.assertTrue(self.path.exists())
    def test_lost_release_is_reconciled_read_only_with_original_neutral_and_three_second_stability(self):
        owner=self.started();owner.world_input();self.transport.fail='release'
        with self.assertRaises(NativeUIError):owner.release()
        self.assertEqual('release-issued',owner.state['attempts'][0]['phase']);self.transport.fail=None
        self.assertEqual('quiet',self._release(self.owner()));self.assertEqual(1,self.transport.cleanup_count)
    def test_input_or_release_intent_write_failure_prevents_first_possible_transport_mutation(self):
        owner=self.started()
        with patch.object(owner.store,'write',side_effect=NativeUIError('Explicit disk failure')),self.assertRaises(NativeUIError):owner.world_input()
        self.assertEqual([],self.transport.envelopes)
        owner=self.owner();owner.world_input()
        with patch.object(owner.store,'write',side_effect=NativeUIError('Explicit disk failure')),self.assertRaises(NativeUIError):owner.release()
        self.assertEqual(0,self.transport.cleanup_count)
    def test_newer_cursor_or_different_original_binding_never_releases_someone_elses_stream(self):
        owner=self.started();owner.world_input()
        for key in ('processIdentity','artifactSha256','generation'):
            wrong=deepcopy(BINDING);wrong[key]=2 if key=='generation' else '9'*len(wrong[key])
            with self.subTest(key=key),self.assertRaises(NativeUIError):self.owner(wrong)
        with patch.object(self.transport,'stage',side_effect=lambda envelope,profile:FakeTransport.stage(self.transport,envelope,profile)):
            self.session.stage(BINDING['processIdentity'],'input.look',dict(horizontal=.1))
        with self.assertRaises(NativeUIError):owner.release()
        self.assertEqual(0,self.transport.cleanup_count)
    def test_ack_neutral_or_stopped_axes_cannot_substitute_for_original_client_neutral(self):
        owner=self.started();owner.world_input();self.transport.fail='axis-neutral'
        with self.assertRaises(NativeUIError):owner.release()
        self.assertEqual('release-issued',owner.state['attempts'][0]['phase']);self.assertTrue(self.path.exists())
    def test_home_without_a_closed_owned_tablet_cannot_become_post_editor_world_input(self):
        owner=self.started();owner.world_input();owner.release();self.native.retire()
        with self.assertRaises(NativeUIError):owner.world_input()
        self.assertEqual(1,len(self.transport.envelopes))

    def test_foreign_native_status_prevents_even_the_first_grant_removal(self):
        owner=self.started();owner.world_input();original=self.transport.read_status
        def foreign(**kwargs):return original(**kwargs)|dict(acceptedSequence=2)
        with patch.object(self.transport,'read_status',side_effect=foreign),self.assertRaises(NativeUIError):owner.release()
        self.assertEqual(0,self.transport.cleanup_count);self.assertEqual('consumed',owner.state['attempts'][-1]['phase'])

    def test_three_dimensional_motion_and_observation_gap_reset_release_window(self):
        owner=self.started();owner.world_input();started=self.native.clock
        def changed(native):
            if native.clock-started<1.5:native.drive.source['feetPosition'][0]+=.03
        self.native.changed=changed;owner.release();self.assertGreaterEqual(self.native.clock-started,4.25)
    def test_slow_locked_intent_cannot_send_a_gesture_from_aged_original_sources(self):
        owner=self.started();write=owner.store.write
        def slow(value,previous):
            write(value,previous)
            attempts=unpack(value['payload'])[0]['attempts']
            if attempts and attempts[-1]['phase']=='enveloped':self.native.clock+=2
        with patch.object(owner.store,'write',side_effect=slow),self.assertRaises(NativeUIError):owner.world_input()
        self.assertEqual([],self.transport.envelopes);self.assertEqual('enveloped',owner.state['attempts'][-1]['phase'])

    def test_foreign_original_started_gesture_after_owned_barrier_cannot_be_ignored(self):
        owner=self.started();owner.world_input();self.transport.cleanup()
        self.native.publish('started',MOVE['strength'],'e'*32)
        with self.assertRaises(NativeUIError):self.owner().reconcile()
        self.assertEqual(1,len(self.transport.envelopes))


if __name__=='__main__':unittest.main()
