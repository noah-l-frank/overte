#!/usr/bin/env python3
"""Original Pico QML/controller/OS admission; explicit SDK/native source seams."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT/'android/vr/pico/tests/device'),str(ROOT/'tests/device')]
suite=unittest.defaultTestLoader.loadTestsFromNames([
    'test_navigation_transport_hook',
    'test_controller_transport_hook',
    'test_lifecycle_transport_once'])

if __name__=='__main__':
    raise SystemExit(0 if unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful() else 1)
