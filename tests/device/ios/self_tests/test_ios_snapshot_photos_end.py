"""Closed Photos end scope, real Node originals and passive retired replay."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
from pathlib import Path
import tempfile
from unittest.mock import patch
import unittest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.original_file_reads import collect
from adapters.native_clock_join import digest
from adapters.normal_ui import NativeUIError
from ios.adapters.appium_adapter import WebDriverRequestError
from ios.adapters.process_retirement import filename
from ios.adapters.snapshot_photos_end_graph import SnapshotPhotosEndGraph
from ios.adapters.snapshot_photos_end_owner import SnapshotPhotosEndOwner
from ios.adapters.snapshot_photos_end_position import SnapshotPhotosRetiredSDKPosition
from ios.adapters.snapshot_capture_owner import IOSSnapshotCaptureOwner
from ios.adapters import snapshot_photos_end_read_area as read_area
from ios.self_tests.snapshot_photos_end_domain import PhotosEndFlow,selected_public_policy,selection_pin


class SnapshotPublicSelectionMetadataTests(unittest.TestCase):
    """Ticket guards only; no before-delivery, product or graph authority."""
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name);self.root.chmod(0o700);self.path=self.root/'selected-domain-policy.json'
        self.policy=dict(url='http://127.0.0.1:49112/v1/snapshot-domain-policy',tokenSha256='0'*64,
            binding=dict(processId=73,startIdentity='123456',domainId='11111111-2222-4333-8444-555555555555'),instance='b'*32)
        value=dict(selectionKind='snapshot-photos-public-domain-selection',runId='a'*32,configuration=self.policy)
        PrivateFeatureState(self.path).write(value,None);raw=self.path.read_bytes()
        self.ticket=dict(path=str(self.path),stat=selection_pin(self.path),sha256=hashlib.sha256(raw).hexdigest(),valueSha256=digest(value))
    def test_unchanged_independently_chosen_metadata_round_trips_without_product_authority(self):
        self.assertEqual(self.policy,selected_public_policy(self.ticket))
    def test_same_public_json_on_replacement_inode_is_rejected(self):
        replacement=self.path.with_name('replacement.json');replacement.write_bytes(self.path.read_bytes());replacement.chmod(0o600);replacement.replace(self.path)
        with self.assertRaises(NativeUIError):selected_public_policy(self.ticket)
    def test_changed_original_bytes_cannot_be_reselected_from_their_current_value(self):
        self.path.write_bytes(self.path.read_bytes()+b' ')
        with self.assertRaises(NativeUIError):selected_public_policy(self.ticket)
    def test_different_missing_file_cannot_supply_the_selected_configuration(self):
        wrong=dict(self.ticket,path=str(self.root/'unselected-missing.json'))
        with self.assertRaises((NativeUIError,FileNotFoundError)):selected_public_policy(wrong)
    def test_byte_and_value_digests_are_separate_required_selection_pins(self):
        for key in ('sha256','valueSha256'):
            with self.subTest(pin=key),self.assertRaises(NativeUIError):selected_public_policy(dict(self.ticket,**{key:'f'*64}))


class SnapshotPhotosEndContractTests(unittest.TestCase):
    def test_new_process_profile_accepts_only_photos_primary_stage_zero(self):
        self.assertEqual('ios-snapshot-photos-primary-0-process-retirement.json',filename('snapshotphotos','primary',0))
        self.assertEqual('ios-snapshot-share-archive-primary-0-process-retirement.json',filename('snapshotsharearchive','primary',0))
        self.assertEqual('ios-graphics-actor-1-process-retirement.json',filename('graphics','actor',1))
        for role,stage in (('actor',0),('primary',1),('actor',1)):
            with self.subTest(role=role,stage=stage),self.assertRaises(NativeUIError):filename('snapshotphotos',role,stage)
    def test_foreign_retired_sdk_position_cannot_open_any_original_graph(self):
        graph=object.__new__(SnapshotPhotosEndGraph)
        with self.assertRaises(NativeUIError):graph.replay(object())
        with self.assertRaises(NativeUIError):SnapshotPhotosRetiredSDKPosition(object())
    def test_frozen_graph_rejects_untyped_or_live_journey_before_file_access(self):
        with self.assertRaises(NativeUIError):SnapshotPhotosEndGraph(object())


class SnapshotPhotosEndWholeTests(unittest.TestCase):
    def test_first_photos_pid_sdk_end_replays_frozen_same_png_graph_without_live_context(self):
        flow=PhotosEndFlow(self);d=flow.domain;helper=d.photos.helper;host=(flow.host.stat().st_ino,flow.host.read_bytes())
        with flow.owner() as owner:
            self.assertTrue(d.public_selection_before_first_page_delivery)
            self.assertIsNone(read_area._ACTIVE.get())
            self.assertEqual(1,flow.last_read_counts['captureDecodes']);self.assertEqual(1,flow.last_read_counts['inventoryDecodes'])
            self.assertGreater(flow.last_read_counts.get('captureHits',0),0);self.assertGreater(flow.last_read_counts.get('inventoryHits',0),0)
            literal=deepcopy(owner.graph.previous['originalResult2']);self.assertTrue(literal['photosSDKRetirementRequired'])
            self.assertEqual(2,owner.previous['snapshotPhotosEndOwnerVersion']);self.assertEqual(2,owner.ctx.snapshot['snapshotPhotosEndSnapshotVersion'])
            slot=deepcopy(owner.ctx.snapshot['sdkSlot']);self.assertEqual(1,slot['snapshotPhotosSDKSlotVersion'])
            self.assertEqual(str(helper.session.path),slot['path']);self.assertEqual(str(helper.session.path.parent),slot['parentPath'])
            self.assertEqual(owner.ctx.parent_pin(),slot['parentIdentity']);self.assertEqual(owner.ctx.pin(helper.session.path),slot['originalSDKStat'])
            self.assertEqual(owner.binding,slot['binding']);self.assertEqual(owner.run,slot['runId']);self.assertEqual(digest(owner.ctx.admission.previous),slot['admissionOwnerSha256'])
            result=owner.finalize();self.assertEqual((1,7),(owner.graph.last_round_counts['captureDecodes'],owner.graph.last_round_counts['captureHits']))
            self.assertGreater(owner.graph.last_round_counts['captureOriginalReads'],0)
            self.assertEqual(2,result['snapshotPhotosEndedVersion']);self.assertEqual(2,result['retiredSDKPosition']['snapshotPhotosRetiredSDKPositionVersion'])
            self.assertEqual(digest(slot),result['retiredSDKPosition']['sdkSlotSha256'])
            self.assertEqual(84,result['originalPID']);self.assertTrue(result['originalGraphReplayedWithoutSDK'])
            self.assertTrue(result['mainProcessStillOwned']);self.assertTrue(result['sourceMainSDKWitnessRetirementRequired'])
            self.assertEqual(literal,owner.graph.previous['originalResult2']);self.assertEqual(404,owner.state['sdkChecks'][-1]['status'])
            self.assertEqual((1,1),(helper.stop_calls,helper.delete_calls));self.assertIsNone(helper.session.read())
            process,history=owner.process_history();self.assertTrue(history['windows'][-1]['complete']);self.assertGreaterEqual(history['windows'][-1]['elapsedMs'],3000)
        with flow.owner() as repeated:self.assertEqual(result,repeated.finalize())
        self.assertEqual((1,1),(helper.stop_calls,helper.delete_calls));self.assertFalse(helper.sdk_alive)
        with flow.journey() as fresh:
            before=(deepcopy(helper.requests),deepcopy(helper.sdk),deepcopy(d.main.commands))
            with (patch.object(helper,'execute',side_effect=AssertionError('Retired historical SDK command')),
                    patch.object(helper,'call',side_effect=AssertionError('Retired historical SDK read')),
                    patch.object(PrivateFeatureState,'write',side_effect=AssertionError('Retired historical write'))):
                helper_config=flow.helper();wrong_slot=PrivateFeatureState(helper.session.path.with_name('other-unowned-missing-sdk.json'))
                self.assertIsNone(wrong_slot.read())
                with self.assertRaises(NativeUIError):SnapshotPhotosEndOwner.history(fresh,dict(helper_config,sessionStore=wrong_slot))
                historical=SnapshotPhotosEndOwner.history(fresh,helper_config);self.assertEqual(result,historical.proof())
                self.assertEqual(str(helper.session.path),historical.ctx.snapshot['sdkSlot']['path'])
                position=SnapshotPhotosRetiredSDKPosition(historical);self.assertEqual(literal,historical.graph.replay(position))
                row=historical.graph.row_store(1).path;held=row.with_name('held-photos-end-pin.json');row.rename(held)
                try:
                    with self.assertRaises(NativeUIError):historical.proof()
                finally:held.rename(row)
            self.assertEqual(before,(helper.requests,helper.sdk,d.main.commands))
        self.assertEqual(host,(flow.host.stat().st_ino,flow.host.read_bytes()));self.assertTrue(d.main_foreground)
        self.assertEqual((1,1,1,1,1),(d.main.upload_count,d.photos.save_count,helper.read_count,helper.delete_count,helper.retire_count))
    def test_typed_capture_inventory_hits_preserve_actual_reads_and_fresh_verdicts(self):
        # Separate real typed Result2 cache integration, not an End2 endpoint.
        flow=PhotosEndFlow(self);d=flow.domain;factory=flow.originals();host=(flow.host.stat().st_ino,flow.host.read_bytes())
        before=deepcopy((d.photos.helper.requests,d.photos.helper.sdk,d.archive.requests,d.archive.sdk,d.main.commands))
        with (patch.object(d.photos.helper,'execute',side_effect=AssertionError('Historical Photos SDK command')),
                patch.object(d.photos.helper,'call',side_effect=AssertionError('Historical Photos SDK read')),
                patch.object(d.archive,'execute',side_effect=AssertionError('Historical Archive SDK command')),
                patch.object(d.archive,'call',side_effect=AssertionError('Historical Archive SDK read')),
                patch.object(PrivateFeatureState,'write',side_effect=AssertionError('Historical state write')),
                patch.object(PrivateFeatureState,'discard',side_effect=AssertionError('Historical state discard'))):
            with factory.read_journey() as journey:
                area=read_area._ACTIVE.get();self.assertIsNotNone(area)
                capture_entry=next(row for row in area.cache.values() if row['kind']=='capture')
                args=(journey.photos.capture_store,journey.photos.lock,journey.photos.binding,journey.photos.run,journey.photos.fixture_url)
                with collect() as first_reads:first=IOSSnapshotCaptureOwner.archive(*args,combined=True)
                with collect() as second_reads:second=IOSSnapshotCaptureOwner.archive(*args,combined=True)
                self.assertIs(first,second);self.assertEqual(set(capture_entry['paths']),first_reads);self.assertEqual(first_reads,second_reads)
                first_result=first.result();second_result=second.result();self.assertEqual(first_result,second_result);self.assertIsNot(first_result,second_result)
                inventory=journey.journey.returned.end.files.inventory
                inventory_entry=next(row for row in area.cache.values() if row['kind']=='inventory' and row['owner'] is inventory)
                with collect() as inventory_first_reads:original=inventory.original()
                with collect() as inventory_second_reads:repeated=inventory.original()
                self.assertEqual(original,repeated);self.assertEqual(set(inventory_entry['paths']),inventory_first_reads);self.assertEqual(inventory_first_reads,inventory_second_reads)
                first_proof=inventory.proof();second_proof=inventory.proof();self.assertEqual(first_proof,second_proof);self.assertIsNot(first_proof,second_proof)
                hits=area.counts['inventoryHits']
                with collect() as atomic_first_reads:atomic_first=read_area.inventory_original_with_fresh_proof(inventory)
                with collect() as atomic_second_reads:atomic_second=read_area.inventory_original_with_fresh_proof(inventory)
                self.assertEqual(atomic_first,atomic_second);self.assertIsNot(atomic_first[2],atomic_second[2])
                self.assertEqual(first_proof,atomic_first[2]);self.assertEqual(original,atomic_first[:2])
                self.assertEqual(atomic_first_reads,atomic_second_reads)
                self.assertTrue(set(inventory_entry['paths'])<=atomic_first_reads)
                self.assertEqual(hits+2,area.counts['inventoryHits'])
                self.assertTrue(journey.proof()['photosSDKRetirementRequired'])
        self.assertEqual(1,factory.last_read_counts['captureDecodes']);self.assertEqual(1,factory.last_read_counts['inventoryDecodes'])
        self.assertGreater(factory.last_read_counts['captureHits'],0);self.assertGreater(factory.last_read_counts['inventoryHits'],0)
        self.assertIsNone(read_area._ACTIVE.get());self.assertEqual(before,(d.photos.helper.requests,d.photos.helper.sdk,d.archive.requests,d.archive.sdk,d.main.commands))
        self.assertEqual(host,(flow.host.stat().st_ino,flow.host.read_bytes()));self.assertTrue(d.public_selection_before_first_page_delivery)
    def test_lost_delivered_stop_and_sdk_delete_cold_reopen_original_without_second_effect(self):
        flow=PhotosEndFlow(self);helper=flow.domain.photos.helper;helper.lose_stop=True
        with flow.owner() as first:
            with self.assertRaisesRegex(NativeUIError,'lost Photos Stop'):first.finalize()
            self.assertTrue(first.state['stopIssued']);self.assertFalse(first.state['processReady']);stop_record=first.store.read()
        self.assertEqual((1,0),(helper.stop_calls,helper.delete_calls));helper.lose_delete=True
        with flow.owner() as second:
            self.assertIsNot(first,second);self.assertEqual(stop_record,second.previous)
            with self.assertRaises(WebDriverRequestError):second.finalize()
            self.assertTrue(second.state['sdkIssued']);self.assertFalse(second.state['sdkAbsent']);delete_record=second.store.read()
        self.assertEqual((1,1),(helper.stop_calls,helper.delete_calls));self.assertFalse(helper.sdk_alive);self.assertIsNotNone(helper.session.read())
        with flow.owner() as third:
            self.assertIsNot(second,third);self.assertEqual(delete_record,third.previous)
            result=third.finalize();self.assertTrue(result['localSDKPointerRetired']);self.assertTrue(result['originalPhotosSDK404'])
        self.assertEqual((1,1),(helper.stop_calls,helper.delete_calls));self.assertIsNone(helper.session.read())
        self.assertTrue(flow.domain.main_foreground);self.assertTrue(flow.host.exists())


if __name__=='__main__':unittest.main()
