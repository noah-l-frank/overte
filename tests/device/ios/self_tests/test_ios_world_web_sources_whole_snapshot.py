"""Source5 retains actual twelve-child Snapshot2; old Sources3/4 stay readable."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import tempfile
import unittest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import unpack
from adapters.script_feature.lock import ScriptSourceLock
from ios.self_tests.world_web_sources_fixture import SDK


class WorldWebSourcesWholeSnapshotTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.root=Path(temp.name);self.root.chmod(0o700)
        self.store=PrivateFeatureState(self.root/'ios-world-web-primary-sources.json');self.lock=ScriptSourceLock(self.root/'script-feature-sources.lock')
        self.sdk=SDK();self.sdk.use_snapshot=True;self.sdk.use_whole_snapshot=True
    def test_actual_parent_includes_cache_closures_and_emitters_with_seven_original_clock_queries_and_reconstruction(self):
        with self.lock.held():
            owner=self.sdk.owner(self.store,self.lock);ref=owner.capture('whole-baseline');frame=owner.frame(ref)
            self.assertEqual(5,owner.previous['iosWorldWebSourcesVersion']);self.assertEqual(['snapshot','uikit'],[row['name'] for row in frame['clockFloors']])
            self.assertEqual(7,len(frame['nativeQueries']));self.assertEqual([],frame['surfaceQueries']);self.assertEqual([],frame['closureQueries'])
            retained=unpack(owner.record_store(1).read()['payload'])[0]
            projected=[part for part in retained['originals'].values() if 'worldWebSnapshotProjectionVersion' in part]
            self.assertEqual(12,len(projected));self.assertTrue(all(part['parent']==retained['nativeSnapshot'] and part['worldWebSnapshotProjectionVersion']==2 for part in projected))
            self.assertEqual(frame,self.sdk.owner(self.store,self.lock,historical=True).frame(ref))
            rebuilt=self.sdk.owner(self.store,self.lock);second=rebuilt.capture('new-whole-original');self.assertEqual(2,second['index']);rebuilt.frame(second)
    def test_loss_of_actual_cache_child_never_becomes_partial_success_or_replays_outer_nonce(self):
        with self.lock.held():
            owner=self.sdk.owner(self.store,self.lock);self.sdk.fail='surfaces'
            with self.assertRaises((NativeUIError,OSError)):owner.capture('lost-cache-child')
            self.assertIsNone(owner.state['pending']['nativeSnapshot']);first=self.sdk.snapshot_native.commands[-1]['commandId'];self.sdk.fail=None
            ref=owner.capture('new-batch');owner.frame(ref)
            self.assertNotEqual(first,self.sdk.snapshot_native.commands[-1]['commandId']);self.assertEqual(2,len(self.sdk.snapshot_native.commands))
    def test_equal_byte_parent_replacement_blocks_next_native_send(self):
        with self.lock.held():
            owner=self.sdk.owner(self.store,self.lock);ref=owner.capture('original');frame=owner.frame(ref)
            path=owner.parts.snapshot.paths(frame['nativeSnapshot'])[0];replacement=path.with_suffix('.replacement');replacement.write_bytes(path.read_bytes());replacement.chmod(0o600);replacement.replace(path)
            before=len(self.sdk.snapshot_native.commands)
            with self.assertRaises(NativeUIError):
                with owner.input_round(PrivateFeatureState(self.root/'ios-world-web-inputs.json')):owner.capture('forbidden')
            self.assertEqual(before,len(self.sdk.snapshot_native.commands))
    def test_widget_observation_is_one_exact_receipt_carrier_with_copied_projection_and_inode_guards(self):
        from copy import deepcopy
        with self.lock.held():
            owner=self.sdk.owner(self.store,self.lock);ref=owner.capture('one-widget-receipt');frame=owner.frame(ref)
            retained=unpack(owner.record_store(1).read()['payload'])[0]['originals'];projection=retained['widgets'];parent=retained['widgetReceipt']['parent']
            self.assertEqual(1,projection['worldWebAuxProjectionVersion']);self.assertEqual(parent,projection['parent'])
            self.assertTrue(all(retained[name]['parent']==parent for name in ('widgets','widgetReceipt','uikit','browser')))
            self.assertEqual(1,len({str(path) for name in ('widgets','widgetReceipt','uikit','browser') for path in owner.parts.paths(retained[name])}))
            observed=owner.parts.read(projection);observed['ready']=False
            self.assertTrue(owner.parts.read(projection)['ready']);self.assertEqual(frame['originals']['widgets'],owner.parts.read(retained['widgetReceipt'])['observation'])
            changed=deepcopy(projection);changed['acquisitionId']='ios-'+'f'*32
            with self.assertRaises(NativeUIError):owner.parts.read(changed)
            path=owner.parts.paths(projection)[0];replacement=path.with_suffix('.replacement');replacement.write_bytes(path.read_bytes());replacement.chmod(0o600)
            before=len(self.sdk.snapshot_native.commands)
            with self.assertRaises(NativeUIError):
                with owner.input_round(PrivateFeatureState(self.root/'ios-world-web-inputs.json')):
                    owner.parts.read(projection);replacement.replace(path);owner.capture('forbidden-widget-replacement')
            self.assertEqual(before,len(self.sdk.snapshot_native.commands))


if __name__=='__main__':unittest.main()
