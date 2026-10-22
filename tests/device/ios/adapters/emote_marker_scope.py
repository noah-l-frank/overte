"""Emote marker owner facade preserving its original v1 files and API."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters.original_marker_scope import OriginalMarkerScope,VERSION,PHASES


class IOSEmoteMarkerScope(OriginalMarkerScope):
    PROFILE='emote'
