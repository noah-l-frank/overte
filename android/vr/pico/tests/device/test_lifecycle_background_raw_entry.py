"""Private seven-normal-action Background3 entry; only baseline Actor samples."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[5]/'tests/device'))
import test_lifecycle_actor_storage3 as canonical


def load_tests(loader,tests,pattern):
    return loader.loadTestsFromTestCase(canonical.LifecycleActorStorage3EntryTests)


if __name__=='__main__':unittest.main()
