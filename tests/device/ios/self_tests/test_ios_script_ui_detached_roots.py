"""Current whole-tree membership differs from retained original weak lifetime."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import gc
import unittest
from adapters.normal_ui import NativeUIError
from adapters.script_ui_inventory import validate,ui_state
from ios.self_tests.world_web_ui_roots_fixture import Root,RootCensus
from self_tests.test_script_manager_status import observed
from self_tests.test_script_ui_inventory import inventory,snapshot


class ScriptUiDetachedRootTests(unittest.TestCase):
    def test_detached_live_original_is_retained_without_becoming_current_walk_member(self):
        census=RootCensus();root=Root('manager');identity=census.observe(root)
        before=inventory([observed(componentSource=root.source)],inventoryVersion=2,
            rootOwnership=census.source(),rootMembership=dict(managers=[identity],pickers=[]))
        validate(before,pid=31)
        after=inventory(inventoryVersion=2,rootOwnership=census.source(),rootMembership=dict(managers=[],pickers=[]))
        self.assertIs(after,validate(after,pid=31))
        self.assertFalse(ui_state(snapshot(after))['open'])
        self.assertEqual(identity,after['rootOwnership']['roots'][0]['observedIdentity'])
        self.assertTrue(after['rootOwnership']['roots'][0]['weakAlive'])
        self.assertEqual(before['rootOwnership']['roots'][0],after['rootOwnership']['roots'][0])

    def test_current_walk_requires_exact_actual_member_even_when_original_is_retained(self):
        census=RootCensus();root=Root('manager');identity=census.observe(root)
        original=inventory([observed(componentSource=root.source,rootVisible=False,labelVisible=False)],
            inventoryVersion=2,rootOwnership=census.source(),rootMembership=dict(managers=[identity],pickers=[]))
        validate(original,pid=31)
        for fault in ('missing-current-member','unknown-current-member','extra-current-member','wrong-source','expired-current-member'):
            value=deepcopy(original)
            if fault=='missing-current-member':value['rootMembership']['managers']=[]
            elif fault=='unknown-current-member':value['rootMembership']['managers']=['f'*32]
            elif fault=='extra-current-member':value['rootMembership']['managers'].append(identity)
            elif fault=='wrong-source':value['managers'][0]['componentSource']='qrc:/other/hifi/dialogs/TabletRunningScripts.qml'
            else:
                del root;gc.collect();value['rootOwnership']=census.source()
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):validate(value,pid=31)


if __name__=='__main__':unittest.main()
