"""Same v16 Navigation recipe through original modeled G1 Open/Delete/Close."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[5]/'tests/device'))
from self_tests.test_pico_navigation_generation_prefix import NavigationGenerationPrefixTests
if __name__=='__main__':unittest.main()
