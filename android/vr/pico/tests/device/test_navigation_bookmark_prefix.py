"""Existing normal bookmark/arrival/Home/Close/Stereo under the first-eleven parent."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[5]/'tests/device'))
from self_tests.test_pico_navigation_bookmark_prefix import NavigationBookmarkPrefixTests
if __name__=='__main__':unittest.main()
