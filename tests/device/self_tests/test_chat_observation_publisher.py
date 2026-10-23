"""Independent original repeated publication; native/HTTP producers are seams."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from contextlib import contextmanager
import unittest
import uuid
from unittest.mock import patch

from adapters.chat_journey.observation import ChatObservationOwner
from adapters.chat_journey.observation_cursor import ChatObservationCursor
from adapters.chat_journey.observation_publisher import ChatObservationPublisher
from adapters.chat_journey.samples import ChatCacheAbsence
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from feature_journeys.phase_fixture import PhasePending
from self_tests import test_chat_compiled_dispatcher as seams
from self_tests.test_native_chat_observation import RUN


class ChatObservationPublisherTests(unittest.TestCase):
    def setUp(self):
        self.h=seams.CompiledDispatcherTests();self.h.setUp();self.addCleanup(self.h.doCleanups)
        self.flow=self.h.h;self.flow.next(0);self.native=self.flow.h.native;self.root=self.flow.root
        self.initial_samples=self.h.samples('actor',self.flow.w.initial_witness_store,kind=ChatCacheAbsence)
        self.initial=self.observation(self.initial_samples,'initial')
        self.cursor=ChatObservationCursor(self.initial,PrivateFeatureState(self.root/'independent-cursor.json'))
        self.store=PrivateFeatureState(self.root/'independent-publisher.json');self.owner=ChatObservationPublisher(self.cursor,self.store)
        self.posts=[];self.request=self.flow.w.actor.request
        def request(path,value=None,method=None,**kwargs):
            if path.endswith('/samples'):
                original=self.store.read();self.assertEqual('reading',original['phase']);self.assertEqual('publishing',original['delivery'])
                self.posts.append(deepcopy(value));self.flow.w.journal.publish(RUN,value);return {'accepted':True}
            return self.request(path,value,method,**kwargs)
        self.flow.w.actor.request=request

    def observation(self,samples,stage):
        return ChatObservationOwner(self.flow.w.actor_source,samples,self.flow.flow.store,
            PrivateFeatureState(self.root/('independent-'+stage+'-observation.json')),stage=stage,monotonic=lambda:self.native.host)

    def queries(self):return tuple(len(getattr(self.flow.h.h,key).commands) for key in ('primary','peer','view','native'))

    def test_repeated_same_phase_publications_each_query_original_actor_sources_and_independent_receiver(self):
        before=deepcopy(self.flow.widgets.calls)
        self.assertEqual([1,2,3],[self.owner.publish() for _ in range(3)])
        self.assertEqual(before,self.flow.widgets.calls);self.assertEqual(1,len(self.flow.flow.rows))
        self.flow.next(1);samples=self.h.samples('actor',self.flow.w.witness_store)
        self.owner.select(self.observation(samples,'active'));self.assertEqual([4,5],[self.owner.publish(),self.owner.publish()])
        received=self.flow.w.journal.snapshot(RUN)['entries']
        self.assertEqual([1,2,3,4,5],[row['actorSequence'] for row in received])
        self.assertEqual([1,2,3,1,2],[row['sourceSequence'] for row in self.cursor.rows])
        self.assertEqual(3,len({tuple(row['reference']['queries']) for row in self.initial.rows}))
        self.assertEqual(1,len({row['payload']['ticket'] for row in self.owner.rows[:3]}))
        for actual,published in zip(received,self.owner.rows):
            self.assertTrue(all(actual[key]==field for key,field in published['payload'].items()))
        self.assertIsNot(self.initial.samples.script_source,self.flow.roles[0].script_source)
        self.assertTrue(all(row['facts']['open'] for row in received[3:]));self.owner.control()

    def test_input_waiting_is_read_only_before_intent_and_can_continue_only_after_actual_open(self):
        self.owner.publish();self.flow.w.journal.activate(RUN,uuid.uuid4().hex,'open',{})
        before=self.queries();previous=deepcopy(self.store.read());posts=len(self.posts)
        with self.assertRaises(PhasePending):self.owner.publish()
        self.assertEqual(before,self.queries());self.assertEqual(previous,self.store.read());self.assertEqual(posts,len(self.posts))
        self.assertFalse(self.owner.failed);self.flow.owner.step()
        with self.assertRaises(PhasePending):self.owner.publish()
        self.owner.select(self.observation(self.h.samples('actor',self.flow.w.witness_store),'active'))
        self.assertEqual(2,self.owner.publish());self.assertEqual(2,len(self.posts))

    def test_lost_post_keeps_durable_exact_pending_payload_and_freezes_queries_without_resend(self):
        request=self.flow.w.actor.request
        def lost(path,*args,**kwargs):
            value=request(path,*args,**kwargs)
            if path.endswith('/samples'):raise OSError('Original publication reply lost')
            return value
        self.flow.w.actor.request=lost
        with self.assertRaises((OSError,NativeUIError)):self.owner.publish()
        self.assertEqual('publishing',self.store.read()['delivery']);self.assertEqual(1,len(self.posts))
        self.assertEqual(self.posts[0],self.store.read()['pending']['payload']);before=self.queries()
        with self.assertRaises(NativeUIError):self.owner.publish()
        with self.assertRaises(NativeUIError):self.cursor.read()
        self.assertEqual(before,self.queries());self.assertEqual(1,len(self.flow.w.journal.snapshot(RUN)['entries']))

    def test_native_jump_after_received_post_never_qualifies_success_or_retry(self):
        request=self.flow.w.actor.request
        def late(path,*args,**kwargs):
            value=request(path,*args,**kwargs)
            if path.endswith('/samples'):self.native.epoch+=2000
            return value
        self.flow.w.actor.request=late
        with self.assertRaises(NativeUIError):self.owner.publish()
        self.assertEqual(1,len(self.posts));self.assertTrue(self.owner.failed);before=self.queries()
        with self.assertRaises(NativeUIError):self.owner.publish()
        self.assertEqual(before,self.queries());self.assertEqual(1,len(self.posts))

    def test_late_wire_copy_prevents_first_post_without_refetching_originals(self):
        from adapters.chat_journey import observation_publisher
        copied=observation_publisher.deepcopy
        def late(value):
            result=copied(value)
            if (type(value) is dict and set(value)=={'ticket','actor','actorSequence','capturedEpochMs','facts'}
                    and self.owner.base['delivery']=='publishing'):self.native.epoch+=2000
            return result
        with patch.object(observation_publisher,'deepcopy',side_effect=late),self.assertRaises(NativeUIError):self.owner.publish()
        self.assertEqual([],self.posts);self.assertTrue(self.owner.failed);self.assertEqual(1,len(self.cursor.rows))

    def test_cold_or_mutated_publication_history_cannot_adopt_fresh_actor_cursor(self):
        self.owner.publish();before=self.queries()
        with self.assertRaises(NativeUIError):ChatObservationPublisher(self.cursor,self.store)
        self.owner.rows[0]['payload']['facts']['draft']='forged'
        with self.assertRaises(NativeUIError):self.owner.publish()
        self.assertEqual(before,self.queries());self.assertEqual(1,len(self.posts));self.assertTrue(self.owner.failed)

    def test_final_root_write_and_outer_original_lock_release_remain_inside_native_age_bound(self):
        for fault in ('cas','lock-exit'):
            with self.subTest(fault=fault):
                if fault=='lock-exit':self.setUp()
                if fault=='cas':
                    write=self.store.write
                    def late(value,previous):
                        write(value,previous)
                        if value['phase']=='ready':self.native.epoch+=2000
                    self.store.write=late
                else:
                    held=self.cursor.held;depth=[0]
                    @contextmanager
                    def late_exit():
                        depth[0]+=1
                        try:
                            with held():yield
                        finally:
                            depth[0]-=1
                            if depth[0]==0:self.native.epoch+=2000
                    self.cursor.held=late_exit
                with self.assertRaises(NativeUIError):self.owner.publish()
                self.assertTrue(self.owner.failed);self.assertEqual(1,len(self.posts))
                self.assertEqual('ready',self.store.read()['phase']);before=self.queries()
                with self.assertRaises(NativeUIError):self.owner.publish()
                with self.assertRaises(NativeUIError):self.cursor.bind_freeze(lambda:True)
                self.assertEqual(before,self.queries())

    def test_actual_outer_lock_exit_failure_latches_publisher_and_freezes_original_cursor(self):
        held=self.cursor.held;depth=[0];exits=[]
        @contextmanager
        def failed_outer_exit():
            depth[0]+=1
            try:
                with held():yield
            finally:
                depth[0]-=1
                if depth[0]==0:
                    exits.append('actual outer lock released')
                    raise OSError('Original outer lock metadata release failed')
        self.cursor.held=failed_outer_exit
        with self.assertRaises(OSError):self.owner.publish()
        self.assertEqual(['actual outer lock released'],exits)
        self.assertEqual(1,len(self.posts));self.assertEqual(1,len(self.cursor.rows))
        self.assertEqual('ready',self.store.read()['phase'])
        self.assertTrue(self.owner.failed);before=self.queries()
        with self.assertRaises(NativeUIError):self.owner.publish()
        self.assertEqual(before,self.queries());self.assertEqual(1,len(self.posts))
        # The actual source locks remain available; the failed owner, rather
        # than the injected exit wrapper, must reject any new cursor query.
        self.cursor.held=held
        with self.assertRaises(NativeUIError):self.cursor.read()
        self.assertEqual(before,self.queries())


if __name__=='__main__':unittest.main()
