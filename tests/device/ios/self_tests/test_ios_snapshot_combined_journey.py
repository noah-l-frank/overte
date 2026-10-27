"""Original combined pending/capture pair and conditional two-prefix cleanup."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from adapters.normal_ui import NativeUIError
from ios.adapters.snapshot_journey_files import IOSSnapshotJourneyFilesOwner
from ios.self_tests.snapshot_combined_journey_domain import CombinedJourneyDomain,RUN


class SnapshotCombinedJourneyTests(unittest.TestCase):
    def prepared(self):
        d=CombinedJourneyDomain(self);d.complete_pending()
        with d.capture_owner() as owner:owner.capture('c'*32);original=owner.history('artifact',owner.state['artifact']).path()
        return d,original

    def test_normal_pair_cleanup_preserves_one_manager_original_png_and_pure_archive(self):
        d,original=self.prepared();before=(original.stat().st_ino,original.read_bytes())
        with d.files_owner() as owner:
            result=owner.cleanup();self.assertEqual(2,result['iosSnapshotJourneyFilesResultVersion']);self.assertEqual('combined',result['workProfile'])
            self.assertTrue(result['hostOriginalRetained']);self.assertTrue(result['pairedCleanupRequired']);self.assertFalse(result['standaloneCaptureFinalized'])
            self.assertIn('managerSha256',owner.pins);self.assertEqual(3000,result['fileChannel']['fileChannelQuietMilliseconds'])
            store,lock,binding,url=owner.store,owner.lock,owner.binding,owner.fixture_url
        self.assertFalse(d.f.f.h.path.exists());self.assertEqual(before,(original.stat().st_ino,original.read_bytes()))
        self.assertEqual((2,1,1),(d.capture_count,d.cancel_count,d.png_count));self.assertEqual(1,sum(query['action']=='feature-ios-snapshot-file-remove' for query in d.commands))
        commands=deepcopy(d.commands)
        with lock.held():
            archived=IOSSnapshotJourneyFilesOwner.archive(store,lock,binding,RUN,url,combined=True);self.assertEqual(result,archived.proof())
            with self.assertRaises(NativeUIError):IOSSnapshotJourneyFilesOwner.archive(store,lock,binding,RUN,url)
        self.assertEqual(commands,d.commands)

    def test_lost_conditional_unlink_return_reopens_original_without_second_delete_or_capture(self):
        d,original=self.prepared();d.lose_remove=True
        with d.files_owner() as owner,self.assertRaises(NativeUIError):owner.cleanup()
        self.assertFalse(d.f.f.h.path.exists())
        with d.files_owner() as owner:self.assertTrue(owner.cleanup()['hostOriginalRetained'])
        self.assertTrue(original.exists());self.assertEqual(1,sum(query['action']=='feature-ios-snapshot-file-remove' for query in d.commands))
        self.assertEqual((2,1),(d.capture_count,d.cancel_count))

    def test_default_profile_cannot_adopt_combined_pair_or_issue_file_removal(self):
        d,original=self.prepared();commands=deepcopy(d.commands)
        with self.assertRaises(NativeUIError),d.files_owner(combined=False):pass
        self.assertEqual(commands,d.commands);self.assertTrue(original.exists());self.assertTrue(d.f.f.h.path.exists())

    def test_new_capture_manager_cannot_reanchor_pending_pair_or_authorize_unlink(self):
        d=CombinedJourneyDomain(self);d.complete_pending()
        d.work_template['source']['workers'][0]['manager']['instance']='7'*32
        d.work_template['source']['timerSources']['workers'][0]['membership']['instance']='7'*32
        with d.capture_owner() as owner:owner.capture('c'*32)
        commands=deepcopy(d.commands);original=d.f.f.h.path.read_bytes()
        with self.assertRaises(NativeUIError),d.files_owner():pass
        self.assertEqual(commands,d.commands);self.assertEqual(original,d.f.f.h.path.read_bytes())
        self.assertFalse(any(query['action']=='feature-ios-snapshot-file-remove' for query in d.commands))


if __name__=='__main__':unittest.main()
