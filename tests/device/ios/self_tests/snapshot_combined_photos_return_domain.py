"""One shared PNG and provider ledger, with both helpers admitted at Capture."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from ios.self_tests.snapshot_combined_upload_return_domain import CombinedUploadReturnFlow
from ios.self_tests.snapshot_photos_domain import SnapshotPhotosDomain
from ios.self_tests.snapshot_share_domain import DEVICE


class SharedPhotosDomain(SnapshotPhotosDomain):combined=True


class CombinedPhotosReturnFlow(CombinedUploadReturnFlow):
    def prepare_destinations(self,case):
        self.photos=SharedPhotosDomain(case,main=self.main,phase_client=self.client,foreground_owner=self,physical_selector=DEVICE)
    def __init__(self,case):
        super().__init__(case);self.activate('save','7'*32)
        with self.photos.owner() as owner:
            self.photos_saved=owner.save('7'*32);self.photos_cleaned=owner.cleanup()
