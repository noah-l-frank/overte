"""Immutable Create evidence storage using the reviewed common file owner."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import time
from adapters.original_frame_store import OriginalFrameStore,VERSION,LIMIT,BLOCK,MAX_FRAMES


class IOSCreateOriginals(OriginalFrameStore):
    def __init__(self,root,binding,run,role,guard,intent,*,kind='sources',monotonic=time.monotonic):
        super().__init__(root,binding,run,role,guard,intent,namespace='create',schema_prefix='create',kind=kind,monotonic=monotonic)
