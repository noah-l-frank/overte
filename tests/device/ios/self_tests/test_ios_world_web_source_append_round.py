"""Only journaled original append writes may cross a fresh input boundary."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import unpack,pack
from ios.self_tests import test_ios_world_web_input as fixture


class WorldWebAppendRoundTests(unittest.TestCase):
    def setUp(self):
        self.test=fixture.WorldWebInputTests();self.test.setUp();self.addCleanup(self.test.doCleanups)
    def test_undeclared_new_carrier_during_actual_post_preparation_blocks_delivery_and_no_round_survives(self):
        t=self.test
        with t.held():
            source=t.sdk.owner(t.source_store,t.lock);owner=t.owner(source)
            t.sdk.before_post=lambda:PrivateFeatureState(t.root/'undeclared-original.json').write({'unexpected':True},None)
            with self.assertRaises(NativeUIError):owner.perform(t.sdk.ticket,'uncertain','tap','text')
            self.assertEqual([],t.sdk.posted);self.assertEqual('issued',owner.state['records'][0]['phase'])
            self.assertIsNone(source._round);self.assertIsNone(source._write_round);self.assertIsNone(source._round_pins)
    def test_actual_old_record_prefix_mutation_during_final_post_preparation_never_uses_warm_frame(self):
        t=self.test
        with t.held():
            source=t.sdk.owner(t.source_store,t.lock);first=source.capture('original-before-input');source.frame(first);owner=t.owner(source)
            def mutate():
                store=source.record_store(1);old=store.read();new=deepcopy(old);rows=unpack(new['payload']);rows[0]['label']='mutated-old-prefix';new['payload']=pack(rows);store.write(new,old)
            t.sdk.before_post=mutate
            with self.assertRaises(NativeUIError):owner.perform(t.sdk.ticket,'uncertain','tap','text')
            self.assertEqual([],t.sdk.posted);self.assertIsNone(source._write_round)
    def test_unknown_passive_query_retains_actual_intent_and_no_product_delivery_or_nonce_replay(self):
        t=self.test
        with t.held():
            source=t.sdk.owner(t.source_store,t.lock);owner=t.owner(source);t.sdk.fail='geometry'
            with self.assertRaises(NativeUIError):owner.perform(t.sdk.ticket,'lost-passive-read','tap','text')
            self.assertEqual([],t.sdk.posted);unknown=deepcopy(source.state['pending']['nativeQueries']);self.assertTrue(unknown)
            original_nonces=[row['query']['commandId'] for row in unknown];t.sdk.fail=None
            source.capture('different-passive-read')
            self.assertEqual(unknown,source.state['interrupted'][0]['nativeQueries'])
            self.assertFalse(set(original_nonces)&{row['query']['commandId'] for row in source.frame(source.state['records'][-1])['nativeQueries']})
            with self.assertRaises(NativeUIError):owner.perform(t.sdk.ticket,'lost-passive-read','tap','text')
            self.assertEqual([],t.sdk.posted)

    def test_unsaved_mutable_source_reference_cannot_cross_the_actual_final_input_send(self):
        t=self.test
        with t.held():
            source=t.sdk.owner(t.source_store,t.lock);owner=t.owner(source)
            def mutate():source.state['records'][-1]['sha256']='f'*64
            t.sdk.before_post=mutate
            with self.assertRaises(NativeUIError):owner.perform(t.sdk.ticket,'unsaved-metadata','tap','text')
            self.assertEqual([],t.sdk.posted);self.assertEqual('issued',owner.state['records'][0]['phase'])
            self.assertIsNone(source._round_state_sha);self.assertIsNone(source._write_round)


if __name__=='__main__':unittest.main()
