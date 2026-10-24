"""World Web passive Qt pointer originals on the common closed profile."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters.original_marker_pointers import OriginalMarkerPointers,receipt as original_receipt,zero


def receipt(value,binding,run,role,previous=None):
    return original_receipt(value,binding,run,role,previous=previous,profile='worldweb')


class WorldWebPointers(OriginalMarkerPointers):
    PROFILE='worldweb'
