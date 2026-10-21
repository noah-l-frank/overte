"""Canonical teardown must retain the last legitimate installed-byte cursor."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from ios.self_tests import test_ios_script_runtime as runtime_fixture
from ios.adapters.script_runtime import IOSScriptRuntime


class CleanupBindingTests(unittest.TestCase):
    def setUp(self):
        self.fixture=runtime_fixture.IOSScriptRuntimeTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.f,self.runtime=self.fixture.f,self.fixture.runtime
        self.store=self.f.adapter._binding_store('test-only');self.initial=self.store.read();self.seen=[]
        self.owner=self.runtime.script_feature_store('test-only');self.owner.write(dict(runId='a'*32),None)

    def finalizer(self,mutate=None,*,stop=False):
        def finalize():
            self.runtime._sources('test-only') # Actual canonical byte observer advances its original cursor.
            if stop:self.f.adapter.invoke('test-only','app.stop',{})
            current=self.store.read()
            if mutate is not None:
                changed=deepcopy(current);mutate(changed);self.store.write(changed,current)
            self.seen.append(self.store.read());self.owner.discard(self.owner.read());return {'performed':True}
        return SimpleNamespace(finalize=finalize)

    def cleanup(self,flow):
        with patch.object(IOSScriptRuntime,'_script_feature',return_value=flow):return self.f.adapter.cleanup('test-only')

    def test_feature_finalization_byte_observation_advances_before_canonical_binding_retirement(self):
        self.assertEqual({'cleaned':True},self.cleanup(self.finalizer()))
        self.assertGreater(self.seen[0]['observation']['sequence'],self.initial['observation']['sequence'])
        self.assertIsNone(self.store.read());self.assertIsNone(self.f.adapter.read_session('test-only'))

    def test_qualified_normal_stop_during_finalization_preserves_original_pid_and_retires_current_record(self):
        self.assertEqual({'cleaned':True},self.cleanup(self.finalizer(stop=True)))
        self.assertEqual('retired',self.seen[0]['phase']);self.assertEqual(self.initial['process'],self.seen[0]['process'])
        self.assertIsNone(self.store.read());self.assertIsNone(self.f.process)

    def reject_change(self,mutate):
        with self.assertRaises((ValueError,RuntimeError)):self.cleanup(self.finalizer(mutate))
        self.assertEqual(self.seen[0],self.store.read());self.assertIsNone(self.f.adapter.read_session('test-only'))

    def test_foreign_source_cannot_be_retired_after_original_sdk_teardown(self):
        self.reject_change(lambda row:row['source'].update(instance='f'*32))

    def test_new_session_generation_cannot_be_adopted_as_a_cleanup_cursor(self):
        self.reject_change(lambda row:row['scope'].update(generation=row['scope']['generation']+1))

    def test_foreign_pid_cannot_be_adopted_as_a_cleanup_cursor(self):
        def changed(row):row['process']['pid']+=1;row['observation']['processId']+=1
        self.reject_change(changed)

    def test_changed_original_native_bytes_cannot_be_retired_as_a_cursor_advance(self):
        self.reject_change(lambda row:row['observation']['bundle'].update(bundleSha256='f'*64))

    def test_new_nonce_with_reused_original_sequence_does_not_retire_binding(self):
        self.reject_change(lambda row:row['observation'].update(sequence=self.initial['observation']['sequence']))

    def test_boolean_session_generation_cannot_match_an_unchanged_integer_owner(self):
        def finalize():
            before=self.store.read();changed=deepcopy(before);changed['scope']['generation']=True
            self.store.write(changed,before);self.seen.append(changed);self.owner.discard(self.owner.read());return {'performed':True}
        with self.assertRaises((ValueError,RuntimeError)):self.cleanup(SimpleNamespace(finalize=finalize))
        self.assertEqual(self.seen[0],self.store.read());self.assertIsNone(self.f.adapter.read_session('test-only'))


if __name__=='__main__':unittest.main()
