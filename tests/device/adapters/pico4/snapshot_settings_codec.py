"""Snapshot Source2 limits over the neutral original loaded chunk codec.

No Snapshot/Native/namespace/input authority is granted by this codec profile.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters.loaded_chunk_codec import OriginalChunkCodec,UNRESOLVED
from adapters.native_feature_observation import need
from adapters.chat_journey import source_bundles
from adapters.script_journey import history

WIRE_LIMIT=69632
CANONICAL_LIMIT=98304
COPY_RESERVATION=2*1024*1024


class SnapshotSettingsCodec(OriginalChunkCodec):
    def __init__(self):
        OriginalChunkCodec.__init__(self)
        try:
            compressed=self.compress_bound(CANONICAL_LIMIT);encoded=4*((compressed+2)//3)
            parts=(encoded+source_bundles.PART_BYTES-1)//source_bundles.PART_BYTES
            inner=self.compress_bound(source_bundles.PART_BYTES+512);packed=4*((inner+2)//3)
            need(1<=parts<=12 and packed<=history.MAX_PACKED and packed+1024<=65536)
            copies=(WIRE_LIMIT+4*((WIRE_LIMIT+2)//3)+2*CANONICAL_LIMIT+compressed+2*encoded
                +4*65536+WIRE_LIMIT+4096+self.metadata_bytes())
            need(copies<=COPY_RESERVATION)
            self.limits=self.original_limits=(compressed,encoded,parts,inner,packed,copies)
            self.verify()
        except BaseException:self.poison();raise

    def verify(self):
        self.guard();need(self.limits is self.original_limits
            and self.compress_bound(CANONICAL_LIMIT)==self.limits[0]
            and self.compress_bound(source_bundles.PART_BYTES+512)==self.limits[3])
        self.guard();return dict(parts=self.limits[2],copies=COPY_RESERVATION)
