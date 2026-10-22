"""Avatar v1 facade over the closed original-byte segment store."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters.original_packet_segments import OriginalPacketSegments,VERSION,CHUNK_BYTES,LIMIT,AVATAR_LABELS,sha

LABELS=set(AVATAR_LABELS)


class AvatarTailSegments(OriginalPacketSegments):
    PROFILE='avatar-tail'
