"""Canonical ownership admission for retained Process roots and write attempts."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import unittest
import test_normal_scripts as original
from adapters.normal_feature_state import PrivateFeatureState


class LifecycleProcessFileFactoryTests(unittest.TestCase):
    def test_actual_cleanup_guard_retains_each_process_root_input_and_orphan_write(self):
        fixture=original.PicoNormalScriptsTests();fixture.setUp();self.addCleanup(fixture.doCleanups)
        adapter,native=fixture.instance,fixture.native
        root=adapter._lifecycle_world_store(native.target).path.parent
        self.assertFalse(adapter._lifecycle_restore_owned(native.target))
        for name in ('lifecycle-process-owner.json','lifecycle-restart-inputs.json','lifecycle-process-owner.json.pending-test'):
            with self.subTest(name=name):
                store=PrivateFeatureState(root/name);store.write({'unknown':'retained original process intent'},None)
                before=store.path.read_bytes();self.assertTrue(adapter._lifecycle_restore_owned(native.target))
                self.assertEqual(before,store.path.read_bytes())
                store.path.unlink() # Only this test's deliberately unowned sentinel between disjoint admissions.
        self.assertEqual([],native.inputs);self.assertEqual([],native.controllers)


if __name__=='__main__':unittest.main()
