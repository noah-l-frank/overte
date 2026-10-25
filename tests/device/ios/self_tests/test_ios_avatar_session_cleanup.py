"""Canonical teardown fails closed on actual unresolved local Avatar owners."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.adapters import avatar_session_cleanup as cleanup,avatar_session_carriers as carriers
from ios.adapters.appium_adapter import WebDriver


class AvatarSessionCleanupTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup);self.root=Path(temporary.name);self.root.chmod(0o700)
        self.sdk_calls=[]
        self.adapter=SimpleNamespace(state_path=lambda _:self.root/'session.json',_target=lambda *_:self.sdk_calls.append('target'))
        config=patch('ios.adapters.feature_configuration.configuration',return_value=None);config.start();self.addCleanup(config.stop)
    def test_unrelated_session_without_avatar_carriers_uses_existing_teardown_unchanged(self):
        calls=[];entry=cleanup.session_entry(lambda adapter,target:calls.append(target) or {'performed':True})
        self.assertEqual({'performed':True},entry(self.adapter,'existing'));self.assertEqual(['existing'],calls)
        self.assertTrue(cleanup.ensure_finalized(self.adapter,'existing'));self.assertEqual([],self.sdk_calls)
    def test_actual_orphan_role_metadata_and_foreign_source_each_prevent_any_sdk_teardown(self):
        for name in ('ios-avatar-primary-feature.json','ios-avatar-actor-sources.json','avatar-unknown-original.json'):
            with self.subTest(name=name):
                path=PrivateFeatureState(self.root/name);path.write(dict(unqualified=True),None)
                self.assertTrue(cleanup.owned(self.adapter,'existing'))
                with self.assertRaises((NativeUIError,ValueError)):cleanup.ensure_finalized(self.adapter,'existing')
                self.assertEqual([],self.sdk_calls);self.assertEqual(dict(unqualified=True),path.read());path.discard(path.read())
    def test_slow_admission_scan_cannot_renew_original_canonical_teardown_deadline(self):
        clock=[0.];calls=[]
        def own(*_args):clock[0]=60.;return True
        entry=cleanup.session_entry(lambda *_:calls.append('sdk'),monotonic=lambda:clock[0])
        with patch.object(cleanup,'owned',side_effect=own),self.assertRaises(NativeUIError):entry(self.adapter,'existing')
        self.assertEqual([],calls)
    def test_nested_budget_and_last_actual_sdk_guard_keep_first_deadline(self):
        clock=[0.];sent=[];client=WebDriver('http://127.0.0.1:1')
        import ios.adapters.appium_adapter as sdk
        original=sdk.json.dumps
        def slow(*args,**kwargs):value=original(*args,**kwargs);clock[0]=60.;return value
        with self.assertRaises(NativeUIError),cleanup.budget(self.adapter,'existing',monotonic=lambda:clock[0]):
            clock[0]=59.
            with cleanup.budget(self.adapter,'existing',monotonic=lambda:clock[0]),patch.object(sdk.json,'dumps',side_effect=slow),patch.object(sdk,'urlopen',side_effect=lambda *_a,**_k:sent.append(True)):
                client.call('POST','/session',{})
        self.assertEqual([],sent)
    def test_carrier_inventory_requires_actual_read_membership_and_refuses_hardlink(self):
        path=PrivateFeatureState(self.root/'avatar-orphan-original.json');path.write(dict(original=True),None)
        self.assertEqual({path.path},carriers.inventory({self.root}))
        with self.assertRaises(NativeUIError):carriers.covered(self.root,{self.root},set())
        carriers.covered(self.root,{self.root},{path.path})
        import os
        os.link(path.path,self.root/'same-inode.json')
        with self.assertRaises(NativeUIError):carriers.inventory({self.root})


if __name__=='__main__':unittest.main()
