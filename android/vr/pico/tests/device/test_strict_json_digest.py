"""Shared exact JSON metadata admission; no native or device execution."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[5]/'tests/device'))
from self_tests.test_strict_json_digest import StrictJsonDigestTests


def load_tests(loader,tests,pattern):
    return loader.loadTestsFromTestCase(StrictJsonDigestTests)


if __name__=='__main__':unittest.main()
