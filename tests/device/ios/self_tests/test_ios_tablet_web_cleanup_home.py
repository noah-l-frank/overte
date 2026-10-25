"""Independent cleanup input ownership never changes generic manager flags."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from types import SimpleNamespace
import unittest
from adapters.normal_ui import NativeUIError
from adapters.token_script_ui import TokenScriptUI
from ios.adapters.tablet_web_cleanup import TabletWebCleanupAppOwner
from ios.self_tests.world_web_ui_roots_fixture import Root,RootCensus
from self_tests.test_token_script_ui import NativeBoundary
from self_tests.test_script_manager_status import observed


class TabletCleanupHomeTests(unittest.TestCase):
    def fixture(self):
        native=NativeBoundary();native.opened=True;root=Root('manager');census=RootCensus();identity=census.observe(root)
        capture=native.capture
        def snapshot():
            value=capture();visible=native.opened and native.page=='scripts'
            value.update(fileControlsVersion=1,scriptInventory=dict(inventoryVersion=2,complete=True,tabletPresent=True,tabletShown=native.opened,
                managers=[observed(componentSource=root.source,rootVisible=visible,labelVisible=visible)],pickers=[],rootOwnership=census.source(),
                rootMembership=dict(managers=[identity],pickers=[])))
            return value
        native.capture=snapshot;ui=TokenScriptUI(native,monotonic=lambda:native.clock,sleep=native.sleep)
        flags=dict(tabletOwned=False,managerOwned=False);manager=SimpleNamespace(state=flags,require_current=lambda:True,ui=ui,
            open=lambda:self.fail('Generic manager may not adopt independently owned Home'),close_tablet=lambda:self.fail('No generic flag rewrite'))
        owner=object.__new__(TabletWebCleanupAppOwner);owner.base=SimpleNamespace(state=dict(operations=[dict(label='open-app-home-1',status='returned')]))
        owner.state=dict(operations=[]);return owner,manager,native
    def test_own_returned_Home_and_current_source_controls_enter_and_close_without_flag_adoption(self):
        owner,manager,native=self.fixture();original=deepcopy(manager.state)
        owner.open_manager(manager);self.assertEqual('scripts',native.page);self.assertEqual(original,manager.state)
        owner.state['operations'].append(dict(label='cleanup-open-manager-1',status='returned'))
        owner.close_manager(manager,'cleanup-open-manager-1');self.assertFalse(native.opened);self.assertEqual(original,manager.state)
        self.assertEqual(['scripts.entry','tablet.close'],native.inputs)
    def test_foreign_surface_or_missing_own_Home_cannot_enter_and_unknown_cleanup_entry_cannot_close(self):
        for fault in ('owner','surface','close'):
            owner,manager,native=self.fixture()
            if fault=='owner':owner.base.state['operations']=[]
            elif fault=='surface':native.page='foreign'
            else:native.page='scripts'
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):
                owner.close_manager(manager,'cleanup-open-manager-1') if fault=='close' else owner.open_manager(manager)
            self.assertEqual([],native.inputs)
    def test_never_loaded_scope_has_no_invented_Stop_and_issued_unknown_load_stays_blocked(self):
        calls=[];manager=SimpleNamespace(require_current=lambda:True,state=dict(source=None,loadAttempted=False),stop_source=lambda url:calls.append(url))
        TabletWebCleanupAppOwner.stop_source(manager,dict(directory='file:///private/owned'))
        self.assertEqual([],calls);manager.state['loadAttempted']=True
        with self.assertRaises(NativeUIError):TabletWebCleanupAppOwner.stop_source(manager,dict(directory='file:///private/owned'))
        self.assertEqual([],calls)


if __name__=='__main__':unittest.main()
