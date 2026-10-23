"""Source-backed global sequences; native/input/widget/clock producers are seams."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from contextlib import contextmanager
import unittest
import uuid
from unittest.mock import patch

from adapters.chat_journey.observation import ChatObservationOwner
from adapters.chat_journey.observation_cursor import ChatObservationCursor
from adapters.chat_journey.cleanup_admission import ChatCleanupAdmission
from adapters.chat_journey.cache_lifetime import ChatCacheLifetime
from adapters.chat_journey.flow_inputs import recipe
from adapters.chat_journey.phase_fence import ChatPhaseFence,bind_phase_fence
from adapters.chat_journey.samples import ChatCacheAbsence
from adapters.native_chat_observation import OwnedChatCapture
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from self_tests import test_chat_observation as seams


class ChatObservationCursorTests(unittest.TestCase):
    def setUp(self):
        self.h=seams.ChatObservationTests();self.h.setUp();self.addCleanup(self.h.doCleanups)
        self.initial=self.h.owner();self.store=PrivateFeatureState(self.h.root/'cursor.json')
        self.owner=ChatObservationCursor(self.initial,self.store)

    def active(self):
        return ChatObservationOwner(self.h.source,self.h.h.roles[0],self.h.h.flow.store,
            PrivateFeatureState(self.h.root/'active-observation.json'),stage='active',monotonic=lambda:self.h.native.host)

    def test_initial_repeated_original_queries_then_open_new_local_owner_keep_global_sequences(self):
        first=self.owner.read();self.h.h.sleep(.25);second=self.owner.read(first['sequence'])
        self.h.h.next(1);active=self.active();calls=deepcopy(self.h.h.widgets.calls)
        self.owner.select(active);third=self.owner.read(second['sequence']);fourth=self.owner.read(third['sequence'])
        self.assertEqual([1,2,3,4],[row['sequence'] for row in self.owner.rows])
        self.assertEqual([1,2,1,2],[row['sourceSequence'] for row in self.owner.rows])
        self.assertEqual([0,0,1,1],[row['stageIndex'] for row in self.owner.rows])
        self.assertEqual([1,2],[row['sample']['sequence'] for row in active.rows])
        self.assertEqual((3,4),(third['sequence'],fourth['sequence']));self.assertTrue(third['state']['open'])
        self.assertEqual(calls,self.h.h.widgets.calls);self.assertEqual(2,len(self.h.h.flow.rows))
        self.assertNotEqual(active.rows[0]['reference']['queries'],active.rows[1]['reference']['queries'])
        self.owner.control()

    def test_source_query_outside_cursor_cannot_be_adopted_as_next_global_sequence(self):
        self.owner.read();self.initial.read(1);before=self.h.queries()
        with self.assertRaises(NativeUIError):self.owner.read(1)
        self.assertEqual(before,self.h.queries());self.assertTrue(self.owner.failed)
        self.assertEqual(1,len(self.owner.rows));self.assertEqual(2,len(self.initial.rows))

    def test_actual_retired_cache_sources_continue_same_cursor_after_metadata_only_remaining_input_rows(self):
        self.owner.read();self.h.h.next(1);active=self.active();self.owner.select(active);self.owner.read(1)
        h=self.h.h
        # Only initial/Open were ordinary child inputs. The other consumed
        # flow rows are explicit metadata seams, not 24 target-effect proofs.
        for step in recipe(self.initial.source.run)[2:]:
            h.sleep(.01);h.w.journal.activate(self.initial.source.run,uuid.uuid4().hex,step['verb'],step['inputs'])
            with h.flow.session():h.flow.begin(h.flow.source.read());h.flow.finish()
        h.w.journal.activate(self.initial.source.run,uuid.uuid4().hex,'cleanup',{})
        admission=ChatCleanupAdmission(h.flow,PrivateFeatureState(self.h.root/'cleanup-admission.json'))
        with h.flow.session():admission.admit()
        h.widgets.panel=False;h.widgets.tablet=False;h.widgets.focus=False;h.widgets.keyboard_request=False;h.sync()
        fence=ChatPhaseFence(h.flow,cleanup=admission)
        with h.flow.session():
            for old,boundary in zip(h.owner.caches,(h.h.h.primary,h.h.h.peer)):
                reader=boundary.reader();reader.pid=old.reader.pid
                reader.clock_ms=lambda:self.h.native.epoch;reader.monotonic=lambda:self.h.native.host;reader.sleep=h.sleep
                cache=ChatCacheLifetime(OwnedChatCapture(reader,old.capture.owner,self.initial.source.run),old.store,old.lock,
                    monotonic=lambda:self.h.native.host)
                bind_phase_fence(cache,fence);cache.retire()
        samples=self.h.c.samples('primary',PrivateFeatureState(self.h.root/'cleanup-samples.json'),
            kind=ChatCacheAbsence,script_source=active.samples.script_source)
        cleanup=ChatObservationOwner(self.h.source,samples,h.flow.store,PrivateFeatureState(self.h.root/'cleanup-observation.json'),
            stage='cleanup',cleanup_store=admission.store,monotonic=lambda:self.h.native.host)
        self.owner.select(cleanup);value=self.owner.read(2)
        self.assertEqual(3,value['sequence']);self.assertEqual(1,cleanup.rows[-1]['sequence'])
        self.assertEqual('cleanup',self.owner.current.stage);self.assertEqual([],value['resources'])
        self.assertFalse(value['state']['open']);self.owner.control()

    def test_cold_root_rootless_chunks_and_future_cursor_never_query_or_adopt(self):
        self.owner.read();before=self.h.queries()
        with self.assertRaises(NativeUIError):self.owner.read(2)
        with self.assertRaises(NativeUIError):ChatObservationCursor(self.initial,self.store)
        self.store.path.unlink()
        # A new original stage owner cannot cover up the cursor's old chunks.
        new=ChatObservationOwner(self.h.source,self.initial.samples,self.initial.flow_store,
            PrivateFeatureState(self.h.root/'another-initial.json'),stage='initial',monotonic=lambda:self.h.native.host)
        with self.assertRaises(NativeUIError):ChatObservationCursor(new,self.store)
        self.assertEqual(before,self.h.queries());self.assertTrue(self.owner.history.store(0).path.exists())

    def test_lost_global_ready_cas_never_requeries_an_uncertain_source(self):
        write=self.store.write
        def lost(value,previous):
            write(value,previous)
            if value['phase']=='ready':raise OSError('global cursor receipt lost')
        self.store.write=lost
        with self.assertRaises((OSError,NativeUIError)):self.owner.read()
        before=self.h.queries();self.assertEqual(1,len(self.initial.rows));self.assertTrue(self.owner.failed)
        with self.assertRaises(NativeUIError):self.owner.read()
        self.assertEqual(before,self.h.queries());self.assertTrue(self.owner.history.store(0).path.exists())

    def test_frozen_host_native_jump_after_final_copy_cannot_return_global_sample(self):
        from adapters.chat_journey import observation_cursor
        copied=observation_cursor.deepcopy
        def late(value):
            result=copied(value)
            if type(value) is dict and value.get('schemaVersion')==1 and 'state' in value:self.h.native.epoch+=2000
            return result
        with patch.object(observation_cursor,'deepcopy',side_effect=late),self.assertRaises(NativeUIError):self.owner.read()
        self.assertTrue(self.owner.failed);self.assertIsNotNone(self.store.read())

    def test_final_validator_and_original_lock_exit_cost_remain_inside_native_age_fence(self):
        from adapters.chat_journey import observation_cursor
        for fault in ('validator','lock-exit'):
            with self.subTest(fault=fault):
                if fault=='lock-exit':self.setUp()
                original_result=observation_cursor.result
                def late_result(*args):
                    value=original_result(*args);self.h.native.epoch+=2000;return value
                original_held=self.owner.held
                @contextmanager
                def late_exit():
                    with original_held():yield
                    self.h.native.epoch+=2000
                if fault=='validator':
                    with patch.object(observation_cursor,'result',side_effect=late_result),self.assertRaises(NativeUIError):self.owner.read()
                else:
                    self.owner.held=late_exit
                    with self.assertRaises(NativeUIError):self.owner.read()
                self.assertTrue(self.owner.failed);self.assertIsNotNone(self.store.read())

    def test_inspection_copies_cannot_mutate_original_source_or_global_rows(self):
        self.owner.read();before=self.h.queries()
        self.initial.rows[0]['sample']['state']['draft']='invented'
        copied=self.owner.rows;copied[0]['sample']['resources']=tuple(copied[0]['sample']['resources'])
        self.owner.control();value=self.owner.read(1)
        self.assertEqual(2,value['sequence']);self.assertNotEqual(before,self.h.queries())
        self.assertNotEqual('invented',self.initial.row(0)['sample']['state']['draft'])
        self.assertEqual(self.initial.row_digest(0),self.owner.row(0)['observationSha256'])
        self.assertEqual(self.owner.row_digest(0),self.owner.hashes[0])

    def test_old_internal_source_bytes_and_tuple_hash_alias_cannot_keep_cursor_green(self):
        for fault in ('source','tuple'):
            with self.subTest(fault=fault):
                if fault=='tuple':self.setUp()
                self.owner.read();before=self.h.queries()
                if fault=='source':
                    memory=self.initial.originals;memory.raws=memory._raws=(memory.raws[0]+b' ',)
                else:self.owner.hashes=tuple(self.owner.hashes)
                with self.assertRaises(NativeUIError):self.owner.read(1)
                self.assertEqual(before,self.h.queries());self.assertTrue(self.owner.failed)

    def test_internal_original_change_after_final_cas_keeps_new_row_unqualified(self):
        self.owner.read();write=self.store.write
        def changed(value,previous):
            write(value,previous)
            if value['phase']=='ready':
                memory=self.owner.originals;memory.raws=memory._raws=(memory.raws[0]+b' ',)
        self.store.write=changed
        with self.assertRaises(NativeUIError):self.owner.read(1)
        self.assertTrue(self.owner.failed);before=self.h.queries()
        with self.assertRaises(NativeUIError):self.owner.read(1)
        self.assertEqual(before,self.h.queries());self.assertIsNotNone(self.store.read())


if __name__=='__main__':unittest.main()
