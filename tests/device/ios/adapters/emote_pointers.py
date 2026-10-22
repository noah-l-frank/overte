"""Preserve original Emote v1 ownership and native receipt semantics."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters.original_marker_pointers import OriginalMarkerPointers,receipt as _receipt,VERSION,zero


def receipt(value,binding,run,role,previous=None):return _receipt(value,binding,run,role,previous=previous,profile='emote')


class IOSEmotePointers(OriginalMarkerPointers):
    PROFILE='emote'
