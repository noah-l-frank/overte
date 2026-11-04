"""Declared Host400 storage admission/cross-group file faults only."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import unittest
import test_snapshot_settings_decoded_groups as owner

def load_tests(loader,tests,pattern):
    return unittest.TestSuite(owner.SnapshotSettingsDecodedGroupsTests(name) for name in sorted(owner.ADMISSION_TESTS))

if __name__=='__main__':unittest.main()
