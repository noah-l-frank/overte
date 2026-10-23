"""Actual private phase/source/CAS projection; native/V8/widget producers are seams."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
import uuid
from unittest.mock import patch

from adapters.chat_journey.observation import ChatObservationOwner
from adapters.chat_journey.compiled_samples import CompiledChatCacheAbsence
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from feature_journeys.phase_fixture import PhaseFixtureReader
from self_tests import test_chat_compiled_dispatcher as compiled_seams
from self_tests.test_native_chat_observation import RUN


class ChatObservationTests(unittest.TestCase):
    def setUp(self):
        self.c=compiled_seams.CompiledDispatcherTests();self.c.setUp();self.addCleanup(self.c.doCleanups)
        self.h=self.c.h;self.h.next(0);self.root=self.h.root;self.native=self.h.h.native
        self.store=PrivateFeatureState(self.root/'observation.json')
        original=self.h.w.parent_source
        self.source=PhaseFixtureReader(original.client,RUN,'chat',epoch_ms=original.epoch_ms,monotonic=original.monotonic)

    def owner(self,stage='initial',samples=None):
        selected=samples or (self.h.roles[0] if stage=='active' else self.h.flow.initial_roles[0])
        return ChatObservationOwner(self.source,selected,self.h.flow.store,self.store,stage=stage,monotonic=lambda:self.native.host)

    def queries(self):return tuple(len(getattr(self.h.h.h,key).commands) for key in ('primary','peer','view','native'))

    def test_repeated_same_phase_acquires_new_original_transactions_and_projects_only_actual_sources(self):
        owner=self.owner();first=owner.read();self.h.sleep(.25);second=owner.read(first['sequence'])
        self.assertEqual((1,2),(first['sequence'],second['sequence']));self.assertEqual(first['state'],second['state'])
        self.assertEqual([],second['resources']);self.assertEqual([],second['artifacts'])
        a,b=owner.rows;self.assertEqual(a['before']['activations'],b['before']['activations'])
        self.assertNotEqual(a['reference']['queries'],b['reference']['queries'])
        self.assertNotEqual(a['reference']['sourceSha256'],b['reference']['sourceSha256'])
        samples=owner.samples;self.assertNotEqual(samples.frames[-2]['compiledChat']['ticket'],samples.frames[-1]['compiledChat']['ticket'])
        self.assertEqual(owner.sample(2,samples.frames[-1]),second);self.assertEqual('ready',self.store.read()['phase'])
        self.assertEqual([],self.h.widgets.calls);self.assertEqual(1,len(self.h.flow.rows))

    def test_active_observation_uses_actual_open_view_without_creating_another_input(self):
        self.h.next(1);owner=self.owner('active');calls=deepcopy(self.h.widgets.calls)
        value=owner.read();self.assertTrue(value['state']['open']);self.assertEqual('local',value['state']['channel'])
        self.assertEqual(calls,self.h.widgets.calls);self.assertIn('panel:chat',value['resources'])

    def test_cold_ready_or_lost_reading_roots_never_adopt_ownership_or_issue_source_queries(self):
        owner=self.owner();owner.read();before=self.queries()
        with self.assertRaises(NativeUIError):self.owner()
        self.assertEqual(before,self.queries())
        self.store.path.unlink() # Explicit root-loss fault leaves original chunks.
        with self.assertRaises(NativeUIError):self.owner()
        self.assertEqual(before,self.queries())
        self.setUp();owner=self.owner();write=self.store.write
        def lost(value,previous):write(value,previous);raise OSError('Original observation reading receipt lost')
        self.store.write=lost
        with self.assertRaises((OSError,NativeUIError)):owner.read()
        self.assertEqual('reading',self.store.read()['phase']);before=self.queries()
        with self.assertRaises(NativeUIError):owner.read()
        with self.assertRaises(NativeUIError):self.owner()
        self.assertEqual(before,self.queries())

    def test_changed_final_phase_keeps_historical_row_and_never_relabels_or_requeries_it(self):
        owner=self.owner();write=self.store.write
        def changed(value,previous):
            write(value,previous)
            if value['phase']=='ready':self.h.w.journal.activate(RUN,uuid.uuid4().hex,'open',{})
        self.store.write=changed
        with self.assertRaises(NativeUIError):owner.read()
        self.assertTrue(owner.failed);self.assertEqual('ready',self.store.read()['phase']);before=self.queries()
        with self.assertRaises(NativeUIError):owner.read()
        self.assertEqual(before,self.queries());self.assertEqual(1,len(owner.rows))

    def test_frozen_host_native_jump_during_last_cas_or_result_copy_cannot_return_a_sample(self):
        for fault in ('cas','copy','guard'):
            with self.subTest(fault=fault):
                if fault!='cas':self.setUp()
                owner=self.owner();write=self.store.write
                def late(value,previous):
                    write(value,previous)
                    if value['phase']=='ready' and fault=='cas':self.native.epoch+=2000
                self.store.write=late
                from adapters.chat_journey import observation
                original=observation.deepcopy
                def copied(value):
                    value=original(value)
                    if fault=='copy' and type(value) is dict and value.get('schemaVersion')==1 and 'state' in value:self.native.epoch+=2000
                    return value
                guard=owner.samples.script_source.scripts.guard
                def late_guard():
                    value=guard()
                    if fault=='guard' and owner.rows:self.native.epoch+=2000
                    return value
                owner.samples.script_source.scripts.guard=late_guard
                with patch.object(observation,'deepcopy',side_effect=copied),self.assertRaises(NativeUIError):owner.read()
                self.assertTrue(owner.failed);self.assertIsNotNone(self.store.read())

    def test_in_memory_source_mutation_after_final_cas_is_not_a_fresh_original(self):
        owner=self.owner();write=self.store.write
        def mutate(value,previous):
            write(value,previous)
            if value['phase']=='ready':owner.samples.frames[-1]['view']['source']['storage']['configSha256']='d'*64
        self.store.write=mutate
        with self.assertRaises(NativeUIError):owner.read()
        self.assertTrue(owner.failed);self.assertIsNotNone(self.store.read())

    def test_source_subclasses_and_future_cursors_fail_before_query_or_intent(self):
        class Unqualified(CompiledChatCacheAbsence):pass
        with self.assertRaises(NativeUIError):self.owner(samples=object.__new__(Unqualified))
        owner=self.owner();before=self.queries()
        with self.assertRaises(NativeUIError):owner.read(1)
        self.assertEqual(before,self.queries());self.assertIsNone(self.store.read())


if __name__=='__main__':unittest.main()
