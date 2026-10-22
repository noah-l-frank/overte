"""Avatar marker API-return and EntityItem weak-lifetime ownership profile."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters.original_marker_entities import OriginalMarkerEntities,VERSION


class IOSAvatarMarkerEntities(OriginalMarkerEntities):
    PROFILE='avatar'
