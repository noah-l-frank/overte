"""World Web immutable originals; input delivery never establishes an effect."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import time
from adapters.original_frame_store import OriginalFrameStore


class IOSWorldWebOriginals(OriginalFrameStore):
    def __init__(self,root,binding,run,role,guard,intent,*,kind='sources',monotonic=time.monotonic):
        super().__init__(root,binding,run,role,guard,intent,namespace='world-web',schema_prefix='worldWeb',
                         kind=kind,monotonic=monotonic)
