"""Explicit raw literal profiles using original private host ranges only."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[5]/'tests/device'))
from self_tests.test_pico_raw_literal_profile import RawLiteralProfileTests
if __name__=='__main__':unittest.main()
