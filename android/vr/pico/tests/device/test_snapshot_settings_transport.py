"""Original Source2 shell branches on task-owned host files, without ADB."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[5]/'tests/device'))
from self_tests.test_pico_snapshot_settings_transport import SnapshotSettingsShellTests


def load_tests(loader,tests,pattern):
    return loader.loadTestsFromTestCase(SnapshotSettingsShellTests)


if __name__=='__main__':unittest.main()
