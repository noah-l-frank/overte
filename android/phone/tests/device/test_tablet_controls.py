"""Ordinary tablet ownership counterexamples through its real public owner."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
import test_world_web_feature as world
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from overte_phone_tablet_controls import PhoneTabletControls


class UI:
    def __init__(self):self.visible=False;self.inputs=[];self.fail=None
    def tablet_visible(self):return self.visible
    def open_tablet(self):
        self.inputs.append('open')
        if self.fail!='ignored':self.visible=True
        if self.fail=='lost':raise NativeUIError('Lost original pointer return')
    def close_tablet(self):
        self.inputs.append('close')
        if self.fail!='ignored':self.visible=False
        if self.fail=='lost':raise NativeUIError('Lost original pointer return')


class TabletControlsTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.path=Path(self.temp.name);self.path.chmod(0o700)
        self.clock=world.Clock();self.ui=UI();self.store=PrivateFeatureState(self.path/'controls.json')
        self.binding=dict(sourceRevision='a'*40,artifactSha256='b'*64,processIdentity='123:456',sessionId='session',generation=1,targetFingerprint='c'*64)
    def flow(self,binding=None):return PhoneTabletControls(self.ui,self.store,binding or self.binding,lambda:True,monotonic=self.clock.now,sleep=self.clock.sleep)
    def test_normal_open_and_close_observe_original_ui_and_retire_host_owner(self):
        self.flow().open();self.flow().open();self.flow().close();self.flow().close()
        self.assertEqual(['open','close'],self.ui.inputs);self.assertIsNone(self.store.read());self.assertGreaterEqual(self.clock.now(),6)
    def test_native_ack_without_visible_open_cannot_become_active(self):
        self.ui.fail='ignored'
        with self.assertRaises(NativeUIError):self.flow().open()
        self.assertEqual('open-issued',self.store.read()['phase'])
    def test_lost_open_is_not_replayed_and_original_close_can_retire_it(self):
        self.ui.fail='lost'
        for _ in range(2):
            with self.assertRaises(NativeUIError):self.flow().open()
        self.ui.fail=None;self.flow().cleanup();self.assertEqual(['open','close'],self.ui.inputs);self.assertIsNone(self.store.read())
    def test_lost_close_resolves_only_from_original_absence_without_resend(self):
        self.flow().open();self.ui.fail='lost'
        with self.assertRaises(NativeUIError):self.flow().close()
        self.ui.fail=None;self.flow().close();self.assertEqual(['open','close'],self.ui.inputs)
    def test_foreign_tablet_or_replaced_candidate_cannot_be_adopted(self):
        self.ui.visible=True
        with self.assertRaises(NativeUIError):self.flow().open()
        with self.assertRaises(NativeUIError):self.flow().close()
        self.ui.visible=False;self.flow().open();replacement=deepcopy(self.binding);replacement['artifactSha256']='e'*64
        with self.assertRaises(NativeUIError):self.flow(replacement)
        self.assertEqual(['open'],self.ui.inputs)
    def test_late_visible_tablet_after_issued_close_cannot_be_green(self):
        self.flow().open();self.ui.fail='ignored'
        with self.assertRaises(NativeUIError):self.flow().close()
        with self.assertRaises(NativeUIError):self.flow().close()
        self.assertEqual(['open','close'],self.ui.inputs);self.assertEqual('close-issued',self.store.read()['phase'])


if __name__=='__main__':unittest.main()
