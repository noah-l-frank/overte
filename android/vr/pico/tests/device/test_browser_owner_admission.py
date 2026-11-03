"""Original Parent/owner admission; complete public Browser remains open."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[5]/'tests/device'))
from self_tests.test_pico_browser_owner_admission import BrowserOwnerAdmissionTests


def load_tests(loader, _tests, _pattern):
    return loader.loadTestsFromTestCase(BrowserOwnerAdmissionTests)


if __name__ == '__main__':
    unittest.main()
