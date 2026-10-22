#!/usr/bin/env python3
"""Private Pico browser composition; SDK/DOM/Java product effects remain explicit seams."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT/'tests/device'))
if __name__=='__main__':
    suite=unittest.defaultTestLoader.loadTestsFromName('self_tests.test_pico_tablet_web_feature')
    suite.addTests(unittest.defaultTestLoader.loadTestsFromName('self_tests.test_pico_tablet_web_images'))
    suite.addTests(unittest.defaultTestLoader.loadTestsFromName('self_tests.test_pico_tablet_web_flow'))
    suite.addTests(unittest.defaultTestLoader.loadTestsFromName('self_tests.test_pico_browser_quiet_journal'))
    raise SystemExit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())
