"""Actual production inventory decoder, preserving literal historical v1."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from adapters.normal_ui import NativeUIError
from adapters.script_ui_inventory import validate,ui_state
from ios.self_tests.world_web_ui_roots_fixture import Root,RootCensus
from self_tests.test_script_manager_status import observed
from self_tests.test_script_ui_inventory import inventory,snapshot


class ScriptUiInventoryRootsTests(unittest.TestCase):
    def test_literal_v1_retains_original_shape_and_never_manufactures_root_ownership(self):
        original=inventory([observed(rootVisible=False,labelVisible=False)])
        self.assertIs(original,validate(original,pid=31,epoch=20000))
        self.assertNotIn('rootOwnership',original)
        self.assertFalse(ui_state(snapshot(original))['open'])
        for edit in ({'rootOwnership':{}},{'rootMembership':{}},{'inventoryVersion':True}):
            with self.subTest(edit=edit),self.assertRaises(NativeUIError):validate(dict(original,**edit))

    def test_current_inventory_joins_exact_walk_operand_and_original_native_process_clock(self):
        census=RootCensus();root=Root('manager');identity=census.observe(root);source=census.source()
        original=inventory([observed(componentSource=root.source)],inventoryVersion=2,rootOwnership=source,
            rootMembership=dict(managers=[identity],pickers=[]))
        self.assertIs(original,validate(original,pid=31,epoch=source['capturedEpochMs']))
        self.assertTrue(ui_state(snapshot(original))['open'])
        for edit in ('foreign-pid','old-clock','root-missing','membership-missing','legacy-relabel','member-duplicate'):
            value=deepcopy(original);pid=31;epoch=source['capturedEpochMs']
            if edit=='foreign-pid':pid=53
            elif edit=='old-clock':epoch+=1501
            elif edit=='root-missing':del value['rootOwnership']
            elif edit=='membership-missing':del value['rootMembership']
            elif edit=='legacy-relabel':value['inventoryVersion']=1
            else:value['rootMembership']['managers']*=2
            with self.subTest(edit=edit),self.assertRaises(NativeUIError):validate(value,pid=pid,epoch=epoch)

    def test_incomplete_scan_retains_weak_original_and_cannot_qualify_closed_ui(self):
        census=RootCensus();root=Root('manager');census.observe(root)
        original=inventory(complete=False,inventoryVersion=2,rootOwnership=census.source(ready=False),
            rootMembership=dict(managers=[],pickers=[]))
        self.assertTrue(validate(original,pid=31)['rootOwnership']['roots'][0]['weakAlive'])
        with self.assertRaises(NativeUIError):ui_state(snapshot(original))


if __name__=='__main__':unittest.main()
