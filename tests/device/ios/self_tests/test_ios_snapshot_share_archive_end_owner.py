"""Archive Stop/SDK end over real Node source and original file retirement."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import unittest
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.adapters.appium_adapter import WebDriverRequestError
from ios.adapters.snapshot_share_owner import IOSSnapshotShareOwner
from ios.adapters.snapshot_share_archive_end_owner import SnapshotShareArchiveEndOwner
from ios.self_tests.snapshot_share_archive_end_domain import SourceArchiveEndFlow
from ios.self_tests.snapshot_share_domain import RUN,SYSTEM_UI


class SnapshotShareArchiveEndOwnerTests(unittest.TestCase):
    def prepared(self):
        domain=SourceArchiveEndFlow(self);domain.activate('share-open','1'*32)
        with domain.owner() as share:share.open('1'*32)
        domain.activate('share-select-owned','2'*32)
        with domain.owner() as share:
            share.select('2'*32);share.cleanup();share.admission_seal_owner().seal();share.source_inventory_owner().inspect();share.source_retirement_owner().cleanup()
        return domain
    def history(self,domain):
        share=IOSSnapshotShareOwner.history(PrivateFeatureState(domain.main.ctx.root/'snapshot-share-owner.json'),domain.main.ctx.lock,
            domain.archive.source_lock,domain.main.ctx.binding,domain.archive.binding,RUN,domain.archive.fixture_url,SYSTEM_UI,
            domain.primary.target['appId'],domain.archive.ipa,domain.archive.admission_store)
        return SnapshotShareArchiveEndOwner.history(share,domain.archive_config())

    def test_original_Archive_PID_and_SDK_end_return_to_still_owned_primary_without_parent_end_claim(self):
        domain=self.prepared()
        with domain.end_owner() as owner:
            result=owner.finalize();self.assertTrue(result['archiveProcessRetired']);self.assertTrue(result['archiveSDKAbsent'])
            self.assertTrue(result['primaryProcessStillOwned']);self.assertTrue(result['primarySDKRetirementRequired']);self.assertTrue(result['primaryPageRestorationRequired'])
            value,state=owner.process_history();self.assertTrue(state['windows'][-1]['complete']);self.assertGreaterEqual(state['windows'][-1]['elapsedMs'],3000)
            self.assertEqual(85,result['originalPID']);self.assertEqual(404,owner.state['sdkChecks'][-1]['status'])
        self.assertEqual((1,1),(domain.archive.stop_calls,domain.archive.delete_calls));self.assertFalse(domain.archive.sdk_alive)
        self.assertIsNone(domain.archive.session.read());self.assertTrue(domain.main_foreground);self.assertTrue(domain.main.f.f.h.path.exists())
        with domain.end_owner() as owner:self.assertEqual(result,owner.finalize())
        self.assertEqual((1,1),(domain.archive.stop_calls,domain.archive.delete_calls))
        with (domain.main.ctx.lock.held(),domain.archive.source_lock.held(),patch.object(domain.archive,'execute',side_effect=AssertionError('Historical SDK command')),
                patch.object(domain.archive,'call',side_effect=AssertionError('Historical SDK read')),patch.object(PrivateFeatureState,'write',side_effect=AssertionError('Historical write'))):
            self.assertEqual(result,self.history(domain).proof())

    def test_lost_Stop_return_uses_original_OS_quiet_without_repeating_terminate(self):
        domain=self.prepared();domain.archive.lose_stop=True
        with domain.end_owner() as owner,self.assertRaises(NativeUIError):owner.finalize()
        with domain.end_owner() as owner:self.assertTrue(owner.finalize()['archiveSDKAbsent'])
        self.assertEqual((1,1),(domain.archive.stop_calls,domain.archive.delete_calls))

    def test_lost_DELETE_return_requires_actual_404_and_exact_local_CAS_without_resend(self):
        domain=self.prepared();domain.archive.lose_delete=True
        with domain.end_owner() as owner,self.assertRaises(WebDriverRequestError):owner.finalize()
        self.assertFalse(domain.archive.sdk_alive);self.assertIsNotNone(domain.archive.session.read())
        with domain.end_owner() as owner:self.assertTrue(owner.finalize()['localSDKPointerRetired'])
        self.assertEqual((1,1),(domain.archive.stop_calls,domain.archive.delete_calls))

    def test_ignored_DELETE_ACK_remains_owned_and_does_not_repeat_SDK_deletion(self):
        domain=self.prepared();domain.archive.ignore_delete=True
        for _ in range(2):
            with domain.end_owner() as owner,self.assertRaises(NativeUIError):owner.finalize()
        self.assertTrue(domain.archive.sdk_alive);self.assertIsNotNone(domain.archive.session.read());self.assertEqual(1,domain.archive.delete_calls)
        with domain.main.ctx.lock.held(),domain.archive.source_lock.held():
            owner=self.history(domain);self.assertFalse(owner.state['sdkAbsent']);self.assertIsNone(owner.state['result'])


if __name__=='__main__':unittest.main()
