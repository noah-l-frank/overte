"""Same-PNG whole composition after one delivered Save loses its return."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from unittest.mock import patch
import unittest
from ios.self_tests import test_ios_snapshot_combined_photos_return as normal
from ios.self_tests.snapshot_combined_photos_recovery_domain import LostSaveCombinedPhotosReturnFlow


class SnapshotCombinedPhotosRecoveryTests(unittest.TestCase):
    def test_lost_save_return_reopens_original_then_completes_same_png_result2(self):
        with patch.object(normal,'CombinedPhotosReturnFlow',LostSaveCombinedPhotosReturnFlow):
            normal.SnapshotCombinedPhotosWholeTests.test_one_png_upload_photos_read_delete_share_archive_end_cleanup_and_return(self)


if __name__=='__main__':unittest.main()
