"""Explicit Assets component cases; no whole/native/device qualification."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[5]/'tests/device'))
from self_tests.test_pico_assets_prefix3_factory import AssetsPrefix3FactoryTests,AssetsRawReceiptCodecTests


def load_tests(loader, _tests, _pattern):
    return unittest.TestSuite(loader.loadTestsFromTestCase(case) for case in (AssetsPrefix3FactoryTests,AssetsRawReceiptCodecTests))


if __name__ == '__main__':
    unittest.main()
