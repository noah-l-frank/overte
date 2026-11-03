"""Literal Script open_manager through original native Qt Home delegates.

Qt controls are modeled producers; HTTP/AFC, NativeUI token checks, UIKit
callbacks and TokenScriptUI.open_manager remain production code. No returned
UI result, control expectation, Runtime factory or manager verifier is patched.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import time,unittest,weakref
from copy import deepcopy
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUI,NativeUIError,Locator
from adapters.token_script_ui import TokenScriptUI
from ios.adapters.normal_scripts import IOSScriptIO
from ios.adapters.avatar_runtime import IOSAvatarRuntime
from ios.adapters.avatar_controls import IOSAvatarIO,AvatarUI
from ios.self_tests.avatar_installed_full15_fixture import NativeInstalledFrontdoor
from ios.self_tests import test_ios_avatar_prepare_composed as preparation


class AvatarNativeTabletHomeTests(preparation.AvatarPrepareComposedTests):
    def component(self):
        f=NativeInstalledFrontdoor(self);d=f.domain;flow=d.owners['actor']
        return f,d,flow
    def controls(self,f):
        source=IOSAvatarRuntime(f.adapter)._sources('actor')
        nativeui=NativeUI(source['client'],source['session'],source['check'])
        io=IOSScriptIO(nativeui,source['native'])
        return source,io,TokenScriptUI(io,monotonic=time.monotonic,sleep=time.sleep)
    def test_actual_home_chrome_before_original_open_manager_enters_script_menu_once(self):
        f,d,flow=self.component();native=d.natives['actor'];world=d.scenes['actor'].domain
        with flow.held(paired=True):
            source,io,ui=self.controls(f);ui.open_tablet()
            self.assertTrue(any(row['id']=='tablet.home' for row in io.capture()['controls']))
            self.assertFalse(any(row['id']=='tablet.home' for row in world.io.capture()['controls']))
            ui.open_manager();self.assertTrue(ui.manager_visible());self.assertEqual('scripts',world.io.qt.page)
            self.assertEqual(1,native.input_log.count('tablet.home'))
            self.assertEqual(['scripts.menu','scripts.menu-edit','scripts.menu-running'],
                [name for name in world.io.qt.inputs if name.startswith('scripts.')])
            ui.activate('tablet.home');self.assertEqual('home',world.io.qt.page);self.assertEqual('home',native.menu)
            self.assertEqual(1,world.io.qt.inputs.count('tablet.home'))
            ui.close_tablet();ui.wait_tablet_absent()
    def test_home_from_actual_avatar_root_uses_widget_delegate_and_releases_same_visible_root(self):
        f,d,flow=self.component();world=d.scenes['actor'].domain;widget=d.widgets['actor']
        with flow.held(paired=True):
            source,io,ui=self.controls(f);ui.open_tablet()
            intents=PrivateFeatureState(f.root/'actual-avatar-input-intents.json')
            def intent(row):
                old=intents.read();rows=[] if old is None else old['inputs']
                intents.write(dict(inputs=rows+[deepcopy(row)]),old)
            avatar=AvatarUI(IOSAvatarIO(source['native']),intent,monotonic=time.monotonic,sleep=time.sleep)
            avatar.open('avatar');self.assertEqual('avatar',world.io.qt.page)
            old=weakref.ref(widget.current_root);self.assertIsNotNone(old())
            io.activate('tablet.home');self.assertEqual('home',world.io.qt.page);self.assertEqual('none',widget.dialog)
            self.assertIsNone(widget.current_root);self.assertIsNone(old())
            ui.open_manager();self.assertTrue(ui.manager_visible());ui.activate('tablet.home');ui.close_tablet()
    def test_stale_home_token_after_visible_root_reopen_refuses_before_either_producer_changes(self):
        f,d,flow=self.component();native=d.natives['actor'];world=d.scenes['actor'].domain
        with flow.held(paired=True):
            source,io,ui=self.controls(f);ui.open_tablet();original=io.capture()
            token=next(row['token'] for row in original['controls'] if row['id']=='tablet.home')
            ui.close_tablet();ui.wait_tablet_absent();ui.open_tablet();before=list(native.input_log);qt=list(world.io.qt.inputs)
            with self.assertRaises(NativeUIError):io.ui.click_with_token(Locator('accessibility id','OverteNavigation.tablet.home'),token)
            self.assertEqual(before,native.input_log);self.assertEqual(qt,world.io.qt.inputs)
            self.assertEqual('home',world.io.qt.page);ui.close_tablet()


if __name__=='__main__':unittest.main()
