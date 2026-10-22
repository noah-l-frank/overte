"""Avatar-owned normal Script/View marker and actual quiet cleanup."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters.original_marker_scope import OriginalMarkerScope,VERSION,PHASES


class IOSAvatarMarkerScope(OriginalMarkerScope):
    PROFILE='avatar'
