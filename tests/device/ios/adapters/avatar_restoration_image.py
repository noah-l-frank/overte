"""Strict restored full-frame pixels from unchanged Avatar Vulkan originals."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from io import BytesIO
from PIL import Image
from adapters.native_feature_observation import need
from adapters.original_marker_restoration_image import restored as marker_restored
from ios.adapters.avatar_restoration_frames import IOSAvatarRestorationFrames

VERSION=1


def restored(owner,baseline,current,admission,marker_id,*,after_native):
    """Refuse any changed output pixel, including outside the marker/body box.

    This intentionally has no animation/noise allowance: without a separate
    original draw attribution, a small remote stale wearable cannot be
    distinguished from an unrelated legitimate visual change. Both stay
    unqualified. The originals are never edited or filled with a background.
    """
    need(isinstance(owner,IOSAvatarRestorationFrames));owner.lock.assert_held()
    marker=marker_restored(owner,baseline,current,admission,marker_id,after_native=after_native)
    _first,old_raw=owner.frame(baseline);last,new_raw=owner.frame(current)
    old=Image.open(BytesIO(old_raw)).convert('RGBA');new=Image.open(BytesIO(new_raw)).convert('RGBA')
    extent=last['capture']['source']['targetExtent'];need(old.size==new.size==tuple(extent))
    # All decoded RGBA channels, including RGB beneath transparent alpha.
    need(old.tobytes()==new.tobytes());changed=0
    return dict(avatarRestorationImageVersion=VERSION,marker=marker,extent=list(extent),
        pixels=extent[0]*extent[1],changedPixels=changed)
