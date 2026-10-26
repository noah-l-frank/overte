"""Unresolved Audio ownership blocks SDK work using actual private journals."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.adapters.audio_session_owners import owners_absent,ensure_released,register_scope,installed_entry
from ios.self_tests.test_ios_create_files import BINDING
from ios.self_tests.test_ios_installed_adapter import InstalledAdapterTests
from ios.adapters.audio_runtime import IOSAudioRuntime
from ios.self_tests.test_ios_audio_recorded_owner import Model,RUN


class AudioSessionOwnerTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name);self.root.chmod(0o700)
        self.adapter=SimpleNamespace(state_path=lambda _:self.root/'session.json')
    def test_empty_ownership_check_is_readonly_and_does_not_create_locks(self):
        before=list(self.root.iterdir());self.assertTrue(owners_absent(self.adapter,'owned'))
        self.assertTrue(ensure_released(self.adapter,'owned'));self.assertEqual(before,list(self.root.iterdir()))
    def test_partial_or_malformed_owner_and_orphan_original_are_never_absence(self):
        for name in ('ios-audio-recorded-owner.json','ios-audio-pcm-lease.json','ios-audio-recorded-orphan.json','ios-audio-unknown.json'):
            path=self.root/name;PrivateFeatureState(path).write(dict(original='unretired'),None)
            self.assertFalse(owners_absent(self.adapter,'owned'))
            with self.assertRaises(NativeUIError):ensure_released(self.adapter,'owned')
            self.assertEqual(dict(original='unretired'),PrivateFeatureState(path).read());path.unlink()
    def test_external_artifact_scope_remains_known_after_operation_owner_is_lost(self):
        external=self.root/'external';external.mkdir(mode=0o700)
        value=register_scope(self.adapter,'owned',BINDING,'a'*32,external)
        self.assertEqual(str(external),value['artifactRoot']);self.assertFalse(owners_absent(self.adapter,'owned'))
        self.assertEqual(value,register_scope(self.adapter,'owned',BINDING,'a'*32,external))
        with self.assertRaises(NativeUIError):register_scope(self.adapter,'owned',BINDING,'b'*32,external)
        with self.assertRaises(NativeUIError):ensure_released(self.adapter,'owned')
    def test_entry_barrier_precedes_the_actual_body(self):
        calls=[]
        class Adapter:
            state_path=self.adapter.state_path
            @installed_entry
            def act(self,selector):calls.append(selector)
        # Use the already bound instance function without creating a different
        # selector directory or a source/SDK context.
        instance=Adapter();instance.state_path=self.adapter.state_path
        PrivateFeatureState(self.root/'ios-audio-recorded-owner.json').write(dict(original='unretired'),None)
        with self.assertRaises(NativeUIError):instance.act('owned')
        self.assertEqual([],calls)

    def test_actual_runtime_registers_external_scope_before_input_session_and_retains_failure(self):
        model=Model();native=model.reader();entered=[];runtime=object.__new__(IOSAudioRuntime)
        runtime.adapter=self.adapter
        runtime._sources=lambda _:dict(clock_source=native,native=model,binding=BINDING,
            client=object(),session='owned',check=model.guard)
        external=self.root/'external';external.mkdir(mode=0o700)
        @contextmanager
        def existing(_selector):
            self.assertFalse(owners_absent(self.adapter,'owned'))
            self.assertEqual(str(external),PrivateFeatureState(self.root/'ios-audio-scope.json').read()['artifactRoot'])
            self.assertEqual([],model.native.commands);entered.append(True);yield
        runtime.existing_input_session=existing
        with self.assertRaisesRegex(RuntimeError,'retained failure'):
            with runtime.recorded_owner('owned',RUN,external,model.client()) as owner:
                self.assertEqual(external,owner.root);raise RuntimeError('retained failure')
        self.assertFalse(owners_absent(self.adapter,'owned'));self.assertEqual([True],entered)
        with self.assertRaises(NativeUIError):
            with runtime.recorded_owner('owned','b'*32,external,model.client()):self.fail('foreign run entered')
        self.assertEqual([True],entered);self.assertEqual([],model.native.commands)


class AudioInstalledAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.f=InstalledAdapterTests('test_canonical_subclass_emits_identity_only_after_measured_bytes_and_clean_sources')
        self.f.setUp();self.addCleanup(self.f.doCleanups);self.f.adapter.describe('test-only')
    def test_recorded_or_pcm_responsibility_refuses_all_ordinary_entrypoints_before_sdk(self):
        f=self.f;store=PrivateFeatureState(f.root/'ios-audio-recorded-owner.json');store.write(dict(original='unretired'),None)
        before=(f.sessions,f.launches,f.preflights,deepcopy(f.commands),deepcopy(f.process),f.adapter.read_session('test-only'))
        for action in (lambda:f.adapter.describe('test-only'),lambda:f.adapter.invoke('test-only','app.stop',{}),
                       lambda:f.adapter.cleanup('test-only'),lambda:f.adapter.cleanup_components('test-only')):
            with self.assertRaises(NativeUIError):action()
            self.assertEqual(before,(f.sessions,f.launches,f.preflights,f.commands,f.process,f.adapter.read_session('test-only')))
        self.assertFalse(f.adapter.component_owners_absent('test-only'));self.assertEqual(dict(original='unretired'),store.read())
    def test_no_audio_ownership_preserves_existing_canonical_cleanup(self):
        self.assertEqual(dict(cleaned=True),self.f.adapter.cleanup('test-only'));self.assertIsNone(self.f.process)
