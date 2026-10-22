"""Selective catalog admission/dispatch and the real installed teardown gate.

Scene/whole proof is exercised by the composed owner suites. Here SDK sources
are explicit existing-session fakes; the finalizer spy tests gate ordering only.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import os
import unittest
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.adapters import feature_configuration as config
from ios.adapters.create_runtime import IOSCreateRuntime
from ios.adapters.normal_scripts import PROFILE
from ios.self_tests import test_ios_create_configuration as configuration_fixture
from ios.self_tests import test_ios_installed_adapter as installed_fixture
from ios.self_tests.test_ios_create_state import RUN


class CreateAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.h=configuration_fixture.ConfigurationTests();self.h.setUp();self.addCleanup(self.h.doCleanups)
        self.store=PrivateFeatureState(self.h.root/'adapter.json')
        self.value=dict(iosFeatureAdapterVersion=3,areas=['create'],fixtureConfig=str(self.h.root/'reader.json'),
            graphics=None,create=deepcopy(self.h.value))
        self.store.write(self.value,None)
        self.target=dict(physical=True,normalScripts=dict(contractVersion=1,profile=PROFILE),
            nativeUiObservation=dict(kind='uikit-documents',version=1),probe=dict(kind='ios-documents'),testBuild={'configured':True})
    def test_explicit_v3_create_admits_exactly_its_complete_triple_and_nothing_by_default(self):
        with patch.dict(os.environ,{'OVERTE_IOS_FEATURE_ADAPTER_CONFIG':str(self.store.path)}):
            self.assertEqual(self.value,config.configuration())
            self.assertEqual(['feature.create.act','feature.create.cleanup','feature.create.observe'],config.capabilities(self.target))
            for target in (self.target|dict(physical=False),self.target|dict(normalScripts=None)):
                with self.assertRaises(NativeUIError):config.capabilities(target)
        with patch.dict(os.environ):
            os.environ.pop('OVERTE_IOS_FEATURE_ADAPTER_CONFIG',None)
            self.assertEqual([],config.capabilities(self.target))
    def test_legacy_configuration_unknown_area_boolean_version_and_effect_fields_cannot_admit_create(self):
        for changed in (dict(iosFeatureAdapterVersion=2),dict(iosFeatureAdapterVersion=True),
                        dict(areas=['create','unknown-area']),dict(create=self.value['create']|dict(objects=[]))):
            value=self.value|changed;self.store.write(value,self.store.read())
            with self.subTest(changed=changed),self.assertRaises((NativeUIError,ValueError)):config.configuration(self.store.path)
        self.store.write(self.value,self.store.read());self.store.path.chmod(0o644)
        with self.assertRaises(NativeUIError):config.configuration(self.store.path)


class CreateInstalledRoutingTests(unittest.TestCase):
    def setUp(self):
        self.h=installed_fixture.InstalledAdapterTests();self.h.setUp();self.addCleanup(self.h.doCleanups)
        self.h.target['serverUrl']='http://controlled.invalid:4723'
        self.h.adapter._state['targetFingerprint']=self.h.adapter.fingerprint()
        self.h.adapter.describe('test-only')
    def test_actual_invoke_routes_the_validated_query_to_existing_create_runtime_without_script_fallback(self):
        # Candidate/installed bytes and the after-operation verify stay real in
        # this host fixture. Only the feature body's separate scene work is a spy.
        calls=[];query=dict(contractVersion=16,runId=RUN,ticket='b'*32,fixtureUrl='http://127.0.0.1:12345/feature-fixture/v1/runs/'+RUN+'/',verb='open',inputs={})
        class Flow:
            def act(_self,value):calls.append(('act',deepcopy(value)));return {'performed':True}
        settings={'private-source-settings':'opaque-for-routing-spy'}
        value=dict(iosFeatureAdapterVersion=3,areas=['create'],create=settings)
        def factory(runtime,selector,run,**kwargs):
            self.assertIsInstance(runtime,IOSCreateRuntime);self.assertIs(runtime.adapter,self.h.adapter)
            self.assertEqual(('test-only',RUN),(selector,run));self.assertEqual('primary',kwargs['role'])
            self.assertIs(settings,kwargs['settings']);calls.append(('factory',run));return Flow()
        with patch.object(config,'configuration',return_value=value),patch.object(config,'reader',return_value=object()),\
             patch.object(config,'capabilities',return_value=['feature.create.act']),\
             patch('ios.adapters.appium_adapter.WebDriver',return_value=self.h.adapter.client),\
             patch.object(self.h.adapter.client,'call',return_value={},create=True) as session_read,\
             patch.object(IOSCreateRuntime,'_create_feature',factory):
            self.assertEqual({'performed':True},self.h.adapter.invoke('test-only','feature.create.act',query))
        session_read.assert_called_once_with('GET','/session/test-only')
        self.assertEqual([('factory',RUN),('act',query)],calls);self.assertIsNone(self.h.adapter._operation)
        self.assertEqual('bound',self.h.adapter._binding_store('test-only').read()['phase'])
    def test_failed_create_finalizer_blocks_original_sdk_teardown_and_preserves_binding(self):
        marker=PrivateFeatureState(self.h.root/'ios-create-primary-feature.json');marker.write(dict(owned=True),None)
        before=deepcopy(self.h.commands);binding=self.h.adapter._binding_store('test-only').read();calls=[]
        def pending(runtime,selector,configuration,client):
            self.assertIsInstance(runtime,IOSCreateRuntime);self.assertIs(runtime.adapter,self.h.adapter)
            calls.append(selector);raise NativeUIError('Actual Create ownership remains unresolved')
        with patch.object(config,'configuration',return_value=None),patch('ios.adapters.create_finalization.finalize_existing',side_effect=pending):
            with self.assertRaises(NativeUIError):self.h.adapter.cleanup('test-only')
        self.assertEqual(['test-only'],calls);self.assertEqual(before,self.h.commands)
        self.assertIsNotNone(self.h.process);self.assertEqual(binding,self.h.adapter._binding_store('test-only').read())
        self.assertEqual(dict(owned=True),marker.read())
    def test_lost_fixed_owner_with_retained_unknown_input_blocks_sdk_delete_without_a_finalizer_spy(self):
        marker=PrivateFeatureState(self.h.root/'ios-create-primary-feature.json');marker.write(dict(owned=True),None)
        carrier=PrivateFeatureState(self.h.root/'ios-create-inputs.json');carrier.write(dict(delivery='unknown'),None)
        marker.path.unlink();before=deepcopy(self.h.commands);binding=self.h.adapter._binding_store('test-only').read()
        with patch.object(config,'configuration',return_value=None),self.assertRaises(NativeUIError):self.h.adapter.cleanup('test-only')
        self.assertEqual(before,self.h.commands);self.assertIsNotNone(self.h.process)
        self.assertEqual(binding,self.h.adapter._binding_store('test-only').read());self.assertEqual(dict(delivery='unknown'),carrier.read())
    def test_successful_finalizer_gate_precedes_the_original_sdk_teardown(self):
        marker=PrivateFeatureState(self.h.root/'ios-create-primary-feature.json');marker.write(dict(owned=True),None);calls=[]
        def qualified(runtime,selector,configuration,client):
            self.assertIsInstance(runtime,IOSCreateRuntime);self.assertIsNotNone(self.h.process)
            self.assertIsNotNone(runtime.adapter.read_session(selector));calls.append(selector);return True
        with patch.object(config,'configuration',return_value=None),patch('ios.adapters.create_finalization.finalize_existing',side_effect=qualified):
            self.assertEqual({'cleaned':True},self.h.adapter.cleanup('test-only'))
        self.assertEqual(['test-only'],calls);self.assertIsNone(self.h.process);self.assertIsNone(self.h.adapter.read_session('test-only'))


if __name__=='__main__':unittest.main()
