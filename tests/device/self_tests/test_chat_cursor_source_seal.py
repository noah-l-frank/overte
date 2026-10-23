"""Actual global source graph seals; remaining 24 inputs/native producers are seams."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import unittest

from adapters.chat_journey.cursor_source_seal import ChatCursorSourceSeal
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from self_tests import test_chat_observation_cursor as primary_seams
from self_tests import test_chat_observation_publisher as actor_seams
from self_tests.chat_cursor_fixture import cleanup


class ChatCursorSourceSealTests(unittest.TestCase):
    def setUp(self):
        self.actor='actor' in self._testMethodName
        if self.actor:
            self.h=actor_seams.ChatObservationPublisherTests();self.h.setUp();self.addCleanup(self.h.doCleanups)
            self.cursor=self.h.cursor;self.publisher=self.h.owner;self.publisher.publish()
            self.h.flow.next(1);self.publisher.select(self.h.observation(self.h.h.samples('actor',self.h.flow.w.witness_store),'active'))
            self.publisher.publish();self.publisher.select(cleanup(self.h.h,self.cursor));self.publisher.publish()
            self.native=self.h.native;self.queries=self.h.queries;self.root=self.h.root;owner=self.publisher
        else:
            self.h=primary_seams.ChatObservationCursorTests();self.h.setUp();self.addCleanup(self.h.doCleanups)
            self.cursor=self.h.owner;self.publisher=None;self.cursor.read();self.h.h.h.next(1)
            self.cursor.select(self.h.active());self.cursor.read(1);self.cursor.select(cleanup(self.h.h.c,self.cursor));self.cursor.read(2)
            self.native=self.h.h.native;self.queries=self.h.h.queries;self.root=self.h.h.root;owner=self.cursor
        self.store=PrivateFeatureState(self.root/'global-source-seal.json');self.seal=ChatCursorSourceSeal(owner,self.store)

    def test_primary_global_history_seals_all_original_stages_without_retiring_or_requerying(self):
        before=self.queries();value=self.seal.run();self.assertTrue(self.seal.completed)
        self.assertEqual('sealed',value['phase']);self.assertEqual(1,value['chatCursorSourceSealVersion'])
        expected={owner.store.path.name for owner in self.seal.owners}
        self.assertEqual(expected,{row['journal'] for row in value['originals']});self.assertGreaterEqual(len(expected),8)
        self.assertEqual(value,self.seal.receipt(value));self.assertEqual(before,self.queries())
        with self.assertRaises(NativeUIError):self.cursor.read(3)
        for owner in self.cursor.owners:
            with self.assertRaises(NativeUIError):owner.read()
        self.assertEqual(before,self.queries());self.assertTrue(all(owner.store.path.exists() for owner in self.seal.owners))

    def test_actor_global_publications_and_all_stages_close_without_replacing_original_cursor_guard(self):
        before=self.queries();posts=len(self.h.posts);guard=self.cursor._freeze_guard
        value=self.seal.run();self.assertIs(guard,self.cursor._freeze_guard)
        self.assertIs(self.publisher.read_guard,guard);self.assertIs(self.seal.read_guard,self.publisher._freeze_guard)
        self.assertEqual(value,self.seal.receipt(value));self.assertEqual(before,self.queries());self.assertEqual(posts,len(self.h.posts))
        with self.assertRaises(NativeUIError):self.publisher.publish()
        with self.assertRaises(NativeUIError):self.cursor.read()
        self.assertEqual(before,self.queries());self.assertEqual(posts,len(self.h.posts))
        # Receipt is explicitly historical; a native epoch change is not
        # retimed, queried or forgiven as a new sample.
        self.native.epoch+=2000;self.assertEqual(value,self.seal.receipt(value));self.assertEqual(before,self.queries())

    def test_old_stage_cached_tuple_alias_never_qualifies_global_source_seal(self):
        frame=self.cursor.owners[0].samples.frames[0]
        frame['primary']['source']['events']=tuple(frame['primary']['source']['events'])
        before=self.queries()
        with self.assertRaises(NativeUIError):self.seal.run()
        self.assertTrue(self.seal.failed);self.assertFalse(self.seal.completed)
        with self.assertRaises(NativeUIError):self.cursor.read()
        self.assertEqual(before,self.queries());self.assertTrue(self.cursor.store.path.exists())

    def test_frozen_native_jump_after_final_seal_cas_leaves_all_graph_originals_unknown(self):
        write=self.store.write
        def late(value,previous):
            write(value,previous)
            if value['phase']=='sealed':self.native.epoch+=2000
        self.store.write=late;before=self.queries()
        with self.assertRaises(NativeUIError):self.seal.run()
        self.assertTrue(self.seal.failed);self.assertFalse(self.seal.completed)
        self.assertEqual('sealed',self.store.read()['phase'])
        with self.assertRaises(NativeUIError):self.seal.receipt(self.store.read())
        with self.assertRaises(NativeUIError):self.cursor.read()
        self.assertEqual(before,self.queries())


if __name__=='__main__':unittest.main()
