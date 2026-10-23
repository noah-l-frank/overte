"""Original cleanup publisher/common wait on explicit native/input-metadata seams.

Only baseline/first Open use ordinary controls. Remaining consumed input rows
are metadata fixtures: these tests do not qualify all 25 target effects.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
import uuid
from unittest.mock import patch

from adapters.chat_journey.cleanup_admission import ChatCleanupAdmission
from adapters.chat_journey.cache_lifetime import ChatCacheLifetime
from adapters.chat_journey.cleanup_witness import ChatCleanupWitness
from adapters.chat_journey.flow_inputs import recipe
from adapters.chat_journey.observation import ChatObservationOwner
from adapters.chat_journey.phase_fence import ChatPhaseFence,bind_phase_fence
from adapters.chat_journey.samples import ChatCacheAbsence
from adapters.chat_journey.witness import ChatWitness
from adapters.normal_feature_state import PrivateFeatureState
from adapters.native_chat_observation import OwnedChatCapture
from adapters.normal_ui import NativeUIError
from feature_journeys.engine import Journey
from feature_journeys.phase_fixture import PhaseFixtureReader
from feature_journeys.scenarios import SCENARIOS
from self_tests import test_chat_compiled_dispatcher as compiled_seams
from self_tests.test_native_chat_observation import RUN


class ChatCleanupWitnessTests(unittest.TestCase):
    def setUp(self):
        self.c=compiled_seams.CompiledDispatcherTests();self.c.setUp();self.addCleanup(self.c.doCleanups)
        self.h=self.c.h;self.root=self.h.root;self.native=self.h.h.native
        samples=self.c.samples('actor',self.h.w.witness_store)
        initial=self.c.samples('actor',self.h.w.initial_witness_store,kind=ChatCacheAbsence)
        self.original=ChatWitness(self.h.w.actor_source,samples,self.h.flow.store,self.h.w.publisher_store,
            initial_samples=initial,monotonic=lambda:self.native.host)
        self.h.next(0);self.original.publish();self.h.next(1);self.original.publish()
        for step in recipe(RUN)[2:]:
            self.h.sleep(.01);self.h.w.journal.activate(RUN,uuid.uuid4().hex,step['verb'],step['inputs'])
            with self.h.flow.session():self.h.flow.begin(self.h.flow.source.read());self.h.flow.finish()
            self.original.publish()
        self.ticket=uuid.uuid4().hex;self.h.w.journal.activate(RUN,self.ticket,'cleanup',{})
        self.admission=ChatCleanupAdmission(self.h.flow,PrivateFeatureState(self.root/'cleanup-admission.json'))
        with self.h.flow.session():self.admission.admit()
        self.h.widgets.panel=False;self.h.widgets.tablet=False;self.h.widgets.focus=False;self.h.widgets.keyboard_request=False
        self.h.sync()
        # Reconstruct only fully acknowledged cache lifetimes, as the actual
        # release owner does; the consumed input fence cannot admit cleanup.
        fence=ChatPhaseFence(self.h.flow,cleanup=self.admission)
        with self.h.flow.session():
            for old,boundary in zip(self.h.owner.caches,(self.h.h.h.primary,self.h.h.h.peer)):
                reader=boundary.reader();reader.pid=old.reader.pid
                reader.clock_ms=lambda:self.native.epoch;reader.monotonic=lambda:self.native.host;reader.sleep=self.h.sleep
                cache=ChatCacheLifetime(OwnedChatCapture(reader,old.capture.owner,RUN),old.store,old.lock,
                    monotonic=lambda:self.native.host)
                bind_phase_fence(cache,fence);cache.retire()
        self.observers={}
        for role,client,key in (('primary',self.h.w.primary,'primary'),('actor',self.h.w.actor,'witness')):
            store=PrivateFeatureState(self.root/(key+'-cleanup-samples.json'))
            code=self.c.sources[key]
            samples=self.c.samples(role,store,kind=ChatCacheAbsence,script_source=code)
            source=PhaseFixtureReader(client,RUN,'chat',epoch_ms=lambda:self.native.epoch,monotonic=lambda:self.native.host)
            self.observers[role]=ChatObservationOwner(source,samples,self.h.flow.store,
                PrivateFeatureState(self.root/(key+'-observations.json')),stage='cleanup',cleanup_store=self.admission.store,
                monotonic=lambda:self.native.host)
        self.store=PrivateFeatureState(self.root/'cleanup-publisher.json')
        self.publisher=ChatCleanupWitness(self.original,self.observers['actor'],self.store)
        self.posts=[];previous=self.h.w.actor.request
        def request(path,value=None,method=None,**kwargs):
            if path.endswith('/samples'):
                state=self.store.read();self.assertEqual('reading',state['phase']);self.assertEqual('publishing',state['delivery'])
                self.posts.append(deepcopy(value));self.h.w.journal.publish(RUN,value)
                return {'accepted':True}
            return previous(path,value,method,**kwargs)
        self.h.w.actor.request=request

    def queries(self):
        return tuple(len(getattr(self.h.h.h,key).commands) for key in ('primary','peer','view','native'))

    def refused_again(self):
        before=self.queries();original=deepcopy(self.store.read());count=len(self.posts)
        with self.assertRaises(NativeUIError):self.publisher.publish()
        with self.assertRaises(NativeUIError):ChatCleanupWitness(self.original,self.observers['actor'],self.store)
        self.assertEqual(before,self.queries());self.assertEqual(count,len(self.posts));self.assertEqual(original,self.store.read())

    def test_lost_post_receipt_keeps_exact_publishing_intent_without_warm_or_cold_resend(self):
        request=self.h.w.actor.request
        def lost(path,*args,**kwargs):
            result=request(path,*args,**kwargs)
            if path.endswith('/samples'):raise OSError('Original POST response lost')
            return result
        self.h.w.actor.request=lost
        with self.assertRaises(NativeUIError):self.publisher.publish()
        self.assertEqual(1,len(self.posts));self.assertEqual('publishing',self.store.read()['delivery'])
        self.assertEqual(27,self.h.w.journal.snapshot(RUN)['entries'][-1]['actorSequence'])
        self.refused_again()

    def test_phase_retirement_after_publishing_cas_prevents_any_post_and_retains_original(self):
        write=self.store.write
        def retired(value,previous):
            write(value,previous)
            if value['delivery']=='publishing':self.h.w.journal.close(RUN)
        self.store.write=retired
        with self.assertRaises(NativeUIError):self.publisher.publish()
        self.assertEqual([],self.posts);self.assertEqual('publishing',self.store.read()['delivery']);self.refused_again()

    def test_frozen_host_native_jump_after_publishing_cas_prevents_post(self):
        clock=self.native.host;write=self.store.write
        def late(value,previous):
            write(value,previous)
            if value['delivery']=='publishing':self.native.epoch+=2000
        self.store.write=late
        with self.assertRaises(NativeUIError):self.publisher.publish()
        self.assertEqual(clock,self.native.host);self.assertEqual([],self.posts);self.refused_again()

    def test_late_successful_post_never_reports_fresh_publication(self):
        # The final post path also checks the original native clock; a received
        # late transport result cannot authorize another publisher attempt.
        clock=self.native.host;request=self.h.w.actor.request
        def late(path,*args,**kwargs):
            result=request(path,*args,**kwargs)
            if path.endswith('/samples'):self.native.epoch+=2000
            return result
        self.h.w.actor.request=late
        with self.assertRaises(NativeUIError):self.publisher.publish()
        self.assertEqual(clock,self.native.host);self.assertEqual(1,len(self.posts));self.assertTrue(self.publisher.failed)
        self.refused_again()

    def test_frozen_host_native_jump_during_last_wire_copy_prevents_post(self):
        clock=self.native.host
        def late(value):
            result=deepcopy(value)
            if (type(value) is dict and set(value)=={'ticket','actor','actorSequence','capturedEpochMs','facts'}
                    and self.publisher.base['delivery']=='publishing'):self.native.epoch+=2000
            return result
        with patch('adapters.chat_journey.cleanup_witness.deepcopy',side_effect=late):
            with self.assertRaises(NativeUIError):self.publisher.publish()
        self.assertEqual(clock,self.native.host);self.assertEqual([],self.posts);self.refused_again()

    def test_mutated_active_original_never_becomes_new_cache_retirement_evidence(self):
        self.publisher.active_original['peer']['source']['retiredCommandId']='f'*32
        with self.assertRaises(NativeUIError):self.publisher.publish()
        self.assertEqual([],self.posts);self.assertEqual('acquiring',self.store.read()['delivery']);self.refused_again()

    def test_actual_common_three_second_cleanup_baseline_uses_new_primary_and_independent_actor_queries(self):
        primary=self.observers['primary'];before=deepcopy(self.h.widgets.calls)
        def invoke(operation,call):
            self.assertEqual('feature.chat.observe',operation);self.publisher.publish();return primary.read(call['afterSequence'])
        journey=Journey('chat',RUN,self.h.w.parent_source.fixture_url,invoke=invoke,
            witness=lambda:self.h.w.journal.snapshot(RUN),activate=lambda *_args:None,
            read_artifact=lambda _name:self.fail('Chat private projection has no image evidence'),image_policy={},
            continuity=lambda *_args:None,monotonic=lambda:self.native.host,epoch_ms=lambda:self.native.epoch,
            sleep=self.h.sleep,report=lambda _value:None)
        journey.wait('cleanup-restored-baseline',self.ticket,self.native.epoch,deepcopy(SCENARIOS['chat']['baseline']),['peer'],duration=3.0)
        self.assertGreaterEqual(len(journey.samples),13);self.assertEqual(before,self.h.widgets.calls)
        self.assertGreaterEqual(primary.rows[-1]['sample']['capturedEpochMs']-primary.rows[0]['sample']['capturedEpochMs'],3000)
        self.assertEqual(list(range(27,27+len(self.posts))),[row['actorSequence'] for row in self.posts])
        self.assertTrue(all(sample['resources']==[] and sample['witness']['ticket']==self.ticket for sample in journey.samples))
        self.assertTrue(all(row['payload']['ticket']==self.ticket for row in self.publisher.rows))
        self.assertEqual(26,len(self.original.rows));self.assertEqual('ready',self.store.read()['phase'])


if __name__=='__main__':unittest.main()
