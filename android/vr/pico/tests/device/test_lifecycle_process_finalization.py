"""Actual v2 delivery fences plus original codec/domain compatibility."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[5]/'tests/device'))
from self_tests.test_lifecycle_process_finalization import LifecycleProcessFinalizationTests
from self_tests.test_lifecycle_process_compatibility import LifecycleProcessCompatibilityTests

if __name__=='__main__':unittest.main()
