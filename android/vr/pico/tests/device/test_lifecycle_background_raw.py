"""Scoped Background3 originals, strict namespace and historical1 guards."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[5]/'tests/device'))
from self_tests import test_pico_lifecycle_background_raw as cases


def load_tests(loader,tests,pattern):
    return unittest.TestSuite(loader.loadTestsFromTestCase(case) for case in (
        cases.LifecycleBackgroundRawTests,cases.LifecycleBackgroundRawOwnerTests,cases.LifecycleBackgroundHistoryTests))


if __name__=='__main__':unittest.main()
