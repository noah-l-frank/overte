"""No-build Pico binary original/physical failure checks; no device capability."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[5]/'tests/device'))
from self_tests.test_pico_assets_raw_archive import AssetsRawArchiveTests

if __name__=='__main__':
    unittest.main()
