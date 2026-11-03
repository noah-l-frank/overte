"""Actual pending Actor-return kernel lock wait only."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[5]/'tests/device'))
from self_tests.test_pico_browser_return_wait import BrowserReturnWaitTests


def load_tests(loader,tests,pattern):
    return loader.loadTestsFromTestCase(BrowserReturnWaitTests)


if __name__=='__main__':unittest.main()
