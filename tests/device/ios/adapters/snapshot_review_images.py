"""Existing original WDA PNG owner, explicitly separated Snapshot namespace."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters.original_screen_images import OriginalScreenImages


class SnapshotReviewImages(OriginalScreenImages):
    PROFILE='snapshot'
