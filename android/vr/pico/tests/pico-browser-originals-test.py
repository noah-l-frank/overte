#!/usr/bin/env python3
"""Actual selected native browser/Pico surface and closed original source tests."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT/'tests/device'),str(Path(__file__).resolve().parent/'device')]
if __name__=='__main__':
    suite=unittest.defaultTestLoader.loadTestsFromNames([
        'self_tests.test_pico_browser_geometry','self_tests.test_pico_browser_io',
        'self_tests.test_pico_browser_reveal',
        'self_tests.test_web_dom_observation','self_tests.test_native_web_dom','test_pico_browser_originals',
        'test_pico_browser_apps','self_tests.test_browser_resources'])
    raise SystemExit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())
