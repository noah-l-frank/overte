"""Tablet-owned original packet byte segments, without native fact semantics."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters.original_packet_segments import OriginalPacketSegments,VERSION,CHUNK_BYTES,LIMIT,TABLET_COMPONENTS,sha

COMPONENTS=TABLET_COMPONENTS


class TabletWebSourceSegments(OriginalPacketSegments):
    PROFILE='tabletweb-sources'
