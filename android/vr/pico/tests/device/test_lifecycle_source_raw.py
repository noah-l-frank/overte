"""Disjoint35 SourceRaw4/BG4 cases, including the actual shared512 read cap."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[5]/'tests/device'))
from self_tests.test_pico_lifecycle_source_raw import LifecycleSourceRawTests,PendingBeforeIoTests
from self_tests.test_pico_lifecycle_family_gate import LifecycleFamilyGateTests
from self_tests.test_pico_lifecycle_expanded_guard import LifecycleExpandedGuardTests


def load_tests(loader,tests,pattern):
    return unittest.TestSuite(loader.loadTestsFromTestCase(case) for case in
        (LifecycleSourceRawTests,PendingBeforeIoTests,LifecycleFamilyGateTests,LifecycleExpandedGuardTests))


if __name__ == '__main__':
    unittest.main()
