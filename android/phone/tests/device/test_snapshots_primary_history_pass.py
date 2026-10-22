#!/usr/bin/env python3
"""Public cleanup rechecks actual original receipts after unlocked history IO.

The prefix uses explicit SDK/native/render producers, real TLS and owned host
files. These tests make no compiler, Android device or disk-durability claim.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parent))
import test_snapshots_primary_cleanup_stages as stages


class SnapshotPrimaryHistoryPassTests(unittest.TestCase):
    # Reuse the original public fixture/helper without inheriting its cases.
    setUpClass=classmethod(stages.SnapshotPrimaryCleanupStagesTests.setUpClass.__func__)
    tearDownClass=classmethod(stages.SnapshotPrimaryCleanupStagesTests.tearDownClass.__func__)
    setUp=stages.SnapshotPrimaryCleanupStagesTests.setUp
    exercise=stages.SnapshotPrimaryCleanupStagesTests.exercise

    def test_original_json_changed_after_unlocked_read_cannot_reach_current_measurement(self):self.exercise('after-json')
    def test_original_png_mode_changed_after_unlocked_read_cannot_reach_current_measurement(self):self.exercise('after-png-mode')
    def test_original_binary_hardlinked_after_unlocked_read_cannot_reach_current_measurement(self):self.exercise('after-binary-link')
    def test_original_manifest_changed_after_unlocked_read_cannot_reach_current_measurement(self):self.exercise('after-manifest')
    def test_original_removed_after_unlocked_read_cannot_reach_current_measurement(self):self.exercise('after-missing')
    def test_identical_feature_header_rewritten_after_unlocked_read_is_red(self):self.exercise('after-feature-aba')
    def test_identical_role_header_rewritten_after_unlocked_read_is_red(self):self.exercise('after-role-aba')


if __name__=='__main__':unittest.main()
