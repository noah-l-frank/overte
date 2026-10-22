"""Actual Qt normal controls and whole original editor/bridge recovery bodies."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import json
import unittest
import test_create_polyvox_controls_native as original


class CreateRecoveryNativeTests(unittest.TestCase):
    run_original=original.CreatePolyvoxControlsNativeTests.run_original
    def test_actual_qml_normal_denial_retry_cube_original_create_and_delete(self):
        value=json.loads(self.run_original('create-recovery-controls.cpp'))
        self.assertEqual({'denied','created','deleted','actor','pointerCalls'},set(value))
        self.assertTrue(value['denied']['statusError']);self.assertEqual([],value['denied']['selectedIds'])
        self.assertFalse(value['created']['statusError']);self.assertEqual(1,len(value['created']['selectedIds']))
        self.assertEqual([],value['deleted']['selectedIds']);self.assertGreater(value['pointerCalls'],5)
        self.assertEqual(1,len(value['actor']['creates']));self.assertEqual(1,len(value['actor']['deletes']))
        self.assertEqual([],value['actor']['rows']);self.assertEqual(0,value['actor']['timers'])
        self.assertEqual('Cube',value['actor']['creates'][0]['properties']['shape'])


if __name__=='__main__':unittest.main()
