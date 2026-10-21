"""Emote PNG ownership through the existing private world-image file engine."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from overte_phone_graphics_images import PhoneGraphicsImages,_image_record

VERSION=1


def record(value):return _image_record(value,'emote')


class PhoneEmoteImages(PhoneGraphicsImages):
    # Same exclusive/private IO, actual inode/digest checks and durable write
    # intents as Graphics v1. No new filesystem or relaxed metadata limits.
    KIND='emote'
