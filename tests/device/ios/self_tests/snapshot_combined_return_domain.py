"""Same ordinary Page/Share/Photos/Return producers with explicit Combined2.

Every Combined work producer is selected before its first original exists.
Qt/V8/UIKit/OS/SDK remain models. Existing Python/Node coordinators, private
files, original PNG bytes and bounded lifetime owners execute unchanged.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from unittest.mock import patch
from ios.self_tests import snapshot_page_return_domain,snapshot_photos_domain
from ios.self_tests.snapshot_page_return_domain import PageJourneyDomain,PageReturnFlow
from ios.self_tests.snapshot_combined_journey_domain import CombinedJourneyDomain
from ios.self_tests.snapshot_combined_capture_domain import CombinedCaptureDomain
from ios.self_tests.snapshot_photos_domain import SnapshotPhotosDomain
from ios.self_tests.snapshot_share_domain import SnapshotShareDomain


class CombinedPageJourneyDomain(PageJourneyDomain):
    combined=True
    def __init__(self,case):
        with patch.object(snapshot_page_return_domain,'SnapshotJourneyFilesDomain',CombinedJourneyDomain):super().__init__(case)


class CombinedPageReturnFlow(PageReturnFlow):
    combined=True
    def prepare_main(self,case):
        self.page=CombinedPageJourneyDomain(case);prepared=self.page.prepare_png();main=self.page.capture
        main.runtime._sources=self.page.runtime._sources
        return main,deepcopy(prepared['phase']['activations']),prepared['phase']['createdEpochMs']


class CombinedPhotosDomain(SnapshotPhotosDomain):
    combined=True
    def __init__(self,case):
        with patch.object(snapshot_photos_domain,'SnapshotCaptureDomain',CombinedCaptureDomain):super().__init__(case)


class CombinedShareDomain(SnapshotShareDomain):
    combined=True
    def prepare_main(self,case):
        main=CombinedCaptureDomain(case)
        with main.owner() as capture:
            capture.capture('f'*32);activations=deepcopy(capture.state['phaseOriginal']['activations']);created=capture.state['phaseOriginal']['createdEpochMs']
        return main,activations,created
