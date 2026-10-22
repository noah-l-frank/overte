"""Preserve the original Graphics v1 WDA image API, DTOs and filenames."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters.original_screen_images import OriginalScreenImages,VERSION,LIMIT,pixels,capture_record


class IOSGraphicsImages(OriginalScreenImages):
    PROFILE='graphics'
