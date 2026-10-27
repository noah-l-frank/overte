"""Closed historical Photos2 facts, with no live SDK or source writer."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from unittest.mock import patch
import unittest
from adapters.native_feature_observation import need
from adapters.normal_ui import NativeUIError
from ios.adapters.snapshot_combined_journey import SnapshotCombinedJourney
from ios.adapters.snapshot_combined_photos_journey import SnapshotCombinedPhotosJourney
from ios.adapters.snapshot_photos_archive import SnapshotPhotosArchive
from ios.adapters.snapshot_photos_owner import IOSSnapshotPhotosOwner
from ios.self_tests.snapshot_combined_return_domain import CombinedPhotosDomain


class SnapshotPhotosArchiveContractTests(unittest.TestCase):
    def test_historical_reader_has_no_live_source_input_or_writer_entrypoint(self):
        reader=object.__new__(SnapshotPhotosArchive)
        for name in ('save_state','save','cleanup','observed','handoff','acted','active','permission','companion_clock','inspect_destination'):
            with self.subTest(name=name),self.assertRaises(NativeUIError):getattr(reader,name)()
        for name,args in (('packet',({},)),('inputs',()),('action',({},))):
            with self.subTest(name=name),self.assertRaises(NativeUIError):getattr(reader,name)(*args)
    def test_result2_requires_explicit_historical_profiles_before_any_child_access(self):
        with self.assertRaises(NativeUIError):SnapshotCombinedPhotosJourney(object(),object())
        live=object.__new__(IOSSnapshotPhotosOwner)
        journey=object.__new__(SnapshotCombinedJourney)
        with self.assertRaises(NativeUIError):SnapshotCombinedPhotosJourney(journey,live)


class SnapshotPhotosArchiveTests(unittest.TestCase):
    def completed(self):
        d=CombinedPhotosDomain(self)
        with d.owner() as owner:saved=owner.save('7'*32);cleaned=owner.cleanup()
        return d,owner,saved,cleaned
    def reader(self,d,owner):
        return SnapshotPhotosArchive.history(owner.store,owner.lock,owner.companion_lock,owner.binding,owner.companion_binding,
            owner.run,owner.fixture_url,d.helper.ipa,d.admission_store,owner.primary.target['appId'])
    def test_same_original_save_read_delete_reopens_without_sdk_source_query_or_write(self):
        d,owner,saved,cleaned=self.completed();before={}
        for root in (owner.root,owner.companion_root):
            before[str(root)]={p.name:(p.stat().st_dev,p.stat().st_ino,p.read_bytes()) for p in root.iterdir() if p.is_file()}
        commands,sdk,requests=deepcopy(d.main.commands),deepcopy(d.helper.sdk),deepcopy(d.helper.requests)
        with (owner.lock.held(),owner.companion_lock.held(),
                patch.object(d.helper,'execute',side_effect=AssertionError('Historical SDK command')),
                patch.object(d.helper,'call',side_effect=AssertionError('Historical UIKit query')),
                patch.object(d.primary,'probe',side_effect=AssertionError('Historical OS query')),
                patch('ios.adapters.snapshot_photos_archive.PrivateFeatureState.write',side_effect=AssertionError('Historical write'))):
            reader=self.reader(d,owner);fact=reader.result();self.assertTrue(fact['historicalOnly'])
            self.assertEqual(saved,reader.proof());self.assertEqual(cleaned,reader.cleanup_proof());self.assertTrue(fact['liveSDKPresenceRequired'])
        self.assertEqual(commands,d.main.commands);self.assertEqual(sdk,d.helper.sdk);self.assertEqual(requests,d.helper.requests)
        for root in (owner.root,owner.companion_root):
            self.assertEqual(before[str(root)],{p.name:(p.stat().st_dev,p.stat().st_ino,p.read_bytes()) for p in root.iterdir() if p.is_file()})
        self.assertEqual((1,1,1,1),(d.save_count,d.helper.read_count,d.helper.delete_count,d.helper.retire_count))
    def test_known_saved_result_cannot_hide_pending_action_or_changed_capture_pin(self):
        d,owner,_saved,_cleaned=self.completed()
        with owner.lock.held(),owner.companion_lock.held():
            reader=self.reader(d,owner);before=deepcopy(reader.state['actions'][-1]);reader.state['actions'][-1]['after']=None
            with self.assertRaises(NativeUIError):reader.result()
            reader.state['actions'][-1]=before;baseline=reader.state['input']['baseline'];reader.state['input']['baseline']=reader.state['export']['label']
            with self.assertRaises(NativeUIError):reader.result()
            reader.state['input']['baseline']=baseline;clock=deepcopy(reader.state['companionTail']);reader.state['companionTail']['instance']='7'*32
            with self.assertRaises(NativeUIError):reader.result()
            reader.state['companionTail']=clock;reader.capture_pin=deepcopy(reader.capture_pin);reader.capture_pin['runId']='7'*32
            with self.assertRaises(NativeUIError):reader.result()
        self.assertEqual(1,d.save_count)


if __name__=='__main__':unittest.main()
