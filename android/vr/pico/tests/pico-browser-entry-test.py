#!/usr/bin/env python3
"""Normal Pico app/Home/phase admission; explicit SDK and controller effect seams."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT/'tests/device'),str(Path(__file__).resolve().parent/'device')]
if __name__=='__main__':
    suite=unittest.defaultTestLoader.loadTestsFromName('test_pico_browser_entry')
    raise SystemExit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())
