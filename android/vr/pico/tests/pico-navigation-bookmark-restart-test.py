#!/usr/bin/env python3
"""Existing normal bookmark owners and explicit original restart handoff."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / 'tests/device'))

if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromNames([
        'self_tests.test_navigation_bookmarks',
        'self_tests.test_navigation_bookmark_restart',
    ])
    raise SystemExit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())
