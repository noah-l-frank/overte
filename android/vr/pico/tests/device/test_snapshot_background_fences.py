"""Disjoint Snapshot background admission, stale-clock and archive negatives."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[5]/'tests/device'))
from self_tests.test_pico_snapshot_background_owner import SnapshotBackgroundFenceTests,SnapshotBaseFrameExtractionTests


if __name__=='__main__':unittest.main()
