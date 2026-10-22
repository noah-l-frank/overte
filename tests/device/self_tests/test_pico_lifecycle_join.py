"""Actual X/world owners over explicit UI/input/physics boundaries."""
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
from adapters.normal_ui import NativeUIError
from adapters.pico4.lifecycle_back import PicoLifecycleBack,validate_history
from adapters.pico4.lifecycle_join import PicoLifecycleXJoin
from adapters.script_journey.history import unpack
from openxr_input.adapter_session import AdapterSessionError
from self_tests import test_pico_lifecycle_world as boundaries
from self_tests.test_pico_lifecycle_world import Transport,FakeTransport,BINDING,RUN


class XTransport(Transport):
    def __init__(self,*args):super().__init__(*args);self.back_path=None;self.back_count=0;self.neutral_epoch=None
    def stage(self,envelope,profile):
        if envelope['commands'][0]['operation']!='controller.button':return super().stage(envelope,profile)
        state=unpack(json.loads(self.back_path.read_text())['payload'])[0]
        assert state['phase']=='enveloped' and state['envelope']==envelope
        self.back_count+=1;self.neutral_epoch=self.native.epoch();result=FakeTransport.stage(self,envelope,profile);self.native.retire()
        if self.fail=='back-grant':raise AdapterSessionError('Explicit uncertain X grant')
        return result

    def read_status(self,**kwargs):
        result=super().read_status(**kwargs)
        if self.neutral_epoch is not None and kwargs.get('expected_sequence') is None:
            result['updatedEpochMs']=self.neutral_epoch
        return result


class LifecycleJoinTests(unittest.TestCase):
    def setUp(self):
        self.fixture=boundaries.LifecycleWorldTests();self.fixture.setUp();self.addCleanup(self.fixture.tearDown)
        self.root,self.native,self.session=self.fixture.root,self.fixture.native,self.fixture.session
        self.transport=XTransport(self.native,self.fixture.path);self.transport.back_path=self.root/'lifecycle-x-back-owner.json'
        self.fixture.transport=self.transport;self.session.transport=self.transport
        self.world=self.fixture.started();self.world.world_input();self.world.release()
    def join(self):
        world=self.fixture.owner()
        back=PicoLifecycleBack(self.native.sources()[0],self.session,self.transport.back_path,RUN,BINDING,lambda:self.native.alive,
            monotonic=lambda:self.native.clock,sleep=self.native.sleep,source_lock=world.lock)
        return PicoLifecycleXJoin(world,back,self.root/'lifecycle-x-join.json')
    def test_all_lifecycle_queries_share_one_lock_instance_and_busy_publishers_write_nothing(self):
        from adapters.script_journey.lock import ScriptSourceLock
        join=self.join();world=join.world
        self.assertIs(join.back.source_lock,world.lock);self.assertIs(join.back.source.source_lock,world.lock)
        readers=(world.source,world.axes,world.avatar)
        self.assertTrue(all(reader.source_lock is world.lock for reader in readers))
        before=[len(boundary.commands) for boundary in (self.native.ui,self.native.axes,self.native.drive)]
        world.lock.timeout=.01
        with ScriptSourceLock(world.lock.path,timeout=.01).held():
            for reader in readers:
                with self.assertRaises(NativeUIError):reader.capture(RUN)
        self.assertEqual(before,[len(boundary.commands) for boundary in (self.native.ui,self.native.axes,self.native.drive)])

    def test_original_consumed_world_attempt_joins_actual_x_route_without_retiring_live_context(self):
        join=self.join();result=join.back_once()
        self.assertEqual(1,result['worldAttempts']);self.assertEqual([],result['heldInputs'])
        self.assertEqual(dict(routeObserved=True,originalId='0'*31+'1',editorRetired=False,retainedContext=True),result['back'])
        self.assertEqual(1,self.transport.back_count);self.assertEqual('observed',join.state['phase'])
        self.assertTrue(join.store.path.exists());self.assertTrue(join.back.store.path.exists())
        self.assertEqual(result['back'],self.join().reconcile()['back']);self.assertEqual(1,self.transport.back_count)
    def test_lost_x_ack_restores_original_journals_and_only_reads_same_normal_input(self):
        join=self.join();self.transport.fail='ack'
        with self.assertRaises(NativeUIError):join.back_once()
        self.assertEqual('reserved',join.state['phase']);self.assertEqual(1,self.transport.back_count)
        self.transport.fail=None;result=self.join().reconcile()
        self.assertTrue(result['back']['routeObserved']);self.assertFalse(result['back']['editorRetired'])
        self.assertEqual(1,result['worldAttempts']);self.assertEqual(1,self.transport.back_count)
    def test_uncertain_x_grant_cannot_be_adopted_for_neutral_or_replayed(self):
        join=self.join();self.transport.fail='back-grant'
        with self.assertRaises(NativeUIError):join.back_once()
        self.transport.fail=None
        with self.assertRaises(NativeUIError):self.join().reconcile()
        with self.assertRaises(NativeUIError):self.join().back_once()
        self.assertEqual(1,self.transport.back_count);self.assertTrue(join.store.path.exists())
    def test_persisted_join_reservation_with_no_back_journal_never_creates_a_second_possible_press(self):
        join=self.join()
        with patch.object(join.back,'back',side_effect=NativeUIError('Explicit interruption before Back owner')),self.assertRaises(NativeUIError):join.back_once()
        with self.assertRaises(NativeUIError):self.join().reconcile()
        self.assertEqual(0,self.transport.back_count);self.assertIsNone(join.back.store.read())
    def test_replacement_create_identity_is_rejected_before_any_normal_x_press(self):
        join=self.join();from self_tests.test_pico_lifecycle_source import editor
        self.native.ui.rows[0].update(current=False,text='',focused=False,visible=False,attached=False)
        self.native.ui.rows.append(editor(2));
        with self.assertRaises(NativeUIError):join.back_once()
        self.assertEqual(0,self.transport.back_count)
    def test_pure_original_back_validator_rejects_partial_liveness_forged_as_complete_retirement(self):
        join=self.join();join.back_once();value=deepcopy(join.back.disk);state=unpack(value['payload'])[0]
        state['phase']='released';from adapters.script_journey.history import pack
        value['payload']=pack([state])
        with self.assertRaises(NativeUIError):validate_history(value,RUN,BINDING,123,self.session.profile)
    def test_join_remains_bound_to_original_history_after_a_distinct_second_world_movement(self):
        join=self.join();join.back_once();self.native.ui.shown=False;world=self.fixture.owner();current=world.world_input()
        self.assertEqual((2,['forward'],.5),(current['worldAttempts'],current['heldInputs'],current['worldDisplacement']))
        self.assertEqual('observed',self.join().state['phase']);self.assertEqual(1,self.transport.back_count)


if __name__=='__main__':unittest.main()
