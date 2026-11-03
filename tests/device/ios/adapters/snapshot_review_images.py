"""Existing original WDA PNG owner, explicitly separated Snapshot namespace."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters.original_screen_images import OriginalScreenImages
from adapters.native_feature_observation import need


class SnapshotReviewImages(OriginalScreenImages):
    PROFILE='snapshot'

    def __init__(self,*args,historical=False,**kwargs):
        need(type(historical) is bool);self.historical=historical
        super().__init__(*args,**kwargs)

    def _write(self):
        need(not self.historical);return super()._write()

    def capture(self,ticket):
        need(not self.historical);return super().capture(ticket)

    def cleanup(self):
        need(not self.historical);return super().cleanup()
