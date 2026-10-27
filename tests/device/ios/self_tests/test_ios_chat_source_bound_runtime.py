"""Opt-in v4 uses the same verified installed session and native transports."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import unittest
from adapters.native_script_roots import NativeScriptRoots
from adapters.normal_ui import NativeUIError
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


if __name__=='__main__':unittest.main()
