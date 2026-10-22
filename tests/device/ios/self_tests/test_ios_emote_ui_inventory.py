"""Actual DTO lifetime distinctions at modeled Qt boundaries; no native compile."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import uuid
import unittest
from adapters.normal_ui import NativeUIError
from adapters.token_emote_ui import TokenEmoteUI
from ios.adapters.emote_controls import IOSEmoteIO,project
from ios.adapters.emote_ui_inventory import validate,absent
from ios.adapters.normal_input import observation
from ios.self_tests.test_ios_emote_controls import NativeBoundary

ROOT=str(uuid.uuid4())


def inventory(*,roots=True,visible=True,attached=True):
    return dict(iosEmoteUiInventoryVersion=1,complete=True,roots=[dict(rootId=ROOT,
        qmlSource='qrc:/scripts/system/+android_phoneInterface/PhoneEmote.qml',activeName='',visible=visible,
        enabled=True,attached=attached,windowPresent=attached)] if roots else [])


class VisibilityBoundary(NativeBoundary):
    def __init__(self):
        super().__init__();self.oldShown=self.tablet;self.loginBirth=str(uuid.uuid4());self.living=False
    def capture(self):
        if self.oldShown!=self.tablet:self.loginBirth=str(uuid.uuid4());self.oldShown=self.tablet
        self.living=self.living or self.page
        value=super().capture();value.update(emoteControlsVersion=2,
            emoteInventory=inventory(roots=self.living,visible=self.tablet and self.page,attached=self.tablet))
        return value


class EmoteLifetimeTests(unittest.TestCase):
    def test_v2_source_birth_survives_real_tablet_visibility_and_page_transitions(self):
        native=VisibilityBoundary();io=IOSEmoteIO(native);birth=io.capture()['scope']['generation'];login=native.loginBirth
        native.tablet=False;closed=io.capture();self.assertEqual(birth,closed['scope']['generation']);self.assertNotEqual(login,native.loginBirth)
        native.tablet=True;ui=TokenEmoteUI(io,native.intent,monotonic=lambda:native.clock,sleep=native.sleep)
        ui.open();ui.play('Waving');ui.cancel();ui.close();native.tablet=False;after=io.capture()
        self.assertEqual(birth,after['scope']['generation']);self.assertFalse(after['open'])
        self.assertFalse(absent(native.capture())) # Cached/detached QObject still owns lifetime.
        native.living=False;self.assertTrue(absent(native.capture()))
    def test_hidden_detached_disabled_or_windowless_roots_cannot_be_empty_cleanup(self):
        native=VisibilityBoundary();value=native.capture()
        for field in ('visible','enabled','attached','windowPresent'):
            current=deepcopy(value);current['emoteInventory']=inventory();current['emoteInventory']['roots'][0][field]=False
            self.assertFalse(absent(current))
    def test_v1_controls_remain_readable_but_cannot_prove_root_absence(self):
        value=NativeBoundary().capture();project(value);observation(value,31,20000)
        with self.assertRaises(NativeUIError):absent(value)
    def test_missing_or_incomplete_v2_inventory_never_becomes_current_absence(self):
        value=VisibilityBoundary().capture()
        for mutate in (lambda v:v.pop('emoteInventory'),lambda v:v['emoteInventory'].update(complete=False),
                       lambda v:v['emoteInventory'].update(iosEmoteUiInventoryVersion=True)):
            current=deepcopy(value);mutate(current)
            with self.assertRaises((NativeUIError,KeyError)):absent(current)
    def test_duplicate_foreign_or_encoded_roots_are_refused(self):
        for mutate in (lambda v:v['roots'].append(deepcopy(v['roots'][0])),
                       lambda v:v['roots'][0].update(qmlSource='https://foreign/PhoneEmote.qml'),
                       lambda v:v['roots'][0].update(qmlSource='file:///app/scripts/system/%2e%2e/PhoneEmote.qml')):
            value=inventory();mutate(value)
            with self.assertRaises(NativeUIError):validate(value)
    def test_native_source_uses_dedicated_birth_and_weak_root_inventory_before_hit_testing(self):
        root=Path(__file__).resolve().parents[4];source=(root/'ios/ui/IOSNormalUiInput.cpp').read_text()
        self.assertIn('result["emoteGeneration"]=_emoteGeneration',source)
        self.assertNotIn('result["emoteGeneration"]=_loginGeneration',source)
        self.assertLess(source.index('emoteInventory.visit(node)'),source.index('const auto id = identify(node'))
        self.assertIn('if (root) { survey(root,0); }',source)

if __name__=='__main__':unittest.main()
