"""Connected private capture/Save/destination owners; native/OS are models."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from ios.adapters.snapshot_photos_owner import SnapshotPhotosPending
from ios.adapters.snapshot_photos_packets import PhotosSaveInputs
from ios.self_tests.snapshot_photos_domain import SnapshotPhotosDomain


class SnapshotPhotosOwnerTests(unittest.TestCase):
    def pins(self,d):
        result={}
        for root in (d.main.ctx.root,d.helper.root):
            for path in root.iterdir():
                if path.name.startswith(('photos-normal-frame-','photos-save-input-proof-frame-','photos-save-exports-frame-')):
                    stat=path.stat();result[str(path)]=(stat.st_dev,stat.st_ino,stat.st_size,stat.st_mtime_ns,stat.st_ctime_ns,hashlib.sha256(path.read_bytes()).hexdigest())
        return result
    def test_normal_save_reads_identical_original_png_and_repeated_destination_cleanup_is_once_only(self):
        d=SnapshotPhotosDomain(self)
        with d.owner() as owner:
            proof=owner.save('7'*32);self.assertEqual('png',proof['image']['format']);self.assertTrue(proof['photosCleanupRequired'])
            self.assertEqual(d.main.f.bytes,d.helper.run_root.joinpath('original.bytes').read_bytes())
            self.assertTrue(d.main_foreground);self.assertFalse(d.helper.foreground)
        self.assertEqual(1,d.save_count);self.assertEqual(1,d.helper.read_count);self.assertTrue(d.library)
        original=self.pins(d)
        with d.owner() as owner:
            self.assertEqual(proof,owner.save('7'*32))
            with self.assertRaises(NativeUIError):owner.save('8'*32)
            cleaned=owner.cleanup();self.assertTrue(cleaned['photosAssetAbsent']);self.assertTrue(cleaned['companionRunFilesAbsent'])
            self.assertTrue(cleaned['captureCleanupRequired']);self.assertTrue(d.main.f.f.h.path.exists())
        self.assertFalse(d.library);self.assertFalse(d.helper.run_root.exists());self.assertTrue(d.main_foreground)
        self.assertEqual((1,1,1,1),(d.save_count,d.helper.read_count,d.helper.delete_count,d.helper.retire_count))
        with d.owner() as owner:self.assertEqual(cleaned,owner.cleanup())
        later=self.pins(d);self.assertEqual(original,{key:later[key] for key in original})
        self.assertEqual((1,1,1,1),(d.save_count,d.helper.read_count,d.helper.delete_count,d.helper.retire_count))

    def test_lost_normal_save_return_resolves_original_reception_without_resending(self):
        d=SnapshotPhotosDomain(self);d.lose_save=True
        with d.owner() as owner,self.assertRaises((NativeUIError,OSError)):owner.save('7'*32)
        with d.owner() as owner:self.assertTrue(owner.save('7'*32)['photosCleanupRequired'])
        self.assertEqual(1,d.save_count)

    def test_interruption_after_parent_input_intent_reserves_one_unsent_child_on_recovery(self):
        d=SnapshotPhotosDomain(self)
        with patch.object(PhotosSaveInputs,'reserve',side_effect=OSError('Declared interruption before child reserve')):
            with d.owner() as owner,self.assertRaises(OSError):owner.save('7'*32)
        self.assertEqual(0,d.save_count)
        with d.owner() as owner:self.assertTrue(owner.save('7'*32)['photosCleanupRequired'])
        self.assertEqual(1,d.save_count);self.assertEqual(1,d.helper.read_count)

    def test_ignored_normal_save_cannot_invent_an_export_or_replay_input(self):
        d=SnapshotPhotosDomain(self);d.ignore_save=True
        for _ in range(2):
            with d.owner() as owner,self.assertRaises((NativeUIError,SnapshotPhotosPending)):owner.save('7'*32)
        self.assertEqual(1,d.save_count);self.assertFalse(d.library);self.assertEqual(0,d.helper.read_count)

    def test_limited_or_denied_companion_permission_blocks_before_any_client_save(self):
        for state in (2,4):
            with self.subTest(permission=state):
                d=SnapshotPhotosDomain(self);d.helper.authorization=state
                with d.owner() as owner,self.assertRaises(NativeUIError):owner.save('7'*32)
                self.assertEqual(0,d.save_count);self.assertFalse(d.library)

    def test_lost_original_read_and_delete_returns_reconstruct_without_second_actions(self):
        for control in ('snapshot.destination.read','snapshot.destination.delete','snapshot.destination.retire'):
            with self.subTest(control=control):
                d=SnapshotPhotosDomain(self);d.helper.lost_controls.add(control)
                if control=='snapshot.destination.read':
                    with d.owner() as owner,self.assertRaises(NativeUIError):owner.save('7'*32)
                    with d.owner() as owner:owner.save('7'*32);owner.cleanup()
                else:
                    with d.owner() as owner:owner.save('7'*32)
                    with d.owner() as owner,self.assertRaises(NativeUIError):owner.cleanup()
                    with d.owner() as owner:owner.cleanup()
                self.assertEqual((1,1,1,1),(d.save_count,d.helper.read_count,d.helper.delete_count,d.helper.retire_count))

    def test_replaced_original_copy_before_first_chunk_never_qualifies_same_bytes(self):
        d=SnapshotPhotosDomain(self);d.helper.replace_on_chunk=True
        with d.owner() as owner,self.assertRaises((NativeUIError,OSError)):owner.save('7'*32)
        self.assertEqual(1,d.save_count);self.assertEqual(1,d.helper.read_count);self.assertEqual(0,d.helper.delete_count);self.assertTrue(d.helper.run_root.exists())

    def test_actual_retained_read_and_delete_objects_keep_responsibility_until_weak_expiry(self):
        d=SnapshotPhotosDomain(self);d.helper.hold_read=True
        with d.owner() as owner,self.assertRaises(SnapshotPhotosPending):owner.save('7'*32)
        self.assertTrue(d.helper.held_reads);d.helper.held_reads.clear();d.helper.hold_read=False
        with d.owner() as owner:owner.save('7'*32)
        d.helper.hold_delete=True
        with d.owner() as owner,self.assertRaises(SnapshotPhotosPending):owner.cleanup()
        self.assertEqual(0,d.helper.retire_count);self.assertTrue(d.helper.run_root.exists())
        d.helper.held_deletes.clear();d.helper.hold_delete=False
        with d.owner() as owner:owner.cleanup()
        self.assertEqual(1,d.helper.delete_count);self.assertEqual(1,d.helper.retire_count)


if __name__=='__main__':unittest.main()
