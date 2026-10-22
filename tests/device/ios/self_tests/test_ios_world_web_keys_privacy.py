"""Global original input lifetime privacy, with independent legacy producers.

The Qt dispatch/native boundary is modeled. Native source inspection below is
a source contract check, not compilation or device qualification.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
from pathlib import Path
import unittest

from adapters.normal_ui import NativeUIError
from ios.adapters import world_web_keys as keys
from ios.self_tests.test_ios_world_web_keys import QtKeys,LegacyQtKeys


class WorldWebKeysPrivacyTests(unittest.TestCase):
    def test_current_originals_keep_only_actual_preedit_activity_and_opaque_press_lifetimes(self):
        qt=QtKeys();private='dummy-controlled-secret-東京'
        first=qt.enter('key-press',text=private);qt.finish(first);qt.finish(qt.enter('key-release',text=private))
        second=qt.enter('key-press',text=private);qt.finish(second);qt.finish(qt.enter('key-release',text=private))
        qt.finish(qt.enter('input-method',commit=private,preedit=private));original=qt.packet()
        keys.privacy_qualified(original);self.assertNotIn(private,json.dumps(original,ensure_ascii=False))
        self.assertNotEqual(first['detail']['keyId'],second['detail']['keyId'])
        self.assertEqual({'preeditActive':True},original['source']['dispatches'][-1]['detail'])
        with self.assertRaises(NativeUIError):keys.drained(original)
        qt.finish(qt.enter('input-method',commit=private));after=qt.packet();keys.privacy_qualified(after);keys.drained(after)
        self.assertNotIn(private,json.dumps(after,ensure_ascii=False))

    def test_genuine_legacy_sources_keep_their_old_version_and_cannot_qualify_current_privacy(self):
        qt=LegacyQtKeys();qt.finish(qt.enter('input-method',commit='dummy-old-controlled-input'))
        packet=qt.packet();before=deepcopy(packet);keys.original(packet);keys.drained(packet)
        self.assertEqual(before,packet)
        with self.assertRaises(NativeUIError):keys.privacy_qualified(packet)
        changed=deepcopy(packet);changed['iosWorldWebKeysVersion']=2
        with self.assertRaises(NativeUIError):keys.original(changed)
        changed['source']['iosWorldWebKeySourceVersion']=2
        with self.assertRaises(NativeUIError):keys.original(changed)

    def test_current_closed_details_refuse_character_or_key_code_payloads(self):
        qt=QtKeys();qt.finish(qt.enter('key-press'));packet=qt.packet()
        for key,value in (('text','dummy-private-input'),('key',65),('scanCode',4),('virtualKey',65)):
            broken=deepcopy(packet);broken['source']['dispatches'][0]['detail'][key]=value
            with self.subTest(key=key),self.assertRaises(NativeUIError):keys.privacy_qualified(broken)
        qt=QtKeys();qt.finish(qt.enter('input-method'));packet=qt.packet()
        for key in ('commit','preedit','replacementLength'):
            broken=deepcopy(packet);broken['source']['dispatches'][0]['detail'][key]='dummy-private-input'
            with self.subTest(key=key),self.assertRaises(NativeUIError):keys.privacy_qualified(broken)

    def test_opaque_ids_cannot_be_reused_for_a_later_press_or_reassigned_inside_nested_notify(self):
        qt=QtKeys();qt.finish(qt.enter('key-press'));qt.finish(qt.enter('key-release'))
        qt.finish(qt.enter('key-press'));qt.finish(qt.enter('key-release'));packet=qt.packet()
        reused=packet['source']['dispatches'][0]['detail']['keyId']
        for row in packet['source']['dispatches'][2:]:row['detail']['keyId']=reused
        packet['source']['ended'][1]['keyId']=reused
        with self.assertRaises(NativeUIError):keys.original(packet)
        qt=QtKeys();outer=qt.enter('key-press');inner=qt.enter('key-press',batch=outer['batch'])
        qt.finish(inner);qt.finish(outer);packet=qt.packet();packet['source']['dispatches'][1]['detail']['keyId']='f'*32
        with self.assertRaises(NativeUIError):keys.original(packet)

    def test_native_source_exposes_no_character_accessor_or_raw_key_code_output(self):
        path=Path(__file__).resolve().parents[2]/'native'/'IOSWorldWebKeysObservation.h';source=path.read_text()
        for forbidden in ('commitString()', 'input->text()', 'nativeVirtualKey()', '{"text",', '{"key",', '{"scanCode",', '{"virtualKey",'):
            with self.subTest(accessor=forbidden):self.assertNotIn(forbidden,source)
        self.assertIn('!input->preeditString().isEmpty()',source)
        self.assertIn('keyId=nonce();_physicalKeys.insert(physical,keyId)',source)
        self.assertIn('_physicalKeys.erase(found)',source)


if __name__=='__main__':unittest.main()
