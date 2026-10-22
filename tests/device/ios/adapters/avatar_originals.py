"""Private Avatar original bytes and manifests, preserving their actual identities."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters.original_frame_store import OriginalFrameStore, VERSION, LIMIT, BLOCK, MAX_FRAMES


class IOSAvatarOriginals(OriginalFrameStore):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,namespace='avatar',schema_prefix='avatar',**kwargs)
