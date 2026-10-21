"""Full Script scope through the canonical candidate gate; SDK is synthetic."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from ios.self_tests import test_ios_installed_adapter as installed_fixture
from ios.adapters import appium_adapter
from ios.adapters.normal_scripts import PROFILE
from ios.adapters.script_runtime import IOSScriptRuntime
from adapters.normal_ui import NativeUIError
from feature_journeys.scenarios import VERSION


class IOSScriptRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.f=installed_fixture.InstalledAdapterTests('test_canonical_subclass_emits_identity_only_after_measured_bytes_and_clean_sources')
        self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.f.target.update(serverUrl='http://controlled.invalid:4723',normalScripts=dict(contractVersion=1,profile=PROFILE),
            nativeUiObservation=dict(kind='uikit-documents',version=1))
        self.f.adapter._state['targetFingerprint']=self.f.adapter.fingerprint()
        self.f.adapter.describe('test-only')
        self.calls=[];test=self
        def call(method,path,*_):test.calls.append((method,path));return {}
        self.client=SimpleNamespace(call=call,execute=self.f.adapter.client.execute)
        self.boundary=patch.object(appium_adapter,'WebDriver',return_value=self.client);self.boundary.start();self.addCleanup(self.boundary.stop)
        self.runtime=IOSScriptRuntime(self.f.adapter)

    def test_runtime_uses_real_candidate_scope_and_independent_native_clock_without_launch(self):
        sessions,launches=self.f.sessions,self.f.launches
        source=self.runtime._sources('test-only')
        self.assertEqual(dict(sourceRevision='a'*40,artifactSha256='e'*64,sessionId='test-only',generation=1,
            targetFingerprint=self.f.adapter.fingerprint(),processIdentity='42'),source['binding'])
        self.assertEqual(20000,source['native_clock']());self.assertEqual(20000,source['native'].native_epoch_ms())
        self.assertEqual((sessions,launches),(self.f.sessions,self.f.launches))
        self.assertEqual([('GET','/session/test-only')],self.calls)

    def test_candidate_replacement_fails_guard_before_original_native_input(self):
        source=self.runtime._sources('test-only');before=len(self.f.commands)
        self.f.artifact.write_bytes(b'foreign candidate bytes')
        with self.assertRaises(ValueError):source['check']()
        with self.assertRaises((RuntimeError,ValueError)):source['native'].capture()
        self.assertEqual(before,len(self.f.commands))

    def test_lost_sdk_session_does_not_recreate_or_change_original_owners(self):
        original=self.f.adapter._binding_store('test-only').read();sessions=self.f.sessions
        def lost(*_):raise RuntimeError('synthetic lost SDK result')
        self.client.call=lost
        with self.assertRaises(RuntimeError):self.runtime._sources('test-only')
        self.assertEqual(original,self.f.adapter._binding_store('test-only').read())
        self.assertEqual(sessions,self.f.sessions)

    def test_existing_input_scope_restores_guard_and_rejects_replaced_session_generation(self):
        self.assertFalse(self.f.adapter._session_recreation_forbidden)
        with self.assertRaises(RuntimeError):
            with self.runtime.existing_input_session('test-only'):
                self.assertTrue(self.f.adapter._session_recreation_forbidden)
                self.f.adapter._state['generation']+=1
        self.assertFalse(self.f.adapter._session_recreation_forbidden)

    def test_full_script_stores_share_original_component_ownership_instead_of_parallel_managers(self):
        for name in ('script_store','script_files_store','script_restart_store','script_restart_inputs_store'):
            self.assertEqual(getattr(self.f.adapter,name)('test-only').path,getattr(self.runtime,name)('test-only').path)
        self.assertFalse(self.runtime._script_restart_handoff('test-only').component_only)
        self.assertTrue(self.runtime._script_restart_handoff('test-only').require_membership)
        self.assertFalse(self.runtime._script_restart_inputs('test-only').component_only)

    def test_arbitrary_nested_or_unjournalled_lifecycle_input_is_refused(self):
        for operation in ('app.stop','app.launch','app.install'):
            with self.assertRaises((RuntimeError,ValueError,TypeError)):
                self.runtime._lifecycle('test-only',operation)
        self.assertEqual(1,self.f.launches)

    def test_canonical_authentication_dispatch_still_checks_actual_candidate_and_existing_session(self):
        from ios.adapters import authentication_runtime,feature_configuration
        calls=[];run='a'*32
        def flow(selector,requested):
            calls.append((selector,requested));return SimpleNamespace(observe=lambda values:{'routing-test':values['runId']})
        runtime=SimpleNamespace(_authentication_feature=flow,_existing=self.runtime._existing)
        with patch.object(feature_configuration,'configuration',return_value={'test':'explicit'}), \
             patch.object(feature_configuration,'reader',return_value=object()), \
             patch.object(feature_configuration,'capabilities',return_value=['feature.authentication.observe']), \
             patch.object(authentication_runtime,'IOSAuthenticationRuntime',return_value=runtime):
            values=dict(contractVersion=VERSION,runId=run,afterSequence=0)
            self.assertEqual({'routing-test':run},self.f.adapter.invoke('test-only','feature.authentication.observe',values))
            self.assertEqual([('test-only',run)],calls)
            self.f.artifact.write_bytes(b'foreign candidate bytes')
            with self.assertRaises(ValueError):self.f.adapter.invoke('test-only','feature.authentication.observe',values)
            self.assertEqual(1,len(calls))

    def test_canonical_graphics_dispatch_uses_explicit_reader_policy_and_actual_binding(self):
        from ios.adapters import graphics_runtime,feature_configuration
        calls=[];run='a'*32;client=object();selected={'private-policy':'fixed'}
        def flow(selector,requested,**kwargs):
            calls.append((selector,requested,kwargs));return SimpleNamespace(observe=lambda values:{'routing-test':values['runId']})
        runtime=SimpleNamespace(_graphics_feature=flow,_existing=self.runtime._existing)
        with patch.object(feature_configuration,'configuration',return_value={'graphics':selected}), \
             patch.object(feature_configuration,'reader',return_value=client), \
             patch.object(feature_configuration,'capabilities',return_value=['feature.graphics.observe']), \
             patch.object(graphics_runtime,'IOSGraphicsRuntime',return_value=runtime):
            values=dict(contractVersion=VERSION,runId=run,afterSequence=0)
            self.assertEqual({'routing-test':run},self.f.adapter.invoke('test-only','feature.graphics.observe',values))
            self.assertEqual([('test-only',run,dict(role='primary',client=client,settings=selected))],calls)
            self.f.artifact.write_bytes(b'foreign candidate bytes')
            with self.assertRaises(ValueError):self.f.adapter.invoke('test-only','feature.graphics.observe',values)
            self.assertEqual(1,len(calls))

    def test_canonical_graphics_finalization_failure_never_falls_through_to_native_stop(self):
        from adapters.normal_feature_state import PrivateFeatureState
        from ios.adapters import graphics_session_retirement,feature_configuration
        original={'runId':'a'*32};path=self.f.adapter.state_path('test-only').with_name('ios-graphics-feature.json')
        PrivateFeatureState(path).write(original,None)
        config=dict(iosFeatureAdapterVersion=2,areas=['graphics'],graphics={'private-policy':'fixed'})
        transaction=SimpleNamespace(finalize=lambda:(_ for _ in ()).throw(RuntimeError('Pending paired ownership')))
        current=deepcopy(self.f.adapter._state);process=deepcopy(self.f.process)
        with patch.object(feature_configuration,'configuration',return_value=config), \
             patch.object(feature_configuration,'reader',return_value=object()), \
             patch.object(graphics_session_retirement,'IOSGraphicsSessionRetirement',return_value=transaction) as factory, \
             patch.object(self.f.adapter,'cleanup_components',return_value=True):
            with self.assertRaises(RuntimeError):self.f.adapter.cleanup('test-only')
            self.assertEqual(original,factory.call_args.args[4])
        self.assertEqual(current,self.f.adapter._state);self.assertEqual(process,self.f.process)
        self.assertEqual(original,PrivateFeatureState(path).read())

    def test_retired_candidate_scope_refuses_other_candidate_or_target_without_sdk_creation(self):
        _client,_session,_state,_target,scope=self.runtime._existing('test-only')
        self.assertEqual(self.f.target,self.f.adapter._retired_candidate_scope('test-only',scope))
        calls=len(self.calls)
        for fields in (dict(sourceRevision='b'*40),dict(artifactSha256='f'*64),dict(targetFingerprint='d'*64)):
            with self.assertRaises(ValueError):self.f.adapter._retired_candidate_scope('test-only',scope|fields)
        self.assertEqual(calls,len(self.calls))

    def test_normal_cleanup_still_reaches_original_teardown_if_component_inspection_raises(self):
        with patch.object(self.f.adapter,'cleanup_components',side_effect=RuntimeError('Unreadable original component')):
            with self.assertRaises(RuntimeError):self.f.adapter.cleanup('test-only')
        self.assertIsNone(self.f.process);self.assertIsNone(self.f.adapter._state)
        self.assertIsNotNone(self.f.adapter._binding_store('test-only').read())

    def test_historical_graphics_cleanup_cannot_hide_another_component_owner(self):
        from adapters.normal_feature_state import PrivateFeatureState
        from ios.adapters import graphics_session_retirement
        path=self.f.adapter.state_path('test-only')
        PrivateFeatureState(path.with_name('ios-feature-session-retired.json')).write({'runId':'a'*32},None)
        owner=self.f.adapter.chat_capture_store('test-only');owner.write({'unrelated':'owned'},None)
        store=self.f.adapter._binding_store('test-only');store.discard(store.read());self.f.adapter._state=None
        process=deepcopy(self.f.process)
        with patch.object(graphics_session_retirement.IOSGraphicsSessionRetirement,'from_receipt') as factory:
            with self.assertRaises(ValueError):self.f.adapter.cleanup('test-only')
            factory.assert_not_called()
        self.assertEqual(process,self.f.process);self.assertEqual({'unrelated':'owned'},owner.read())


if __name__=='__main__':unittest.main()
