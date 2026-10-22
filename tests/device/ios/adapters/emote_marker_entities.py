"""Emote marker EntityItem lifetime profile; native source DTO stays generic."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters.original_marker_entities import OriginalMarkerEntities,VERSION


class IOSEmoteMarkerEntities(OriginalMarkerEntities):
    PROFILE='emote'
