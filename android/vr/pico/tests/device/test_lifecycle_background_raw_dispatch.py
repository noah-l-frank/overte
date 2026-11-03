"""Actual canonical arm fence and dispatch replacement/deadline counters."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[5]/'tests/device'))
import test_lifecycle_actor_storage3 as canonical


def load_tests(loader,tests,pattern):
    return loader.loadTestsFromTestCase(canonical.LifecycleActorStorage3DispatchCounters)


if __name__=='__main__':unittest.main()
