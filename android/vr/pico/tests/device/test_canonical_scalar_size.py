"""Shared exact scalar sizing; no native or device execution."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[5]/'tests/device'))
from self_tests.test_canonical_scalar_size import CanonicalScalarSizeTests


def load_tests(loader,tests,pattern):
    return loader.loadTestsFromTestCase(CanonicalScalarSizeTests)


if __name__=='__main__':unittest.main()
