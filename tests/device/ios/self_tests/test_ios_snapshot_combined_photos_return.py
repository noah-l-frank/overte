"""Same actual PNG across Upload4, Photos2 and the original Share/Return path."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from unittest.mock import patch
import unittest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.adapters.snapshot_combined_journey import SnapshotCombinedJourney
from ios.adapters.snapshot_combined_photos_journey import SnapshotCombinedPhotosJourney
from ios.adapters.snapshot_page_return_owner import SnapshotPageReturnOwner
from ios.adapters.snapshot_photos_archive import SnapshotPhotosArchive
from ios.adapters.snapshot_upload_owner import IOSSnapshotUploadOwner
from ios.adapters.snapshot_upload_backend_owner import IOSSnapshotUploadBackendOwner
from ios.self_tests.snapshot_combined_photos_return_domain import CombinedPhotosReturnFlow
from ios.self_tests import test_ios_snapshot_page_return as old_return


class SnapshotCombinedPhotosWholeTests(unittest.TestCase):
    def test_one_png_upload_photos_read_delete_share_archive_end_cleanup_and_return(self):
        with patch.object(old_return,'PageReturnFlow',CombinedPhotosReturnFlow):d,host=old_return.SnapshotPageReturnOwnerTests.prepared(self)
        before=(host.stat().st_ino,host.read_bytes());self.assertEqual(1,d.main.upload_count);self.assertEqual(1,d.photos.save_count)
        with d.return_owner() as returned:returned.restore()
        photo=d.photos
        with returned.lock.held(),returned.end.share.archive_lock.held(),photo.helper_lock.held():
            archived=SnapshotPageReturnOwner.history(returned.page,returned.files,returned.end,combined=True)
            native=IOSSnapshotUploadOwner.history(PrivateFeatureState(archived.root/'snapshot-upload-owner.json'),archived.lock,
                archived.binding,archived.run,archived.fixture_url,combined=True,frontend_http=True,frontend_caller=True)
            backend=IOSSnapshotUploadBackendOwner.history(native,domain_policy=d.main.domain_policy)
            photos=SnapshotPhotosArchive.history(PrivateFeatureState(archived.root/'photos-save-owner.json'),archived.lock,photo.helper_lock,
                archived.binding,photo.helper_binding,archived.run,archived.fixture_url,photo.helper.ipa,photo.admission_store,archived.end.share.primary.target['appId'])
            prior=SnapshotCombinedJourney(archived,backend);literal=prior.proof();self.assertEqual(1,literal['snapshotCombinedJourneyResultVersion'])
            self.assertTrue(literal['photosDestinationCompositionRequired']);calls=deepcopy(d.main.commands);sdk=deepcopy(photo.helper.sdk)
            with (patch.object(photo.helper,'execute',side_effect=AssertionError('Historical Photos SDK')),
                    patch.object(photo.helper,'call',side_effect=AssertionError('Historical Photos UIKit')),
                    patch.object(PrivateFeatureState,'write',side_effect=AssertionError('Historical write'))):
                result=SnapshotCombinedPhotosJourney(prior,photos).proof()
                self.assertEqual(2,result['snapshotCombinedJourneyResultVersion']);self.assertFalse(result['photosDestinationCompositionRequired'])
                self.assertTrue(result['photos']['originalPhotosSaveReadDeleteJoined']);self.assertTrue(result['photosSDKRetirementRequired'])
                self.assertTrue(result['wholeFeatureRequired']);self.assertEqual(1,literal['snapshotCombinedJourneyResultVersion'])
            self.assertEqual(calls,d.main.commands);self.assertEqual(sdk,photo.helper.sdk)
        self.assertEqual(before,(host.stat().st_ino,host.read_bytes()));self.assertFalse(photo.library)
        self.assertEqual((1,1,1,1),(photo.save_count,photo.helper.read_count,photo.helper.delete_count,photo.helper.retire_count))
        self.assertEqual((2,1,1,1,1),(d.main.capture_count,d.main.cancel_count,d.main.png_count,d.main.upload_count,d.share_count))


if __name__=='__main__':unittest.main()
