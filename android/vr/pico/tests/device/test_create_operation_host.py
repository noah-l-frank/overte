"""Disjoint no-build original Pico stdio host checks; no device access."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[5]/'tests/device'))
from self_tests.test_pico_operation_host import PicoOperationHostTests

if __name__=='__main__':unittest.main()
