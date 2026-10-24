"""Source4 composes the actual single-parent snapshot with native clock journal."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.lock import ScriptSourceLock
from ios.self_tests.world_web_sources_fixture import SDK


class WorldWebSourcesSnapshotTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.root=Path(temp.name);self.root.chmod(0o700)
        self.lock=ScriptSourceLock(self.root/'script-feature-sources.lock');self.store=PrivateFeatureState(self.root/'ios-world-web-primary-sources.json');self.sdk=SDK();self.sdk.use_snapshot=True
    @contextmanager
    def held(self):
        error=None
        with self.lock.held():
            try:yield
            except Exception as caught:error=caught
        if error is not None:raise error
    def test_single_actual_parent_and_clock_floor_survive_full_historical_and_live_reconstruction(self):
        with self.held():
            owner=self.sdk.owner(self.store,self.lock);ref=owner.capture('snapshot-baseline');frame=owner.frame(ref)
            self.assertEqual(4,owner.previous['iosWorldWebSourcesVersion']);self.assertEqual(['snapshot','surfaces'],[row['name'] for row in frame['clockFloors']])
            self.assertEqual(12,len(frame['nativeQueries']));self.assertIsNone(frame['originals']['document'])
            self.assertTrue(frame['originals']['surfaces']['source']['surfaces'][0]['cached'])
            self.assertEqual(frame['originals']['surfaces']['requestId'],frame['surfaceQueries'][0]['commandId'])
            raw=owner.record_store(1).read();from adapters.script_feature.history import unpack
            retained=unpack(raw['payload'])[0];parents=[ref['parent'] for ref in retained['originals'].values() if 'worldWebSnapshotProjectionVersion' in ref]
            self.assertEqual(9,len(parents));self.assertTrue(all(parent==retained['nativeSnapshot'] for parent in parents))
            historical=self.sdk.owner(self.store,self.lock,historical=True);self.assertEqual(frame,historical.frame(ref))
            rebuilt=self.sdk.owner(self.store,self.lock);second=rebuilt.capture('fresh-snapshot')
            self.assertEqual(2,second['index']);self.assertGreater(rebuilt.frame(second)['clockJoin']['nativeBefore']['sequence'],frame['clockJoin']['nativeAfter']['sequence'])
            self.assertEqual(2,len(self.sdk.snapshot_native.commands))
    def test_unknown_single_snapshot_delivery_retains_original_query_and_resumes_with_new_nonce(self):
        with self.held():
            owner=self.sdk.owner(self.store,self.lock);self.sdk.fail='geometry'
            with self.assertRaises((NativeUIError,OSError)):owner.capture('unknown-snapshot')
            pending=deepcopy(owner.state['pending']);self.assertTrue(pending['nativeQueries']);self.assertIsNone(pending['nativeSnapshot'])
            first=self.sdk.snapshot_native.commands[-1]['commandId'];self.sdk.fail=None
            ref=owner.capture('new-original');self.assertEqual(pending,owner.state['interrupted'][0]);self.assertNotEqual(first,self.sdk.snapshot_native.commands[-1]['commandId'])
            self.assertEqual(1,ref['index']);owner.frame(ref)
    def test_replaced_single_original_parent_is_rejected_before_any_further_native_send(self):
        with self.held():
            owner=self.sdk.owner(self.store,self.lock);ref=owner.capture('baseline');frame=owner.frame(ref)
            path=owner.parts.snapshot.paths(frame['nativeSnapshot'])[0];raw=path.read_bytes();path.unlink();path.write_bytes(raw);path.chmod(0o600)
            before=len(self.sdk.snapshot_native.commands)
            with self.assertRaises(NativeUIError):
                with owner.input_round(PrivateFeatureState(self.root/'ios-world-web-inputs.json')):owner.capture('forbidden')
            self.assertEqual(before,len(self.sdk.snapshot_native.commands))
    def test_unknown_actual_surface_query_is_retained_before_delivery_and_recovery_does_not_resend_its_nonce(self):
        with self.held():
            owner=self.sdk.owner(self.store,self.lock);self.sdk.fail='surfaces'
            with patch.object(self.sdk,'send',wraps=self.sdk.send) as actual:
                with self.assertRaises(NativeUIError):owner.capture('unknown-cache-original')
                pending=deepcopy(owner.state['pending']);self.assertIsNotNone(pending['nativeSnapshot'])
                self.assertEqual([self.sdk.queries['surfaces']],pending['surfaceQueries']);first=pending['surfaceQueries'][0]['commandId']
                self.sdk.fail=None;ref=owner.capture('new-cache-original');self.assertEqual(pending,owner.state['interrupted'][0])
                frame=owner.frame(ref);self.assertNotEqual(first,frame['surfaceQueries'][0]['commandId'])
                sent=[call.args[1]['commandId'] for call in actual.call_args_list if call.args[0]=='surfaces']
                self.assertEqual(2,len(sent));self.assertEqual(1,sent.count(first))
    def test_equal_byte_replacement_of_actual_cache_carrier_blocks_all_later_native_queries(self):
        with self.held():
            owner=self.sdk.owner(self.store,self.lock);reference=owner.capture('cache-original');frame=owner.frame(reference)
            from adapters.script_feature.history import unpack
            raw=unpack(owner.record_store(1).read()['payload'])[0];path=owner.parts.paths(raw['originals']['surfaces'])[0]
            content=path.read_bytes();replacement=path.with_suffix('.replacement');replacement.write_bytes(content);replacement.chmod(0o600);replacement.replace(path)
            with patch.object(self.sdk,'send',wraps=self.sdk.send) as native:
                with self.assertRaises(NativeUIError):
                    with owner.input_round(PrivateFeatureState(self.root/'ios-world-web-inputs.json')):owner.capture('forbidden-cache-query')
                native.assert_not_called()


if __name__=='__main__':unittest.main()
