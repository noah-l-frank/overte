"""Actual JS settings dispatch with explicitly modeled native/writer leaves."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[5]/'tests/device'))
from self_tests.test_pico_snapshot_settings_probe import SnapshotSettingsProbeTests


def load_tests(loader,tests,pattern):
    return loader.loadTestsFromTestCase(SnapshotSettingsProbeTests)


if __name__=='__main__':unittest.main()
