"""Emote v1 facade preserving existing immutable artifact and manifest formats."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import time
from adapters.original_frame_store import OriginalFrameStore, VERSION, LIMIT, BLOCK, MAX_FRAMES


class IOSEmoteOriginals(OriginalFrameStore):
    def __init__(self,root,binding,run,role,guard,intent,*,kind='sources',monotonic=time.monotonic):
        super().__init__(root,binding,run,role,guard,intent,namespace='emote',schema_prefix='emote',
                         kind=kind,monotonic=monotonic)
