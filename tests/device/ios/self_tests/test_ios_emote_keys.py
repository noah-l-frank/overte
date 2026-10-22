"""Actual immutable host ownership; Qt/UIKit/native producers are modeled."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import unittest
from adapters.normal_ui import NativeUIError
from ios.adapters.emote_keys import IOSEmoteKeys
from ios.self_tests import test_ios_emote_marker_scope as marker_fixture
from ios.self_tests.test_ios_emote_marker_owner import Domain
from ios.self_tests.emote_keys_fixture import KeyDomain


class EmoteKeysTests(unittest.TestCase):
    def setUp(self):
        self.fixture=marker_fixture.MarkerScopeTests();self.fixture.setUp();self.addCleanup(self.fixture.tearDown)
        self.scope=self.fixture.owner();self.domain=Domain(self.scope);self.boundary=KeyDomain(self.scope,self.domain)
        self.owner=self.boundary.owner()
    def quiet(self):
        self.scope.cleanup();indices=[]
        for _ in range(3):
            self.owner.capture();self.scope.capture('keys-quiet');indices.append(len(self.scope.frames));self.owner.capture();self.domain.sleep(1.55)
        self.scope.state['quiet']=indices;self.scope.save()
    def test_real_quiet_requires_global_key_ime_modifiers_and_owned_editor_root_absence(self):
        self.owner.capture();self.quiet();closure=self.owner.closed(self.scope)
        self.assertGreater(closure['last']['clockJoin']['nativeAfter']['capturedEpochMs'],closure['first']['clockJoin']['nativeAfter']['capturedEpochMs'])
        before=deepcopy(self.boundary.commands)
        archived=IOSEmoteKeys.archive(self.owner.store.read(),store=self.owner.store,root=self.scope.root,binding=self.owner.binding,
            run=self.owner.run,role=self.owner.role,lock=self.owner.lock)
        archived.closed(self.scope);self.assertEqual(before,self.boundary.commands)
        with self.assertRaises(NativeUIError):archived.capture()
    def test_held_key_pending_dispatch_ime_and_uikit_keyboard_each_block(self):
        self.owner.capture();self.quiet();self.owner.closed(self.scope)
        press=self.boundary.qt.enter('key-press');self.boundary.qt.finish(press);self.owner.capture()
        with self.assertRaises(NativeUIError):self.owner.closed(self.scope)
        release=self.boundary.qt.enter('key-release');self.owner.capture()
        with self.assertRaises(NativeUIError):self.owner.closed(self.scope)
        self.boundary.qt.finish(release);self.boundary.qt.finish(self.boundary.qt.enter('input-method',preedit='Ω'));self.owner.capture()
        with self.assertRaises(NativeUIError):self.owner.closed(self.scope)
        self.boundary.qt.finish(self.boundary.qt.enter('input-method',commit='Ω',preedit=''));self.boundary.keyboard=True;self.boundary.inset=120
        self.owner.capture()
        with self.assertRaises(NativeUIError):self.owner.closed(self.scope)
        self.boundary.keyboard=False;self.boundary.inset=0;self.quiet();self.owner.closed(self.scope)
    def test_unknown_query_return_is_not_resent_and_hooks_restore_before_recovery(self):
        self.owner.capture();self.boundary.fail_read=True;send,read=self.owner.keys.send,self.owner.keys.original
        with self.assertRaises(NativeUIError):self.owner.capture()
        self.assertEqual(send,self.owner.keys.send);self.assertEqual(read,self.owner.keys.original);before=deepcopy(self.boundary.commands)
        with self.assertRaises(NativeUIError):self.boundary.owner().capture()
        self.assertEqual(before,self.boundary.commands)
        self.boundary.fail_read=False;rebuilt=self.boundary.owner();rebuilt.abandon();rebuilt.capture()
        self.assertEqual(1,len(rebuilt.state['abandoned']))
    def test_geometry_loss_retains_actual_raw_key_floor_and_native_birth_cannot_reset(self):
        self.owner.capture();self.boundary.fail_geometry=True
        with self.assertRaises(NativeUIError):self.owner.capture()
        pending=deepcopy(self.owner.state['pending']);self.assertTrue(pending['wires']);self.boundary.fail_geometry=False
        self.owner.abandon();self.owner.capture();before=self.owner.store.read()
        # Coherent current native packet structure with another global key birth
        # still cannot discard the accepted original from the abandoned read.
        original_send=self.boundary.key_send
        def reset(query):
            original_send(query)
            import json
            value=json.loads(self.boundary.key_raw);value['source']['instance']='f'*32;self.boundary.key_raw=json.dumps(value)
        self.owner.keys.send=reset
        with self.assertRaises(NativeUIError):self.owner.capture()
        self.assertEqual(before['runId'],self.owner.store.read()['runId']);self.assertIsNotNone(self.owner.state['pending'])
    def test_valid_large_original_uses_immutable_files_without_expanding_metadata_limits(self):
        for _ in range(240):
            for kind in ('key-press','key-release'):
                row=self.boundary.qt.enter(kind);self.boundary.qt.finish(row)
        ref=self.owner.capture();original=self.owner.original(ref);wire=original['wire']
        self.assertGreater(wire['bytes'],400*1024);self.assertLess(self.owner.store.path.stat().st_size,48*1024)
        self.assertEqual(480,len(self.owner.packet(original)['source']['dispatches']))
        self.assertEqual('saved',wire['phase']);self.assertEqual([],self.owner.packet(original)['source']['down'])

    def test_stale_legacy_or_foreign_response_never_creates_an_original(self):
        from ios.self_tests.test_ios_world_web_keys import LegacyQtKeys
        legacy=LegacyQtKeys();legacy.finish(legacy.enter('input-method',commit='synthetic-private-marker'))
        stale=json.dumps(legacy.packet());read=self.owner.keys.original;responses=[stale,'{unfinished']
        def polling():return responses.pop(0) if responses else read()
        self.owner.keys.original=polling
        ref=self.owner.capture();item=self.owner.original(ref)
        self.assertEqual(1,len(item['wires']));self.assertEqual(1,self.owner.state['serial'])
        for path in self.scope.root.glob('emote-primary-keys-*'):
            if path.is_file():self.assertNotIn('synthetic-private-marker',path.read_text())

    def test_matching_unsafe_response_keeps_query_without_raw_artifact_or_resend(self):
        from ios.self_tests.test_ios_world_web_keys import LegacyQtKeys
        legacy=LegacyQtKeys();legacy.finish(legacy.enter('input-method',commit='synthetic-private-marker'))
        def unsafe(query):
            self.boundary.commands.append(deepcopy(query));value=legacy.packet()
            value.update(requestId=query['commandId'],runId=query['runId'],processId=int(self.owner.binding['processIdentity']))
            self.boundary.key_raw=json.dumps(value)
        self.owner.keys.send=unsafe
        with self.assertRaises(NativeUIError):self.owner.capture()
        pending=self.owner.state['pending'];self.assertIsNotNone(pending['query']);self.assertEqual([],pending['wires'])
        self.assertIsNone(pending['wire']);self.assertEqual(0,self.owner.state['serial'])
        self.assertEqual([],list(self.scope.root.glob('emote-primary-keys-*')))
        commands=deepcopy(self.boundary.commands)
        with self.assertRaises(NativeUIError):self.boundary.owner().capture()
        self.assertEqual(commands,self.boundary.commands)

    def test_hidden_but_live_owned_editor_root_blocks_even_with_empty_ime(self):
        self.owner.capture();self.quiet();self.owner.closed(self.scope)
        original=self.scope.live['native'].capture
        def retained_editor():
            value=original();value['scriptInventory']['pickers']=[dict(componentSource='qrc:/qml/dialogs/NativeFileBrowser.qml',
                visible=False,closing=False,requestId='',errorText='')]
            return value
        self.scope.live['native'].capture=retained_editor
        self.owner.capture();self.scope.capture('actual-hidden-editor');self.owner.capture()
        self.scope.state['quiet'][-1]=len(self.scope.frames);self.scope.save()
        with self.assertRaises(NativeUIError):self.owner.closed(self.scope)
        self.scope.live['native'].capture=original;self.quiet();self.owner.closed(self.scope)

    def test_actual_global_modifier_state_blocks_despite_empty_held_key_list(self):
        self.owner.capture();self.quiet();self.owner.closed(self.scope);packet=self.boundary.qt.packet
        def modified():
            value=packet();value['source']['qtModifiers']=0x02000000;return value
        self.boundary.qt.packet=modified;self.owner.capture()
        with self.assertRaises(NativeUIError):self.owner.closed(self.scope)
        self.boundary.qt.packet=packet;self.quiet();self.owner.closed(self.scope)
