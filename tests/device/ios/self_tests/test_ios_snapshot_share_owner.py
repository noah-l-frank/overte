"""Connected ordinary Share cancellation/original transfer; native/OS modeled."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import hashlib
import unittest
from adapters.normal_ui import NativeUIError
from ios.adapters.snapshot_share_owner import SnapshotSharePending
from ios.self_tests.snapshot_share_domain import SnapshotShareDomain


class SnapshotShareOwnerTests(unittest.TestCase):
    def opened(self):
        d=SnapshotShareDomain(self);d.activate('share-open','1'*32)
        with d.owner() as owner:owner.open('1'*32)
        d.activate('share-select-owned','2'*32);return d

    def test_normal_cancel_then_select_receive_finish_import_reads_the_actual_capture_bytes_once(self):
        d=SnapshotShareDomain(self);d.activate('share-open','1'*32)
        with d.owner() as owner:self.assertTrue(owner.open('1'*32)['wholeFeatureRequired'])
        d.activate('share-cancel','2'*32)
        with d.owner() as owner:self.assertTrue(owner.cancel('2'*32)['wholeFeatureRequired'])
        d.activate('share-open','3'*32)
        with d.owner() as owner:owner.open('3'*32)
        d.activate('share-select-owned','4'*32)
        with d.owner() as owner:
            result=owner.select('4'*32);self.assertTrue(result['archiveCleanupRequired']);self.assertTrue(result['wholeFeatureRequired'])
            self.assertEqual(hashlib.sha256(d.main.f.bytes).hexdigest(),result['image']['sha256'])
        self.assertEqual(d.main.f.bytes,d.archive.archive_run.joinpath('original.bytes').read_bytes())
        self.assertEqual((2,1,1,1),(d.share_count,d.archive.read_count,d.archive.import_count,d.archive.chunk_count));self.assertTrue(d.main_foreground);self.assertFalse(d.archive.foreground)
        with d.owner() as owner:self.assertEqual(result,owner.select('4'*32))
        self.assertEqual((2,1,1,1),(d.share_count,d.archive.read_count,d.archive.import_count,d.archive.chunk_count))

    def test_lost_normal_Qt_share_return_resolves_actual_native_reception_without_second_input(self):
        d=SnapshotShareDomain(self);d.lost_share=True;d.activate('share-open','1'*32)
        with d.owner() as owner,self.assertRaises((NativeUIError,OSError)):owner.open('1'*32)
        with d.owner() as owner:self.assertTrue(owner.open('1'*32)['wholeFeatureRequired'])
        self.assertEqual(1,d.share_count)

    def test_lost_receiver_read_return_adopts_original_without_repeating_read(self):
        d=self.opened();d.lost_buttons.add('snapshot.share.receive')
        with d.owner() as owner,self.assertRaises(NativeUIError):owner.select('2'*32)
        with d.owner() as owner:self.assertTrue(owner.select('2'*32)['hostOriginalRetained'])
        self.assertEqual(1,d.archive.read_count);self.assertEqual(1,d.primary_ui.clicks.count('snapshot.share.receive'))

    def test_lost_finish_return_never_reanchors_or_reactivates_dead_receiver(self):
        d=self.opened();d.lost_buttons.add('snapshot.share.finish')
        with d.owner() as owner,self.assertRaises(NativeUIError):owner.select('2'*32)
        self.assertFalse(d.receiver_active)
        with d.owner() as owner:self.assertTrue(owner.select('2'*32)['hostOriginalRetained'])
        self.assertEqual(1,d.primary_ui.clicks.count('snapshot.share.finish'));self.assertEqual(1,d.archive.read_count)

    def test_lost_import_return_adopts_unchanged_import_without_second_click(self):
        d=self.opened();d.lost_buttons.add('snapshot.share.archive.import')
        with d.owner() as owner,self.assertRaises(NativeUIError):owner.select('2'*32)
        with d.owner() as owner:self.assertTrue(owner.select('2'*32)['hostOriginalRetained'])
        self.assertEqual(1,d.archive.import_count)

    def test_lost_system_cancel_return_uses_actual_native_outcome_without_resending(self):
        d=SnapshotShareDomain(self);d.activate('share-open','1'*32)
        with d.owner() as owner:owner.open('1'*32)
        d.activate('share-cancel','2'*32);d.lost_buttons.add('System Share Cancel')
        with d.owner() as owner,self.assertRaises(NativeUIError):owner.cancel('2'*32)
        with d.owner() as owner:self.assertTrue(owner.cancel('2'*32)['wholeFeatureRequired'])
        self.assertEqual(1,d.primary_ui.clicks.count('System Share Cancel'))

    def test_actual_retained_read_object_blocks_finish_until_weak_expiry_without_resend(self):
        d=self.opened();d.archive.hold_read=True
        with d.owner() as owner,self.assertRaises(SnapshotSharePending):owner.select('2'*32)
        self.assertEqual(0,d.primary_ui.clicks.count('snapshot.share.finish'));self.assertTrue(d.archive.held_reads)
        d.archive.held_reads.clear()
        with d.owner() as owner:self.assertTrue(owner.select('2'*32)['hostOriginalRetained'])
        self.assertEqual(1,d.archive.read_count);self.assertEqual(1,d.primary_ui.clicks.count('snapshot.share.receive'))

    def test_acknowledged_ignored_selection_stays_pending_and_never_repeats_system_click(self):
        d=self.opened();d.ignore_select=True
        for _ in range(2):
            with d.owner() as owner,self.assertRaises((SnapshotSharePending,NativeUIError)):owner.select('2'*32)
        self.assertEqual(1,d.primary_ui.clicks.count('Snapshot Original Receiver'));self.assertEqual(0,d.archive.read_count)

    def test_acknowledged_ignored_cancellation_stays_pending_without_resending(self):
        d=SnapshotShareDomain(self);d.activate('share-open','1'*32)
        with d.owner() as owner:owner.open('1'*32)
        d.activate('share-cancel','2'*32);d.ignore_cancel=True
        for _ in range(2):
            with d.owner() as owner,self.assertRaises(NativeUIError):owner.cancel('2'*32)
        self.assertEqual(1,d.primary_ui.clicks.count('System Share Cancel'));self.assertIsNotNone(d.pending_operation)

    def test_acknowledged_ignored_Qt_share_stays_pending_without_second_native_input(self):
        d=SnapshotShareDomain(self);d.ignore_share=True;d.activate('share-open','1'*32)
        for _ in range(2):
            with d.owner() as owner,self.assertRaises(NativeUIError):owner.open('1'*32)
        self.assertEqual(1,d.share_count);self.assertIsNone(d.pending_operation)


if __name__=='__main__':unittest.main()
