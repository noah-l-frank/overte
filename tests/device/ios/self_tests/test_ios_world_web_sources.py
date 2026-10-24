"""Real durable source records, typed readers and unknown passive-query recovery."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from contextlib import contextmanager
from pathlib import Path
import tempfile
import unittest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import pack,unpack
from adapters.script_feature.lock import ScriptSourceLock
from ios.self_tests.world_web_sources_fixture import SDK


class WorldWebSourcesTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name);self.root.chmod(0o700)
        self.lock=ScriptSourceLock(self.root/'script-feature-sources.lock');self.store=PrivateFeatureState(self.root/'ios-world-web-primary-sources.json');self.sdk=SDK()

    @contextmanager
    def held(self):
        error=None
        with self.lock.held():
            try:yield
            except Exception as caught:error=caught
        if error is not None:raise error

    def test_actual_typed_native_readers_phase_server_and_every_clock_query_survive_fresh_reconstruction(self):
        with self.held():
            owner=self.sdk.owner(self.store,self.lock);ref=owner.capture('baseline');frame=owner.frame(ref)
            self.assertIsNone(frame['originals']['document']);self.assertEqual(1,len(frame['widgetQueries']))
            self.assertGreater(len(frame['nativeQueries']),10)
            historical=self.sdk.owner(self.store,self.lock,historical=True)
            self.assertEqual(frame,historical.frame(ref));self.assertEqual(owner.state,historical.state)
            fresh=self.sdk.owner(self.store,self.lock);second=fresh.capture('fresh-observation');self.assertEqual(2,second['index'])
            self.assertGreater(fresh.frame(second)['clockJoin']['nativeBefore']['sequence'],frame['clockJoin']['nativeAfter']['sequence'])

    def test_interrupted_passive_native_read_keeps_actual_partial_query_floor_without_input_or_nonce_replay(self):
        with self.held():
            owner=self.sdk.owner(self.store,self.lock);self.sdk.fail='geometry'
            with self.assertRaises(NativeUIError):owner.capture('interrupted')
            partial=deepcopy(owner.state['pending']);self.assertIn('widgets',partial['originals']);self.assertTrue(partial['nativeQueries'])
            self.sdk.fail=None;ref=owner.capture('different-read');self.assertEqual(partial,owner.state['interrupted'][0])
            self.assertNotEqual(partial['start']['nativeBefore']['requestId'],owner.frame(ref)['clockJoin']['nativeBefore']['requestId'])
            self.assertEqual([],owner.frame(ref)['originals']['keys']['source']['down'])

    def test_actual_source_record_bytes_and_immutable_predecessor_are_rechecked_after_warm_cache(self):
        with self.held():
            owner=self.sdk.owner(self.store,self.lock);ref=owner.capture('baseline');owner.capture('next');owner.frame(ref)
            store=owner.record_store(1);original=store.read();changed=deepcopy(original);rows=unpack(changed['payload']);rows[0]['label']='changed-original';changed['payload']=pack(rows)
            store.write(changed,original)
            with self.assertRaises(NativeUIError):owner.frame(owner.state['records'][-1])

    def test_returned_original_alias_cannot_poison_later_frame_or_historical_reconstruction(self):
        with self.held():
            owner=self.sdk.owner(self.store,self.lock);ref=owner.capture('baseline');frame=owner.frame(ref)
            frame['originals']['ledgerAfter']['complete']=False;owner.frames[0]['label']='poisoned-memory'
            self.assertTrue(owner.frame(ref)['originals']['ledgerAfter']['complete'])
            self.assertEqual('baseline',self.sdk.owner(self.store,self.lock,historical=True).frame(ref)['label'])


if __name__=='__main__':unittest.main()
