#!/usr/bin/env python3
"""Original Pico input ownership and independent native animation effects."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT/'tests/device'),str(ROOT/'tests/device/self_tests')]
suite=unittest.defaultTestLoader.loadTestsFromNames([
    'self_tests.test_pico_emote_inputs','self_tests.test_pico_emote_effects'])
if __name__=='__main__':
    raise SystemExit(0 if unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful() else 1)
