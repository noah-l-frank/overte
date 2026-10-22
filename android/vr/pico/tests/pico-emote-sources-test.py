#!/usr/bin/env python3
"""Device-free original Emote storage and actual Pico source-owner checks."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[4]
sys.path[:0] = [str(ROOT / 'tests/device'), str(ROOT / 'tests/device/self_tests')]
suite = unittest.defaultTestLoader.loadTestsFromNames([
    'self_tests.test_emote_originals', 'self_tests.test_pico_emote_sources',
    'self_tests.test_pico_emote_inputs', 'self_tests.test_pico_emote_effects', 'self_tests.test_native_script_work', 'self_tests.test_pico_emote_lifetime', 'self_tests.test_pico_emote_background'])
if __name__ == '__main__':
    raise SystemExit(0 if unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful() else 1)
