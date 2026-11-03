"""Disjoint private Lifecycle Pending prerequisite cases; no whole feature claim."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[5]/'tests/device'))
from self_tests.test_pico_lifecycle_pending_return import LifecyclePendingReturnPinsTests


def load_tests(loader,tests,pattern):
    return unittest.TestSuite(loader.loadTestsFromTestCase(case) for case in
        (LifecyclePendingReturnPinsTests,))


if __name__=='__main__':unittest.main()
