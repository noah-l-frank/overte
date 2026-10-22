"""Actual installed dispatch/candidate gate and strict additive private admission.

The scene work is independently covered by the whole role suites. These spies
isolate routing and ordering without authorizing an effect or SDK creation.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import os
import importlib.util
import json
from pathlib import Path
import sys
from types import ModuleType
import unittest
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.adapters import feature_configuration as config
from ios.adapters.emote_runtime import IOSEmoteRuntime
from ios.adapters.normal_scripts import PROFILE
from ios.self_tests import test_ios_emote_configuration as settings_fixture
from ios.self_tests import test_ios_installed_adapter as installed_fixture
from ios.self_tests.test_ios_emote_sources import RUN


class EmoteAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.h=settings_fixture.ConfigurationTests();self.h.setUp();self.addCleanup(self.h.doCleanups)
        self.store=PrivateFeatureState(self.h.root/'adapter.json')
        self.value=dict(iosFeatureAdapterVersion=4,areas=['emotes'],fixtureConfig=str(self.h.root/'reader.json'),
            graphics=None,create=None,emotes=deepcopy(self.h.value))
        self.store.write(self.value,None)
        self.target=dict(physical=True,normalScripts=dict(contractVersion=1,profile=PROFILE),
            nativeUiObservation=dict(kind='uikit-documents',version=1),probe=dict(kind='ios-documents'),testBuild={'configured':True})
    def test_explicit_v4_admits_only_its_three_operations_and_never_by_default(self):
        with patch.dict(os.environ,{'OVERTE_IOS_FEATURE_ADAPTER_CONFIG':str(self.store.path)}):
            self.assertEqual(self.value,config.configuration())
            self.assertEqual(['feature.emotes.act','feature.emotes.cleanup','feature.emotes.observe'],config.capabilities(self.target))
            for target in (self.target|dict(physical=False),self.target|dict(normalScripts=None)):
                with self.assertRaises(NativeUIError):config.capabilities(target)
        with patch.dict(os.environ):
            os.environ.pop('OVERTE_IOS_FEATURE_ADAPTER_CONFIG',None)
            self.assertEqual([],config.capabilities(self.target))
    def test_legacy_unknown_and_effect_fields_cannot_admit_emotes(self):
        for changed in (dict(iosFeatureAdapterVersion=3),dict(iosFeatureAdapterVersion=True),dict(iosFeatureAdapterVersion=5),
                        dict(areas=['emotes','unknown']),dict(emotes=self.value['emotes']|dict(animation='Waving')),
                        dict(emotes=None),dict(areas=['scripts'])):
            self.store.write(self.value|changed,self.store.read())
            with self.subTest(changed=changed),self.assertRaises((NativeUIError,ValueError)):config.configuration(self.store.path)
        legacy=dict(self.value,areas=['scripts'],emotes=None)
        self.store.write(legacy,self.store.read());self.assertEqual(legacy,config.configuration(self.store.path))
        self.store.path.chmod(0o644)
        with self.assertRaises(NativeUIError):config.configuration(self.store.path)


class EmoteInstalledRoutingTests(unittest.TestCase):
    def setUp(self):
        self.h=installed_fixture.InstalledAdapterTests();self.h.setUp();self.addCleanup(self.h.doCleanups)
        self.h.target['serverUrl']='http://controlled.invalid:4723'
        self.h.adapter._state['targetFingerprint']=self.h.adapter.fingerprint()
        self.h.adapter.describe('test-only')
    def session(self):
        device=Path(__file__).resolve().parents[2]
        catalog=json.loads((device/'catalog.json').read_text())
        module=next(row for row in catalog['modules'] if row['id']=='feature-emotes')
        self.assertIn('feature-emotes',module['suites'])
        self.assertTrue({'feature.emotes.act','feature.emotes.observe','feature.emotes.cleanup'}<=set(module['requires']))
        support=ModuleType('module_support')
        support.ARTIFACT_DIR=self.h.root;support.InfrastructureError=RuntimeError
        support.operation=lambda name,fields:self.h.adapter.invoke('test-only',name,fields)
        for name in ('assert_foreground','assert_process','fail','process_identity','wait_for_process','wait_for_process_stopped','write_json'):
            setattr(support,name,lambda *_:None)
        spec=importlib.util.spec_from_file_location('ios_emote_normal_session',device/'overte_session.py')
        module=importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules,{'module_support':support}):spec.loader.exec_module(module)
        return module.OverteSession()

    def test_actual_invoke_routes_all_three_operations_and_keeps_final_binding_verification(self):
        calls=[];settings={'private-policy':'routing-only'}
        class Flow:
            def act(_self,value):calls.append(('act',deepcopy(value)));return {'performed':True}
            def observe(_self,value):calls.append(('observe',deepcopy(value)));return {'routing':'observed'}
            def cleanup(_self,value):calls.append(('cleanup',deepcopy(value)));return {'performed':True}
        def factory(runtime,selector,run,**kwargs):
            self.assertIsInstance(runtime,IOSEmoteRuntime);self.assertIs(runtime.adapter,self.h.adapter)
            self.assertEqual(('test-only',RUN),(selector,run));self.assertEqual('primary',kwargs['role'])
            self.assertIs(settings,kwargs['settings']);calls.append(('factory',run));return Flow()
        value=dict(iosFeatureAdapterVersion=4,areas=['emotes'],emotes=settings)
        queries={'act':dict(contractVersion=16,runId=RUN,ticket='b'*32,
            fixtureUrl='http://127.0.0.1:12345/feature-fixture/v1/runs/'+RUN+'/',verb='open',inputs={}),
            'observe':dict(contractVersion=16,runId=RUN,afterSequence=0),'cleanup':dict(contractVersion=16,runId=RUN)}
        with patch.object(config,'configuration',return_value=value),patch.object(config,'reader',return_value=object()),\
             patch.object(config,'capabilities',return_value=['feature.emotes.'+kind for kind in queries]),\
             patch('ios.adapters.appium_adapter.WebDriver',return_value=self.h.adapter.client),\
             patch.object(self.h.adapter.client,'call',return_value={},create=True) as session_read,\
             patch.object(IOSEmoteRuntime,'_emote_feature',factory):
            for kind,query in queries.items():
                if kind=='act':result=self.session().feature_operation('emotes',kind,query)
                else:result=self.h.adapter.invoke('test-only','feature.emotes.'+kind,query)
                self.assertEqual({'routing':'observed'} if kind=='observe' else {'performed':True},result)
                self.assertIsNone(self.h.adapter._operation)
        self.assertEqual(3,session_read.call_count)
        self.assertEqual(sum(([('factory',RUN),(kind,query)] for kind,query in queries.items()),[]),calls)
        self.assertEqual('bound',self.h.adapter._binding_store('test-only').read()['phase'])
    def test_real_canonical_cleanup_refuses_actor_or_orphan_owner_before_sdk_stop(self):
        before=deepcopy(self.h.commands);binding=self.h.adapter._binding_store('test-only').read()
        for name in ('ios-emote-actor-feature.json','ios-emote-primary-pointers.json'):
            store=PrivateFeatureState(self.h.root/name);store.write(dict(actual='unresolved ownership'),None)
            with self.subTest(name=name),self.assertRaises(NativeUIError):self.h.adapter.cleanup('test-only')
            self.assertEqual(before,self.h.commands);self.assertIsNotNone(self.h.process)
            self.assertEqual(binding,self.h.adapter._binding_store('test-only').read());store.discard(store.read())
    def test_successful_gate_precedes_original_session_delete_and_keeps_default_behavior(self):
        events=[]
        def qualified(adapter,selector):
            self.assertIs(adapter,self.h.adapter);self.assertIsNotNone(self.h.process);events.append(selector);return True
        with patch('ios.adapters.installed_adapter.finalize_emotes',side_effect=qualified),\
             patch.object(config,'configuration',return_value=None):
            self.assertEqual({'cleaned':True},self.h.adapter.cleanup('test-only'))
        self.assertEqual(['test-only'],events);self.assertIsNone(self.h.process)
        self.assertIsNone(self.h.adapter.read_session('test-only'))
