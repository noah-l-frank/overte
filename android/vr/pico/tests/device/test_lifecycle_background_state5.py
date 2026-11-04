"""Disjoint private Lifecycle component cases; no complete journey claim."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[5]/'tests/device'))
from self_tests.test_pico_lifecycle_background_state5 import LifecycleBackgroundState5Tests


def load_tests(loader,tests,pattern):
    return loader.loadTestsFromTestCase(LifecycleBackgroundState5Tests)


if __name__=='__main__':unittest.main()
