"""Original typed writer and bounded World2 storage counters; no whole journey."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[5]/'tests/device'))
from self_tests import test_pico_lifecycle_write_gate as states
from self_tests import test_lifecycle_world_bounded as codec
import test_lifecycle_source_write_gate as sources
import test_lifecycle_actor_storage3 as canonical


def load_tests(loader,tests,pattern):
    return unittest.TestSuite(loader.loadTestsFromTestCase(case) for case in (
        states.LifecycleWriteStateGateTests,codec.LifecycleWorldBoundedCodecTests,
        sources.LifecycleSourceWriteGateTests,canonical.LifecycleActorStorage3StrictEntryCounters))


if __name__=='__main__':unittest.main()
