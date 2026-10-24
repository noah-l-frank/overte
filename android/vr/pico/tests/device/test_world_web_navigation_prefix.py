"""Normal World Clear/B/Back on the original first-three-step owner."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[5]
sys.path[:0]=[str(ROOT),str(ROOT/'tests/device')]
from self_tests.test_pico_world_web_navigation_prefix import WorldWebNavigationPrefixTests
if __name__=='__main__':unittest.main()
