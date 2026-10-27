"""Opt-in v4 uses the same verified installed session and native transports."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import unittest
from unittest.mock import patch
from adapters.native_script_roots import NativeScriptRoots
from adapters.normal_ui import NativeUIError
from adapters.script_feature.lock import ScriptSourceLock
from ios.adapters.chat_draft_runtime import IOSChatDraftRuntime
from ios.adapters.chat_script_sources import IOSChatScriptSources
from ios.adapters.chat_session_owners import owners_absent
import ios.self_tests.test_ios_keyboard_runtime as keyboard_fixture
from ios.self_tests.chat_source_bound_fixture import SourceBoundMessageModel
from ios.self_tests.chat_script_source_fixture import RUN


class ChatSourceBoundRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.k=keyboard_fixture.KeyboardRuntimeTests();self.k.setUp();self.addCleanup(self.k.doCleanups);self.f=self.k.f
        self.runtime=IOSChatDraftRuntime(self.f.adapter);self.root=self.f.root/'chat-source-artifacts';self.root.mkdir(mode=0o700)
        self.client=SourceBoundMessageModel().client()
    def test_existing_installed_factory_pins_source_profile_before_input_and_restores_scope_on_error(self):
        before=self.f.sessions,self.f.launches;owner=None
        with self.assertRaisesRegex(RuntimeError,'original source-bound failure'):
            with self.runtime.draft_owner('test-only',RUN,self.root,self.client,source_bound=True) as owner:
                self.assertEqual(4,owner.version);self.assertTrue(owner.source_bound)
                self.assertIsInstance(owner.code_roots,NativeScriptRoots);self.assertIsInstance(owner.code_sources,IOSChatScriptSources)
                self.assertFalse(owners_absent(self.f.adapter,'test-only'))
                self.assertTrue(self.f.adapter._session_recreation_forbidden)
                # A source query outside a durably owned observation is refused
                # before it can reach the HTTP sender or native getter.
                with self.assertRaises(NativeUIError):owner.code_sources.send(dict(schemaVersion=1,commandId='ios-'+'c'*32,
                    action='feature-ios-chat-script-sources',runId=RUN))
                raise RuntimeError('original source-bound failure')
        self.assertIsNotNone(owner);self.assertFalse(self.f.adapter._session_recreation_forbidden)
        self.assertEqual(before,(self.f.sessions,self.f.launches))
        self.assertEqual(owner.code_roots.send.__self__,owner.code_sources.send.__self__)
    def test_changed_installed_artifact_refuses_before_source_owner_or_input_session(self):
        before=self.f.sessions,self.f.launches;self.f.artifact.write_bytes(b'foreign candidate')
        with self.assertRaises((ValueError,RuntimeError)):
            with self.runtime.draft_owner('test-only',RUN,self.root,self.client,source_bound=True):self.fail('entered foreign candidate')
        self.assertEqual(before,(self.f.sessions,self.f.launches));self.assertFalse(self.f.adapter._session_recreation_forbidden)
    def test_explicit_held_canonical_lock_is_shared_with_the_same_draft_owner(self):
        lock=ScriptSourceLock(self.runtime.state_path('test-only').with_name('script-feature-sources.lock'))
        before=self.f.sessions,self.f.launches
        with lock.held():
            with self.runtime.draft_owner('test-only',RUN,self.root,self.client,source_bound=True,lock=lock) as owner:
                self.assertIs(lock,owner.lock);lock.assert_held();self.assertEqual(4,owner.version)
            lock.assert_held()
        self.assertEqual(before,(self.f.sessions,self.f.launches))
    def test_explicit_unheld_or_foreign_lock_refuses_before_candidate_queries(self):
        path=self.runtime.state_path('test-only').with_name('script-feature-sources.lock')
        for lock in (ScriptSourceLock(path),ScriptSourceLock(path.with_name('foreign-lock'))):
            with self.subTest(path=lock.path),patch.object(self.runtime,'_sources',side_effect=AssertionError('No candidate query')),self.assertRaises(NativeUIError):
                with self.runtime.draft_owner('test-only',RUN,self.root,self.client,source_bound=True,lock=lock):self.fail('entered')
        self.assertTrue(owners_absent(self.f.adapter,'test-only'))


if __name__=='__main__':unittest.main()
