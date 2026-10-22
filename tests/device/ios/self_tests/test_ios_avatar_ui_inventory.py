"""Optional retained-root DTO; actual host weak roots at a synthetic Qt seam."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import gc
import json
from pathlib import Path
import unittest
import weakref
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from ios.adapters import avatar_ui_inventory as inventory,normal_input,avatar_controls
from ios.self_tests.test_ios_avatar_controls import Boundary


def row(role='avatar'):
    return dict(rootId='00000000-0000-4000-8000-000000000001',qmlSource='qrc:/qml/hifi/'+('AvatarApp.qml' if role=='avatar' else 'Pal.qml'),
        role=role,visible=False,enabled=False,attached=False,windowPresent=False,
        panels=dict.fromkeys(('popup','favorite','settings','wearables') if role=='avatar' else ('connection',),False))


class AvatarUiInventoryTests(unittest.TestCase):
    def widgets(self,roots=(),complete=True):
        source=Boundary();source.shown=False;value=source.observed()
        value['avatarInventory']=dict(iosAvatarUiInventoryVersion=1,complete=complete,roots=deepcopy(list(roots)));return value
    def test_hidden_detached_live_host_root_still_blocks_absence_until_actual_weak_death(self):
        class Root:pass
        root=Root();root.original=row();held=root;weak=weakref.ref(root)
        def snapshot():return self.widgets([] if weak() is None else [weak().original])
        del root;gc.collect();value=snapshot();self.assertFalse(inventory.absent(value))
        self.assertFalse(value['avatarInventory']['roots'][0]['visible']);self.assertFalse(value['avatarInventory']['roots'][0]['attached'])
        del held;gc.collect();self.assertTrue(inventory.absent(snapshot()))
    def test_optional_component_preserves_legacy_controls_and_real_normal_transport_keeps_raw_original(self):
        legacy=Boundary().observed();normal_input.observation(legacy,42,legacy['sampleEpochMs'])
        with self.assertRaises(NativeUIError):inventory.absent(legacy)
        value=self.widgets([row('people')]);normal_input.observation(value,42,value['sampleEpochMs'])
        projected=avatar_controls.project(value);self.assertFalse(projected['open']);self.assertEqual([],projected['controls'])
        self.assertFalse(inventory.absent(value))
        boundary=Boundary();boundary.shown=False;original=boundary.observed
        boundary.observed=lambda:original()|dict(avatarInventory=deepcopy(value['avatarInventory']))
        with patch.object(normal_input,'urlopen',boundary.post):
            native=boundary.input();captured=native.capture()
        self.assertEqual(value['avatarInventory'],captured['avatarInventory'])
        self.assertEqual(captured,native.last_receipt['observation'])
        self.assertEqual(['observe'],[command['operation'] for command in boundary.requests])
    def test_incomplete_empty_bad_profile_duplicate_identity_and_verdict_fields_never_become_absence(self):
        with self.assertRaises(NativeUIError):inventory.absent(self.widgets(complete=False))
        for fault in ('version','duplicate','role','source','panels','verdict'):
            value=self.widgets([row()]);packet=value['avatarInventory'];root=packet['roots'][0]
            if fault=='version':packet['iosAvatarUiInventoryVersion']=True
            elif fault=='duplicate':packet['roots'].append(deepcopy(root))
            elif fault=='role':root['role']='people'
            elif fault=='source':root['qmlSource']='https://foreign.invalid/AvatarApp.qml'
            elif fault=='panels':root['panels']['settings']=1
            else:root['fullyClean']=True
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):inventory.validate(packet)
    def test_native_source_retains_real_QPointers_and_surveys_them_before_visible_control_filter(self):
        root=Path(__file__).resolve().parents[4]
        source=(root/'ios/ui/IOSNormalUiInput.cpp').read_text();header=(root/'tests/device/native/IOSAvatarUiInventory.h').read_text()
        self.assertIn('_avatarRoots.insert(node,node)',source);self.assertIn('if (!it.value()) { it=_avatarRoots.erase(it);continue; }',source)
        self.assertLess(source.index('const auto retainedAvatarRoots=_avatarRoots.values()'),source.index('QHash<QString, Control> controls;'))
        self.assertIn('avatarInventory.visit(node)',source);self.assertIn('avatarRootId(item)',header)
        self.assertIn('object->property("visible")',header);self.assertIn('Q_OS_IOS',header);self.assertIn('--testScript',header)


if __name__=='__main__':unittest.main()
