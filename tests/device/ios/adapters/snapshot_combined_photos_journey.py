"""Explicit Result2 adds a closed historical Photos join to literal Result1."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import time
from adapters.native_clock_join import digest
from adapters.native_feature_observation import need
from adapters.script_feature.history import same
from ios.adapters.snapshot_capture_clock import operation
from ios.adapters.snapshot_combined_journey import SnapshotCombinedJourney,phase_prefix
from ios.adapters.snapshot_photos_archive import SnapshotPhotosArchive


class SnapshotCombinedPhotosJourney:
    def __init__(self,journey,photos,*,monotonic=time.monotonic):
        need(type(journey) is SnapshotCombinedJourney and type(photos) is SnapshotPhotosArchive and photos.combined and photos.historical and callable(monotonic))
        self.journey,self.photos,self.monotonic=journey,photos,monotonic
    @operation
    def proof(self):
        journey,photos=self.journey,self.photos;returned=journey.returned;native=journey.backend.native;share=returned.end.share
        photos.guard();need(photos.root==returned.root and photos.run==returned.run and photos.fixture_url==returned.fixture_url
            and same(photos.binding,returned.binding) and same(photos.capture_pin,returned.files.capture.previous)
            and photos.state['device']==share.state['device'])
        base=journey.proof();read=photos.result()
        need(base['snapshotCombinedJourneyResultVersion']==1 and read['snapshotPhotosArchiveResultVersion']==1
            and read['captureResultSha256']==base['pins']['captureResultSha256'] and read['artifactJournalSha256']==base['pins']['artifactJournalSha256'])
        phase_prefix(native.state['phaseOriginal'],photos.state['phaseOriginal'],returned.run)
        phase_prefix(photos.state['phaseOriginal'],share.state['phaseOriginal'],returned.run)
        need(photos.companion_binding['processIdentity'] not in (returned.binding['processIdentity'],share.archive_binding['processIdentity']))
        result=deepcopy(base);result.update(snapshotCombinedJourneyResultVersion=2,photosDestinationCompositionRequired=False,
            photos=dict(archive=read,literalJourney1Sha256=digest(base),originalPhotosSaveReadDeleteJoined=True,recordedDeviceDigestMatchesShare=True),
            photosSDKRetirementRequired=True)
        return result
