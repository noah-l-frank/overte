#!/usr/bin/env python3
"""Disjoint native and private-reader historical capture inventory checks."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT/'tests/device'),str(ROOT/'android/vr/pico/tests/device')]
if __name__=='__main__':
    suite=unittest.defaultTestLoader.loadTestsFromNames([
        'test_world_render_retirements_native','self_tests.test_pico_world_render_retirements'])
    raise SystemExit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())
