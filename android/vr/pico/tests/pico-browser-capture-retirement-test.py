#!/usr/bin/env python3
"""Disjoint original complete-history browser capture retirement checks."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT/'tests/device'))
if __name__=='__main__':
    suite=unittest.defaultTestLoader.loadTestsFromName('self_tests.test_pico_browser_capture_retirement')
    raise SystemExit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())
