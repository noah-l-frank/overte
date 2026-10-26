"""A real single-main preparation boundary before the final page return."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import unittest
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.adapters.snapshot_page_owner import IOSSnapshotPageOwner
from ios.adapters.snapshot_pending_owner import IOSSnapshotPendingOwner
from ios.adapters.snapshot_page_return_owner import SnapshotPageReturnOwner,initial_snapshot
from ios.self_tests.snapshot_page_return_domain import PageJourneyDomain,PageReturnFlow


class SnapshotPageReturnPreparationTests(unittest.TestCase):
    def test_normal_page_Pending_and_PNG_share_one_original_main_without_rewriting_old_phase(self):
        domain=PageJourneyDomain(self);result=domain.prepare_png()
        self.assertTrue(result['page']['snapshotPageOpen']);self.assertTrue(domain.shown);self.assertEqual('snapshot',domain.route)
        self.assertEqual(2,domain.capture.capture_count);self.assertEqual(1,domain.capture.cancel_count);self.assertEqual(1,domain.capture.png_count)
        self.assertEqual(domain.capture.ctx.binding['processIdentity'],'42');self.assertTrue(domain.capture.f.f.h.path.exists())
        self.assertEqual(['a'*32,'f'*32,'c'*32],[row['ticket'] for row in result['phase']['activations']])
        before=list(domain.clicks)
        with domain.owner() as old:
            pending=IOSSnapshotPendingOwner.archive(PrivateFeatureState(domain.ctx.root/'pending-snapshot-owner.json'),old.lock,old.binding,old.run,old.fixture_url)
            pending.result();original=old.record(old.state['opened']);root=pending.state['initial']['rootId']
            self.assertEqual(root,initial_snapshot(original,root)['root'])
            with self.assertRaises(NativeUIError):initial_snapshot(original,'aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee')
            with self.assertRaises(NativeUIError):old.restore()
        self.assertEqual(before,domain.clicks)


class SnapshotPageReturnOwnerTests(unittest.TestCase):
    def prepared(self):
        domain=PageReturnFlow(self);domain.activate('share-open','1'*32)
        with domain.owner() as share:share.open('1'*32)
        domain.activate('share-select-owned','2'*32)
        with domain.owner() as share:
            share.select('2'*32);share.cleanup();share.admission_seal_owner().seal();share.source_inventory_owner().inspect();share.source_retirement_owner().cleanup()
        with domain.end_owner() as end:self.assertTrue(end.finalize()['archiveSDKAbsent'])
        with domain.main.files_owner() as files:
            cleaned=files.cleanup();self.assertTrue(cleaned['hostOriginalRetained'])
            host=files.capture.history('artifact',files.capture.state['artifact']).path();self.assertTrue(host.exists())
        self.assertFalse(domain.main.f.f.h.path.exists())
        return domain,host
    def test_same_original_main_returns_original_page_after_actual_Share_Archive_end_and_two_prefix_cleanup(self):
        domain,host=self.prepared()
        with domain.return_owner() as owner:
            restored=owner.restore();self.assertTrue(restored['restoration']['originalRouteRestored']);self.assertTrue(restored['restoration']['launcherSelectionRestored'])
            self.assertTrue(restored['mainProcessStillOwned']);self.assertTrue(restored['primarySDKRetirementRequired'])
        self.assertFalse(domain.page.shown);self.assertEqual(2,domain.page.index);self.assertEqual(1,domain.page.clicks.count('tablet.home'))
        self.assertEqual(1,domain.page.clicks.count('tablet.close'));self.assertTrue(host.exists());self.assertTrue(domain.main_foreground)
        self.assertEqual((1,1),(domain.archive.stop_calls,domain.archive.delete_calls))
        before=list(domain.page.clicks)
        with domain.return_owner() as repeated:self.assertEqual(restored,repeated.restore())
        self.assertEqual(before,domain.page.clicks)
        with (repeated.lock.held(),repeated.end.share.archive_lock.held(),
                patch.object(domain.archive,'execute',side_effect=AssertionError('Historical SDK command')),
                patch.object(domain.archive,'call',side_effect=AssertionError('Historical SDK read')),
                patch.object(domain.primary_ui,'call',side_effect=AssertionError('Historical UIKit read')),
                patch.object(PrivateFeatureState,'write',side_effect=AssertionError('Historical write'))):
            historical=SnapshotPageReturnOwner.history(repeated.page,repeated.files,repeated.end);self.assertEqual(restored,historical.proof())
            actual_read=PrivateFeatureState.read
            for destination,replacement in ((historical.engine.store.path,historical.page.previous),(historical.page.store.path,historical.engine.previous)):
                def wrong_profile(store):return replacement if store.path==destination else actual_read(store)
                with patch.object(PrivateFeatureState,'read',wrong_profile),self.assertRaises(NativeUIError):
                    if destination==historical.engine.store.path:SnapshotPageReturnOwner.history(repeated.page,repeated.files,repeated.end)
                    else:IOSSnapshotPageOwner.archive(historical.page.store,historical.lock,historical.binding,historical.run,historical.fixture_url)

    def test_lost_Home_page_and_close_returns_reopen_same_original_engine_without_second_click(self):
        domain,host=self.prepared()
        for control in ('tablet.home','tablet.page.3','tablet.close'):
            domain.page.lose.add(control)
            with domain.return_owner() as owner,self.assertRaises(NativeUIError):owner.restore()
            domain.page.lose.remove(control)
        with domain.return_owner() as owner:result=owner.restore()
        self.assertTrue(result['restoration']['inputDeliveryUnknown']);self.assertTrue(result['restoration']['originalRouteRestored'])
        self.assertFalse(domain.page.shown);self.assertEqual(2,domain.page.index);self.assertTrue(host.exists())
        for control in ('tablet.home','tablet.page.3','tablet.close'):self.assertEqual(1,domain.page.clicks.count(control))
        self.assertEqual((1,1),(domain.archive.stop_calls,domain.archive.delete_calls))


if __name__=='__main__':unittest.main()
