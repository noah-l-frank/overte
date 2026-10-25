"""Actual Runtime/NativeInput transport, with explicit host weak Qt operands.

This exercises the modeled producer before its first raw reply. It does not
turn a legacy retained inventory into a current root-ownership original.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import gc
import unittest

from adapters import original_marker_holders
from adapters.normal_ui import NativeUIError
from ios.self_tests.avatar_final_domain import FinalDomain
from self_tests import test_account_provider as tls


class AvatarRuntimeScriptRootsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):tls.AccountProviderTests.setUpClass()
    @classmethod
    def tearDownClass(cls):tls.AccountProviderTests.tearDownClass()
    def setUp(self):self.d=FinalDomain(self)
    def capture(self,role):return self.d.runtime._sources(role)['native'].capture()

    def test_same_getter_preserves_original_private_login_input_receipt_order(self):
        for role,owner in self.d.owners.items():
            with self.subTest(role=role),owner.held():
                owner.initialize();owner.login()
                self.assertTrue(self.d.natives[role].account['loggedIn'])
                self.assertEqual(1,self.d.natives[role].input_log.count('login.submit'))
                owner.login()
                self.assertEqual(1,self.d.natives[role].input_log.count('login.submit'))

    def test_same_actual_manager_weak_operand_survives_hidden_worldless_runtime_capture(self):
        for role,scene in self.d.scenes.items():
            with self.subTest(role=role),self.d.owners[role].held():
                scene.domain.io.qt.page='scripts';scene.domain.io.qt.opened=True
                admitted=self.capture(role)['scriptInventory']
                self.assertEqual(2,admitted['inventoryVersion'])
                identity=admitted['rootMembership']['managers'][0]
                scene.domain.io.qt.page='home';scene.domain.io.qt.opened=False
                hidden=self.capture(role)
                self.assertEqual(2,hidden['scriptInventory']['inventoryVersion'])
                actual=original_marker_holders.ui('avatar',hidden['scriptInventory'],pid=31,epoch=hidden['sampleEpochMs'])
                self.assertEqual([],hidden['scriptInventory']['managers'])
                self.assertEqual([identity],[row['observedIdentity'] for row in actual['ownership']['roots'] if row['weakAlive']])
                self.assertTrue(actual['holders'])
                scene.domain.actual_roots.clear();gc.collect()
                ended=self.capture(role)
                actual=original_marker_holders.ui('avatar',ended['scriptInventory'],pid=31,epoch=ended['sampleEpochMs'],previous=actual['ownership'])
                self.assertFalse(actual['holders'])
                self.assertEqual(identity,actual['ownership']['roots'][0]['observedIdentity'])
                self.assertFalse(actual['ownership']['roots'][0]['weakAlive'])

    def test_current_incomplete_census_and_literal_legacy_cannot_prove_held_final_ui(self):
        role='primary';scene=self.d.scenes[role]
        with self.d.owners[role].held():
            before=self.capture(role);literal=deepcopy(before['scriptInventory'])
            literal={key:literal[key] for key in ('inventoryVersion','complete','managers','pickers','tabletPresent','tabletShown')}
            literal['inventoryVersion']=1
            with self.assertRaises(NativeUIError):original_marker_holders.ui('avatar',literal,pid=31,epoch=before['sampleEpochMs'])
            scene.domain.roots.complete=False
            current=self.d.natives[role].observed()
            self.assertFalse(current['scriptInventory']['rootOwnership']['complete'])
            with self.assertRaises(NativeUIError):self.capture(role)
            with self.assertRaises(NativeUIError):original_marker_holders.ui('avatar',current['scriptInventory'],pid=31,epoch=current['sampleEpochMs'])


if __name__=='__main__':unittest.main()
