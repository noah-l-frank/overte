"""Actual private Chat scope/session barriers; modeled installed SDK sources."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.adapters.chat_session_owners import owners_absent,ensure_released,register_scope,installed_entry
from ios.adapters.chat_draft_runtime import IOSChatDraftRuntime
from ios.self_tests.test_ios_chat_draft_owner import DraftModel,RUN,BINDING
from ios.self_tests.test_ios_installed_adapter import InstalledAdapterTests


class ChatSessionOwnerTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name);self.root.chmod(0o700)
        self.adapter=SimpleNamespace(state_path=lambda _:self.root/'session.json')
    def test_empty_check_has_no_source_session_or_file_mutation(self):
        before=list(self.root.iterdir());self.assertTrue(owners_absent(self.adapter,'owned'));self.assertTrue(ensure_released(self.adapter,'owned'))
        self.assertEqual(before,list(self.root.iterdir()))
    def test_partial_malformed_orphan_and_unknown_chat_ownership_remain_blocking(self):
        for name in ('ios-chat-draft-owner.json','ios-chat-draft-unknown.json','ios-chat-scope.json','ios-chat-future.json'):
            path=self.root/name;path.write_bytes(b'{');path.chmod(0o600)
            with self.assertRaises(NativeUIError):ensure_released(self.adapter,'owned')
            self.assertFalse(owners_absent(self.adapter,'owned'));self.assertEqual(b'{',path.read_bytes());path.unlink()
    def test_external_scope_remains_discoverable_and_cannot_change_run_or_root(self):
        external=self.root/'external';external.mkdir(mode=0o700)
        original=register_scope(self.adapter,'owned',BINDING,RUN,external)
        self.assertEqual(original,register_scope(self.adapter,'owned',BINDING,RUN,external));self.assertFalse(owners_absent(self.adapter,'owned'))
        for run,root in (('b'*32,external),(RUN,self.root)):
            with self.assertRaises(NativeUIError):register_scope(self.adapter,'owned',BINDING,run,root)
        self.assertEqual(original,PrivateFeatureState(self.root/'ios-chat-scope.json').read())
    def test_marker_write_failure_cannot_enter_input_session(self):
        model=DraftModel();entered=[];runtime=object.__new__(IOSChatDraftRuntime);runtime.adapter=self.adapter
        runtime._sources=lambda _:dict(clock_source=model.native_reader(),native=model,binding=BINDING,check=model.guard,
            observer=SimpleNamespace(chat_view=model.view_reader))
        @contextmanager
        def existing(_):entered.append(True);yield
        runtime.existing_input_session=existing
        from unittest.mock import patch
        with patch.object(PrivateFeatureState,'write',side_effect=OSError('Declared failed Chat scope CAS')):
            with self.assertRaises(OSError):
                with runtime.draft_owner('owned',RUN,self.root,model.client()):self.fail('entered without a scope')
        self.assertEqual([],entered);self.assertEqual([],model.widgets.calls)
    def test_runtime_registers_scope_before_input_and_keeps_the_original_failure(self):
        model=DraftModel();entered=[];runtime=object.__new__(IOSChatDraftRuntime);runtime.adapter=self.adapter
        runtime._sources=lambda _:dict(clock_source=model.native_reader(),native=model,binding=BINDING,check=model.guard,
            observer=SimpleNamespace(chat_view=model.view_reader))
        @contextmanager
        def existing(_):
            self.assertFalse(owners_absent(self.adapter,'owned'));self.assertEqual([],model.widgets.calls);entered.append(True);yield
        runtime.existing_input_session=existing
        with self.assertRaisesRegex(RuntimeError,'original scoped failure'):
            with runtime.draft_owner('owned',RUN,self.root,model.client()):raise RuntimeError('original scoped failure')
        self.assertEqual([True],entered);self.assertFalse(owners_absent(self.adapter,'owned'))
    def test_entry_guard_precedes_the_body(self):
        calls=[]
        class Adapter:
            @installed_entry
            def act(self,selector):calls.append(selector)
        adapter=Adapter();adapter.state_path=self.adapter.state_path
        PrivateFeatureState(self.root/'ios-chat-scope.json').write(dict(unretired=True),None)
        with self.assertRaises(NativeUIError):adapter.act('owned')
        self.assertEqual([],calls)


class ChatInstalledAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.f=InstalledAdapterTests('test_canonical_subclass_emits_identity_only_after_measured_bytes_and_clean_sources')
        self.f.setUp();self.addCleanup(self.f.doCleanups);self.f.adapter.describe('test-only')
    def test_retained_chat_refuses_ordinary_entries_components_and_sdk_cleanup(self):
        f=self.f;store=PrivateFeatureState(f.root/'ios-chat-draft-owner.json');store.write(dict(unretired=True),None)
        before=(f.sessions,f.launches,f.preflights,deepcopy(f.commands),deepcopy(f.process),f.adapter.read_session('test-only'))
        for action in (lambda:f.adapter.describe('test-only'),lambda:f.adapter.invoke('test-only','app.stop',{}),
                       lambda:f.adapter.cleanup('test-only'),lambda:f.adapter.cleanup_components('test-only')):
            with self.assertRaises(NativeUIError):action()
            self.assertEqual(before,(f.sessions,f.launches,f.preflights,f.commands,f.process,f.adapter.read_session('test-only')))
        self.assertFalse(f.adapter.component_owners_absent('test-only'));self.assertEqual(dict(unretired=True),store.read())
    def test_no_chat_ownership_preserves_canonical_cleanup(self):
        self.assertEqual(dict(cleaned=True),self.f.adapter.cleanup('test-only'));self.assertIsNone(self.f.process)


if __name__=='__main__':unittest.main()
