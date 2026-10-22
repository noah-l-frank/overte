"""Bounded strict original domain Settings/controller/runner regression group."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[5]/'tests/device'))
from self_tests import test_pico_create_permissions as original


def load_tests(loader,tests,pattern):return loader.loadTestsFromTestCase(original.PicoCreatePermissionTests)


if __name__=='__main__':unittest.main()
