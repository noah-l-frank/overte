"""Actual global prefix/cleanup source join; no full external journey/device claim."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest

from adapters.chat_journey.cursor_cleanup_consumption import ChatCleanupFinalizationSlot,ChatCursorCleanupConsumption
from adapters.chat_journey.cursor_source_seal import ChatCursorSourceSeal
from adapters.chat_journey.observation import ChatObservationOwner
from adapters.chat_journey.observation_cursor import ChatObservationCursor
from adapters.chat_journey.samples import ChatCacheAbsence
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from feature_journeys.engine import Journey
from feature_journeys.fixtures import context
from feature_journeys.scenarios import SCENARIOS,expand
from feature_journeys.witness import projection
from self_tests import test_chat_observation_publisher as seams
from self_tests.chat_cursor_fixture import cleanup


class ChatCursorCleanupConsumptionTests(unittest.TestCase):
    def setUp(self):
        self.h=seams.ChatObservationPublisherTests();self.h.setUp();self.addCleanup(self.h.doCleanups)
        self.actor=self.h.owner;compiled=self.h.h;flow=self.h.flow;self.run=self.actor.scope['runId']
        initial=ChatObservationOwner(flow.w.parent_source,flow.flow.initial_roles[0],flow.flow.store,
            PrivateFeatureState(self.h.root/'global-primary-initial-observation.json'),stage='initial',monotonic=lambda:self.h.native.host)
        self.primary=ChatObservationCursor(initial,PrivateFeatureState(self.h.root/'global-primary-cursor.json'))
        self.slot=ChatCleanupFinalizationSlot();self.consumer=None
        def no_input(*_args,**_kwargs):raise AssertionError('No new input is authorized by this source join')
        def invoke(operation,fields):
            self.assertEqual('feature.chat.observe',operation)
            # Explicit actor-loop scheduling seam: separate original source
            # owner/credential/journal, in this one hardware-free host fixture.
            self.actor.publish()
            return self.consumer.observe(fields) if self.consumer is not None else self.primary.read(fields['afterSequence'])
        request=self.h.flow.w.actor.request
        def received(path,*args,**kwargs):
            return self.h.flow.w.journal.snapshot(self.run) if path=='/runs/'+self.run else request(path,*args,**kwargs)
        self.h.flow.w.actor.request=received
        self.journey=Journey('chat',self.run,initial.source.fixture_url,invoke=invoke,
            witness=lambda:received('/runs/'+self.run),activate=no_input,read_artifact=no_input,image_policy={},
            continuity=lambda *_args:None,monotonic=lambda:self.h.native.host,epoch_ms=lambda:self.h.native.epoch,
            sleep=flow.sleep,report=no_input,after_cleanup_baseline=self.slot.callback)
        self.slot.attach(self.journey)
        # These original observe/witness calls establish both actual cursors;
        # neither sequence is assigned from a private fixture phase count.
        self.prefix(SCENARIOS['chat']['baseline'])
        flow.next(1)
        self.actor.select(self.h.observation(compiled.samples('actor',flow.w.witness_store),'active'))
        active=ChatObservationOwner(initial.source,flow.roles[0],flow.flow.store,
            PrivateFeatureState(self.h.root/'global-primary-active-observation.json'),stage='active',monotonic=lambda:self.h.native.host)
        self.primary.select(active);self.prefix(SCENARIOS['chat']['steps'][0]['state'])
        # Actual retirement; the remaining 24 consumed input rows are metadata
        # seams and do not prove those target effects or external execute().
        primary_cleanup=cleanup(compiled,self.primary)
        actor_samples=compiled.samples('actor',PrivateFeatureState(self.h.root/'global-actor-cleanup-samples.json'),
            kind=ChatCacheAbsence,script_source=self.actor.observation.samples.script_source)
        actor_cleanup=ChatObservationOwner(self.actor.observation.source,actor_samples,flow.flow.store,
            PrivateFeatureState(self.h.root/'global-actor-cleanup-observation.json'),stage='cleanup',
            cleanup_store=primary_cleanup.cleanup_store,monotonic=lambda:self.h.native.host)
        self.primary.select(primary_cleanup);self.actor.select(actor_cleanup)
        self.seals=(ChatCursorSourceSeal(self.primary,PrivateFeatureState(self.h.root/'global-primary-seal.json')),
            ChatCursorSourceSeal(self.actor,PrivateFeatureState(self.h.root/'global-actor-seal.json')))
        self.store=PrivateFeatureState(self.h.root/'global-cleanup-consumption.json')
        self.consumer=ChatCursorCleanupConsumption(self.primary,self.actor,self.seals,self.store,guard=lambda:True)
        self.ticket=flow.w.journal.snapshot(self.run)['ticket'];self.barrier=self.h.native.epoch

    def prefix(self,expected):
        journal=self.h.flow.w.journal.snapshot(self.run);ticket=journal['ticket'];barrier=self.h.native.epoch
        value=self.journey.observe(ticket,barrier)
        okay,_original=self.journey.observed_witness(ticket,barrier,projection('chat',expand(expected,context(self.run))))
        self.assertTrue(okay);self.assertEqual(value['sequence'],self.journey.sequence)

    def wait(self):
        self.slot.bind(self.consumer)
        self.journey.wait('cleanup-restored-baseline',self.ticket,self.barrier,
            deepcopy(SCENARIOS['chat']['baseline']),['peer'],duration=3)

    def test_actual_global_cursors_consume_original_cleanup_without_local_rebase_or_duplicate_wait(self):
        self.wait();before=self.h.queries();posts=len(self.h.posts)
        self.journey.consumed_cleanup(self.ticket,self.barrier,0)
        self.assertTrue(self.slot.completed);self.assertTrue(self.consumer.completed)
        value=self.consumer.receipt();header=value['externalConsumption']['header']
        self.assertFalse(header['sequenceSucceeded']);self.assertGreater(header['finalSequence'],self.consumer.primary_start)
        samples=[row for row in self.consumer.rows if row['kind']=='sample']
        self.assertEqual(3,samples[0]['common']['sequence']);self.assertEqual(1,self.primary.current.rows[0]['sequence'])
        self.assertEqual(2,value['primaryStart']);self.assertEqual(2,value['actorStart'])
        self.assertEqual(1,len([row for row in self.consumer.rows if row['kind']=='receiver']))
        self.assertTrue(all(seal.completed for seal in self.seals))
        self.assertEqual(before,self.h.queries());self.assertEqual(posts,len(self.h.posts))
        with self.assertRaises(NativeUIError):self.slot.consume(self.journey.cleanup_consumption)
        with self.assertRaises(NativeUIError):self.primary.read()
        with self.assertRaises(NativeUIError):self.actor.publish()
        self.assertEqual(before,self.h.queries());self.assertEqual(posts,len(self.h.posts))

    def test_frozen_native_jump_after_final_consumption_cas_cannot_qualify_global_receipt(self):
        self.wait();write=self.store.write;before=self.h.queries();posts=len(self.h.posts)
        def late(value,previous):
            write(value,previous)
            if value['stage']=='complete':self.h.native.epoch+=2000
        self.store.write=late
        with self.assertRaises(NativeUIError):self.journey.consumed_cleanup(self.ticket,self.barrier,0)
        self.assertTrue(self.slot.failed);self.assertFalse(self.slot.completed)
        self.assertTrue(self.consumer.failed);self.assertFalse(self.consumer.completed)
        self.assertTrue(all(seal.failed for seal in self.seals));self.assertEqual('complete',self.store.read()['stage'])
        with self.assertRaises(NativeUIError):self.consumer.receipt()
        self.assertEqual(before,self.h.queries());self.assertEqual(posts,len(self.h.posts))

    def test_original_slot_rejects_unconsumed_engine_cursor_instead_of_inventing_an_offset(self):
        self.journey.sequence-=1 # Explicit caller-cursor corruption countercase.
        before=self.h.queries();posts=len(self.h.posts)
        with self.assertRaises(NativeUIError):self.slot.bind(self.consumer)
        self.assertTrue(self.slot.failed);self.assertTrue(self.consumer.failed);self.assertIsNone(self.store.read())
        with self.assertRaises(NativeUIError):self.primary.read()
        self.assertEqual(before,self.h.queries());self.assertEqual(posts,len(self.h.posts))

    def test_foreign_received_journal_cannot_qualify_actual_common_consumption_or_start_graph_seals(self):
        self.wait();request=self.h.flow.w.actor.request;before=self.h.queries();posts=len(self.h.posts)
        def foreign(path,*args,**kwargs):
            value=request(path,*args,**kwargs)
            if path=='/runs/'+self.run:value['runId']='f'*32
            return value
        self.h.flow.w.actor.request=foreign
        with self.assertRaises(NativeUIError):self.journey.consumed_cleanup(self.ticket,self.barrier,0)
        self.assertTrue(self.slot.failed);self.assertTrue(self.consumer.failed)
        self.assertTrue(all(seal.failed and not seal.completed and seal.store.read() is None for seal in self.seals))
        self.assertEqual('external-observing',self.store.read()['stage'])
        self.assertEqual(before,self.h.queries());self.assertEqual(posts,len(self.h.posts))


if __name__=='__main__':unittest.main()
