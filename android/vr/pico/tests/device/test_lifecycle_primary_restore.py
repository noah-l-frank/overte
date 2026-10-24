"""Disjoint same-graph normal Lifecycle closure and original restore tests."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[5]/'tests/device'))
from self_tests.test_pico_lifecycle_operations import LifecycleOperationsRestoreTests
from self_tests.test_lifecycle_pending_historical_quiet import LifecyclePendingHistoricalQuietTests

if __name__=='__main__':unittest.main()
