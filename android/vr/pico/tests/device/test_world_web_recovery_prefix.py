"""Normal World foreign-origin/HTTP recovery after actual first-six steps."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[5]
sys.path[:0]=[str(ROOT),str(ROOT/'tests/device')]
from self_tests.test_pico_world_web_recovery_prefix import WorldWebRecoveryPrefixTests
if __name__=='__main__':unittest.main()
