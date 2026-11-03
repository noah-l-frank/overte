"""Assets UI original WDA PNG namespace; no Model/GPU success is implied."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters.original_screen_images import OriginalScreenImages
from adapters.original_packet_segments import OriginalPacketSegments
from ios.adapters.tablet_web_screen_archive import TabletWebScreenArchive


class IOSAssetsUiImages(OriginalScreenImages):PROFILE='assets'
class AssetsUiScreenParts(OriginalPacketSegments):PROFILE='assets-ui-screen'
class AssetsUiScreenArchive(TabletWebScreenArchive):
    VERSION_KEY='assetsUiScreenArchiveVersion'
    PARTS_TYPE=AssetsUiScreenParts
