"""Common browser polling counterexamples; no complete journey claim."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[5]/'tests/device'))
from self_tests.test_pico_browser_poll_period import BrowserPollPeriodTests


def load_tests(loader,tests,pattern):
    return loader.loadTestsFromTestCase(BrowserPollPeriodTests)


if __name__=='__main__':unittest.main()
