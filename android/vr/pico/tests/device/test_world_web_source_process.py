"""World original source pass in a real independent observer process."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[5]
sys.path[:0]=[str(ROOT),str(ROOT/'tests/device')]
from self_tests.test_pico_world_web_source_process import WorldWebSourceProcessTests
if __name__=='__main__':unittest.main()
