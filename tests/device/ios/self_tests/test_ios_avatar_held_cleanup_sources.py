"""Explicit v2 uses unchanged actual source and retained hidden panel operands."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from adapters.normal_ui import NativeUIError
from ios.adapters.avatar_cleanup_sources import restored_held
from ios.adapters.avatar_observation import source_history
from ios.self_tests import test_ios_avatar_cleanup_sources as fixture


class AvatarHeldCleanupSourcesTests(unittest.TestCase):
    def setUp(self):
        self.f=fixture.AvatarCleanupSourcesTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        source=self.f.f.fixture;old=source.widget.observed
        self.root=dict(rootId=source.widget.root(),qmlSource='file:///app.bundle/qml/hifi/AvatarApp.qml',role='avatar',
            visible=False,enabled=False,attached=False,windowPresent=False,panels=dict(popup=False,favorite=False,settings=False,wearables=False))
        def observed():
            value=old();value['avatarInventory']['roots']=[deepcopy(self.root)];return value
        source.widget.observed=observed
    def measure(self):
        owner=self.f.f.source;sources=source_history(owner.previous,None,store=owner.store,root=owner.root,binding=owner.binding,
            run=owner.run,role=owner.role,lock=owner.lock)
        return restored_held(sources,self.f.baseline,len(sources.frames),fixture_url=owner.phase.fixture_url,expected_code=fixture.EXPECTED)
    def test_actual_hidden_detached_root_is_held_in_two_and_never_absence_in_one(self):
        self.f.f.source.read();value=self.measure();self.assertEqual(2,value['avatarCleanupSourcesVersion'])
        holders=value['panelDisposition']['holders'];self.assertEqual(1,len(holders));self.assertEqual('qt-root',holders[0]['kind'])
        self.assertEqual(self.root,holders[0]['original']['roots'][0]);self.assertNotIn('destroyed',holders[0]['original'])
        with self.assertRaises(NativeUIError):self.f.measure()
    def test_actual_visible_or_modal_panel_is_not_quiet_and_cannot_be_only_a_process_hold(self):
        for fault in ('visible','popup'):
            if fault=='visible':self.root['visible']=True
            else:self.root.update(visible=False);self.root['panels']['popup']=True
            self.f.f.source.read()
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):self.measure()


if __name__=='__main__':unittest.main()
