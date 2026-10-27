"""Immutable Create evidence storage using the reviewed common file owner."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import time
from adapters.original_frame_store import OriginalFrameStore,VERSION,LIMIT,BLOCK,MAX_FRAMES
from adapters.native_feature_observation import need


class IOSCreateOriginals(OriginalFrameStore):
    def __init__(self,root,binding,run,role,guard,intent,*,kind='sources',monotonic=time.monotonic,namespace='create'):
        need(namespace in ('create','assets-marker'))
        super().__init__(root,binding,run,role,guard,intent,namespace=namespace,
            schema_prefix='create' if namespace=='create' else 'assetsMarker',kind=kind,monotonic=monotonic)
