"""Original callback/readiness counterexamples; no product/native execution."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'tests/device'))

from self_tests import test_script_journey_measurements as fixtures
from adapters.script_journey.causality import check,ready,wait,ScriptReadinessPending
from self_tests.test_native_script_loads import history,event
from self_tests.test_native_script_membership import membership_source,manager
from adapters.normal_ui import NativeUIError
from feature_journeys.scenarios import VERSION


class ScriptCausalityTests(unittest.TestCase):
    def setUp(self):
        self.f=fixtures.ScriptMeasurementTests('test_live_reader_reacquires_all_original_sources_and_preserves_original_lifecycle')
        self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.before=deepcopy(self.f.execution)
        self.before['source']['engines']=[];self.before['source']['effects']['entities']=[]
        history(self.before,[]);membership_source(self.before,[],0)
        self.current=deepcopy(self.f.execution)
        self.current.update(requestId='9'*32,sequence=self.before['sequence']+1)
        self.call=dict(contractVersion=VERSION,runId=fixtures.RUN,fixtureUrl=fixtures.FIXTURE,ticket=fixtures.TICKET,
                       verb='picker-accept',inputs={'resource':'script.js'})
        membership_source(self.current,[manager(url=self.f.directory+'/script.js',epoch=20000)],1)
        history(self.current,[event(url=self.f.directory+'/script.js',success=True,status='Success',loadGeneration=1,callbackEpochMs=20000)])

    def ready(self):return ready(self.call,self.before,self.current,self.f.directory,20000)

    def test_actual_new_callback_code_companion_and_effect_are_required_together(self):
        actual=self.ready();self.assertTrue(actual['success']);self.assertEqual(20000,actual['callbackEpochMs'])
        self.current['source']['engines']=[];self.current['source']['effects']['entities']=[]
        membership_source(self.current,[],2)
        with self.assertRaises(ScriptReadinessPending):self.ready()

    def test_absent_or_ignored_load_callback_cannot_be_inferred_from_an_engine(self):
        history(self.current,[])
        with self.assertRaises(ScriptReadinessPending):self.ready()

    def test_foreign_cached_or_old_callbacks_cannot_be_relabelled_as_current_import(self):
        for changes in (dict(url='file:///foreign/main.js'),dict(url=self.f.directory+'/script-bundle/main.js'),
                        dict(callbackEpochMs=19999),dict(success=False,status='NotFound')):
            current=deepcopy(self.current)
            history(current,[event(url=self.f.directory+'/script.js',success=True,status='Success',callbackEpochMs=20000)|changes])
            with self.subTest(changes=changes),self.assertRaises((ValueError,RuntimeError)):
                ready(self.call,self.before,current,self.f.directory,20000)

    def test_cancel_detects_even_transient_owned_load_that_is_no_longer_running(self):
        call=self.call|dict(verb='picker-cancel',inputs={})
        self.current['source']['engines']=[];self.current['source']['effects']['entities']=[]
        membership_source(self.current,[],2)
        with self.assertRaises(NativeUIError):check(call,self.before,self.current,self.f.directory,20000)
        history(self.current,[])
        self.assertIsNone(check(call,self.before,self.current,self.f.directory,20000))

    def test_wrong_submitted_code_cannot_qualify_a_successful_file_fetch(self):
        self.current['source']['engines'][0]['code']['sha256']='f'*64
        with self.assertRaises(NativeUIError):self.ready()

    def test_success_for_the_same_url_from_another_manager_or_load_generation_is_not_this_import(self):
        for changes in (dict(managerInstance='f'*32),dict(loadGeneration=2)):
            current=deepcopy(self.current);current['source']['loads']['events'][0].update(changes)
            with self.subTest(changes=changes),self.assertRaises(NativeUIError):
                ready(self.call,self.before,current,self.f.directory,20000)

    def test_pending_assigned_manager_cannot_qualify_an_empty_running_hash(self):
        self.current['source']['engines']=[];self.current['source']['effects']['entities']=[]
        membership_source(self.current,[manager(url=self.f.directory+'/script.js')],1)
        with self.assertRaises(ScriptReadinessPending):self.ready()

    def test_uninitialized_or_zero_tick_effect_does_not_qualify_readiness(self):
        from self_tests.test_native_script_observation import effect_source
        for tick in (None,0):
            current=deepcopy(self.current)
            if tick is None:current['source']['effects']['entities'][0]['userData']=''
            else:effect_source(current,ticks=tick)
            with self.subTest(tick=tick),self.assertRaises(ScriptReadinessPending):
                ready(self.call,self.before,current,self.f.directory,20000)

    def test_missing_url_uses_original_not_found_status_and_complete_absence(self):
        self.current['source']['engines']=[];self.current['source']['effects']['entities']=[]
        membership_source(self.current,[],2)
        call=self.call|dict(verb='load-url',inputs={'resource':'missing.js'})
        history(self.current,[event(url=fixtures.MISSING,callbackEpochMs=20000)])
        self.assertEqual('NotFound',ready(call,self.before,self.current,self.f.directory,20000)['status'])
        self.current['source']['loads']['events'][0]['status']='ConnectionRefused'
        with self.assertRaises(NativeUIError):ready(call,self.before,self.current,self.f.directory,20000)

    def test_original_birth_sequence_nonce_or_history_replay_is_rejected(self):
        for changes in (dict(instance='f'*32),dict(sequence=self.before['sequence']),
                        dict(requestId=self.before['requestId'])):
            with self.subTest(changes=changes),self.assertRaises(NativeUIError):
                ready(self.call,self.before,self.current|changes,self.f.directory,20000)

    def polling(self, *, settle=2):
        source=self.f.execution_source; count=[0]
        original=source.mutate
        def mutate(packet):
            original(packet);count[0]+=1
            history(packet,[] if count[0]<settle else [event(url=self.f.directory+'/script.js',
                success=True,status='Success',loadGeneration=1,callbackEpochMs=20000)])
            membership_source(packet,[manager(url=self.f.directory+'/script.js',epoch=20000)],1)
        source.mutate=mutate
        return source.reader(),count

    def test_wait_reacquires_originals_records_pending_and_final_frames_and_never_replays_input(self):
        reader,count=self.polling();frames=[];sleeps=[];clock=[0.0]
        def sleep(value):sleeps.append(value);clock[0]+=value
        result=wait(self.call,self.before,self.f.directory,reader,
            monotonic=lambda:clock[0],sleep=sleep,record=frames.append)
        self.assertEqual(2,count[0]);self.assertEqual([.25],sleeps)
        self.assertEqual([],frames[0]['source']['loads']['events'])
        self.assertEqual(result,frames[-1]);self.assertEqual(2,len(frames))
        self.assertTrue(all(row['action']=='feature-script-observe' for row in self.f.execution_source.commands))

    def test_wait_exhaustion_or_whole_deadline_never_returns_an_ack_as_readiness(self):
        for late in (False,True):
            with self.subTest(late=late):
                reader,count=self.polling(settle=1000);clock=[0.0]
                def sleep(value):clock[0]+=21 if late else value
                with self.assertRaises(NativeUIError):
                    wait(self.call,self.before,self.f.directory,reader,monotonic=lambda:clock[0],sleep=sleep)
                self.assertEqual(2 if late else 64,count[0])

    def test_wait_record_failure_or_lost_guard_stops_before_another_request(self):
        reader,count=self.polling()
        def fail(_packet):raise OSError('synthetic journal failure')
        with self.assertRaises(OSError):wait(self.call,self.before,self.f.directory,reader,record=fail)
        self.assertEqual(1,count[0])
        reader.guard=lambda:False
        with self.assertRaises(NativeUIError):wait(self.call,self.before,self.f.directory,reader)
        self.assertEqual(1,count[0])

    def test_wait_does_not_retry_a_foreign_callback_or_regressing_monotonic_clock(self):
        reader,count=self.polling(settle=1)
        before=deepcopy(self.before);before['instance']='f'*32
        with self.assertRaises(NativeUIError):wait(self.call,before,self.f.directory,reader)
        self.assertEqual(1,count[0])
        values=iter([2.0,1.0])
        with self.assertRaises(NativeUIError):
            wait(self.call,self.before,self.f.directory,reader,monotonic=lambda:next(values))


if __name__=='__main__':unittest.main()
