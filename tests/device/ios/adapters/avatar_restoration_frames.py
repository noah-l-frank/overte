"""Untouched pre-marker/restored frames in the closed Avatar namespace."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters.original_marker_restoration_frames import OriginalMarkerRestorationFrames


class IOSAvatarRestorationFrames(OriginalMarkerRestorationFrames):
    PROFILE='avatar'
