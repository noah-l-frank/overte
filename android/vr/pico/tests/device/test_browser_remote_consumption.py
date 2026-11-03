"""Explicit Browser component cases; whole public coordinator remains open."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[5]/'tests/device'))
from self_tests.test_pico_browser_remote_consumption import BrowserRemoteConsumptionTests


def load_tests(loader, _tests, _pattern):
    return loader.loadTestsFromTestCase(BrowserRemoteConsumptionTests)


if __name__ == '__main__':
    unittest.main()
