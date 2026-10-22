"""Original UIKit/WK screen PNGs; no Vulkan frame or capture epoch invented.

Actual current native WK window/view/document and original DOM must separately
bracket these screen bytes. A screenshot alone never identifies a web surface.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters.original_screen_images import OriginalScreenImages,VERSION,LIMIT,pixels,capture_record


class IOSTabletWebImages(OriginalScreenImages):
    PROFILE='tablet'
