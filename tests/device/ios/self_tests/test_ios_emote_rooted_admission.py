"""Explicit rooted routing/end fences; authorization spies are declared models.

The canonical candidate/session gates execute. These routing cases do not
qualify native effects, the full Emote journey or complete area admission.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import os
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import pack
from ios.adapters import feature_configuration as config
from ios.adapters import emote_canonical_end
from ios.adapters.emote_api_entry import installed_entry
from ios.adapters.emote_runtime import IOSEmoteRuntime
from ios.self_tests.test_ios_emote_sources import RUN
from ios.self_tests.test_ios_emote_admission import EmoteAdmissionTests,EmoteInstalledRoutingTests
from ios.self_tests.test_ios_emote_terminal_controller import TerminalControllerTests


def rooted_config(settings,fixture):
    return dict(iosFeatureAdapterVersion=6,emoteCoordinatorVersion=2,areas=['emotes'],fixtureConfig=str(fixture),
        graphics=None,create=None,emotes=deepcopy(settings),**{field:None for field,_module in config.WHOLE_SETTINGS.values()})


class RootedConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.f=EmoteAdmissionTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.value=rooted_config(self.f.value['emotes'],self.f.h.root/'reader.json')
    def test_explicit_rooted_version_is_readable_and_complete_capability_remains_closed(self):
        self.f.store.write(self.value,self.f.store.read())
        with patch.dict(os.environ,OVERTE_IOS_FEATURE_ADAPTER_CONFIG=str(self.f.store.path)):
            self.assertEqual(self.value,config.configuration())
            with self.assertRaises(NativeUIError):config.capabilities(self.f.target)
        self.assertNotIn('emotes',config.COMPLETE_AREAS)
    def test_coordinator_cannot_be_boolean_legacy_or_implicitly_added_to_old_configuration(self):
        for version in (True,1,3,None):
            with self.subTest(version=version),self.assertRaises(NativeUIError):config.validate(self.value|dict(emoteCoordinatorVersion=version))
        for version in (4,5):
            with self.subTest(version=version),self.assertRaises(NativeUIError):config.validate(self.value|dict(iosFeatureAdapterVersion=version))
        legacy=self.f.value;self.assertEqual(legacy,config.validate(legacy))
    def test_non_emote_v6_keeps_the_coordinator_absent_and_unknown_editor_fields_are_closed(self):
        other=self.value|dict(areas=['scripts'],emotes=None,emoteCoordinatorVersion=None)
        self.assertEqual(other,config.validate(other))
        for changed in (dict(emoteCoordinatorVersion=2),dict(animation='Waving')):
            with self.subTest(changed=changed),self.assertRaises(NativeUIError):config.validate(other|changed)


class RootedInstalledRoutingTests(unittest.TestCase):
    def setUp(self):
        self.f=EmoteInstalledRoutingTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.adapter=self.f.h.adapter
    def test_rooted_four_operation_path_uses_actual_installed_gate_and_legacy_factory_stays_unused(self):
        calls=[];settings=dict(declaredRoutingModel=True)
        class Flow:
            def act(_self,value):calls.append('act');return dict(performed=True)
            def observe(_self,value):calls.append('observe');return dict(declaredRoutingModel=True)
            def cleanup(_self,value):calls.append('cleanup');return dict(performed=True)
            def terminal(_self,value):calls.append('terminal');return dict(stage='inspect',declaredRoutingModel=True)
        def factory(runtime,selector,run,**values):
            self.assertIs(runtime.adapter,self.adapter);self.assertEqual(('test-only',RUN),(selector,run))
            self.assertIs(settings,values['settings']);return Flow()
        selected=dict(iosFeatureAdapterVersion=6,emoteCoordinatorVersion=2,areas=['emotes'],emotes=settings)
        values=dict(act=dict(contractVersion=16,runId=RUN,ticket='b'*32,fixtureUrl='http://127.0.0.1:9/feature-fixture/v1/runs/'+RUN+'/',verb='open',inputs={}),
            observe=dict(contractVersion=16,runId=RUN,afterSequence=0),cleanup=dict(contractVersion=16,runId=RUN),
            terminal=dict(contractVersion=1,runId=RUN,stage='inspect'))
        with patch.object(config,'configuration',return_value=selected),patch.object(config,'reader',return_value=object()),\
             patch.object(config,'capabilities',return_value=['feature.emotes.'+kind for kind in values]),\
             patch('ios.adapters.appium_adapter.WebDriver',return_value=self.adapter.client),\
             patch.object(self.adapter.client,'call',return_value={},create=True) as requests,\
             patch.object(IOSEmoteRuntime,'_emote_rooted_feature',factory),\
             patch.object(IOSEmoteRuntime,'_emote_feature',side_effect=AssertionError('Legacy coordinator selected')):
            for kind,value in values.items():
                self.adapter.invoke('test-only','feature.emotes.'+kind,value);self.assertIsNone(self.adapter._operation)
        self.assertEqual(list(values),calls);self.assertEqual(4,requests.call_count)
    def test_unfinished_rooted_metadata_cannot_fall_through_to_normal_sdk_teardown(self):
        store=PrivateFeatureState(self.f.h.root/'ios-emote-primary-feature.json')
        store.write(dict(iosEmoteFeatureVersion=2,runId=RUN),None)
        commands=deepcopy(self.f.h.commands);binding=self.adapter._binding_store('test-only').read()
        with patch.object(config,'configuration',return_value=None),self.assertRaises(NativeUIError):self.adapter.cleanup('test-only')
        self.assertEqual(commands,self.f.h.commands);self.assertEqual(binding,self.adapter._binding_store('test-only').read())
        self.assertIsNotNone(store.read());self.assertIsNotNone(self.f.h.process)
    def test_terminal_budget_extends_from_entry_through_a_late_postguard_without_renewal(self):
        clock=[0.];calls=[]
        def invoke(_adapter,_selector,_operation,_values):calls.append(True);clock[0]=30.;return dict(declaredRoutingModel=True)
        wrapped=installed_entry(invoke,monotonic=lambda:clock[0])
        with self.assertRaises(NativeUIError):wrapped(object(),'test-only','feature.emotes.terminal',{})
        self.assertEqual([True],calls)


class RootedCanonicalEndTests(unittest.TestCase):
    def setUp(self):
        self.f=TerminalControllerTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.flow,self.actor,_settings=self.f.factory_pair();self.seal=self.f.f.proof['seal']
        self.store=PrivateFeatureState(self.flow.store.path.with_name('ios-emote-primary-'+self.flow.run+'-rooted-end.json'))
    def value(self,phase):
        return dict(iosEmoteRootedEndArchiveVersion=1,runId=self.flow.run,archiveSha256='a'*64,seal=self.seal,
            payload=pack([dict(phase=phase,pending=None)]))
    def test_missing_or_partial_actual_end_never_constructs_an_authorizing_controller(self):
        with patch.object(emote_canonical_end,'IOSEmoteTerminal',side_effect=AssertionError('Unfinished end controller opened')):
            with self.assertRaises(NativeUIError):emote_canonical_end.completed(self.flow,self.seal)
            for phase in ('prepared','retiring'):
                self.store.write(self.value(phase),self.store.read())
                with self.assertRaises(NativeUIError):emote_canonical_end.completed(self.flow,self.seal)
        self.assertEqual([],self.f.sdk_calls)
    def test_a_bare_complete_marker_without_original_graph_cannot_pass_full_replay(self):
        self.store.write(self.value('complete'),None)
        with self.assertRaises(NativeUIError):emote_canonical_end.completed(self.flow,self.seal)
        self.assertEqual([],self.f.sdk_calls)
    def test_boolean_or_foreign_end_identity_cannot_reuse_a_public_seal(self):
        for changed in (dict(iosEmoteRootedEndArchiveVersion=True),dict(runId='f'*32)):
            self.store.write(self.value('complete')|changed,self.store.read())
            with self.subTest(changed=changed),self.assertRaises(NativeUIError):emote_canonical_end.completed(self.flow,self.seal)
        self.assertEqual([],self.f.sdk_calls)
