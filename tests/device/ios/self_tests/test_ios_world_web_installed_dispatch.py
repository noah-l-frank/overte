"""Canonical routing/guards over modeled installed sources and explicit spies.

The separate composed cases qualify the typed World originals. These routing
cases cannot advertise completeness or replace original native/end evidence.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.adapters import feature_configuration as config
from ios.adapters.world_web_runtime import IOSWorldWebRuntime
from ios.self_tests import test_ios_installed_adapter as fixtures
from ios.self_tests.test_ios_world_web_terminal_seal import WorldWebTerminalSealTests as SealFixture


class WorldWebInstalledDispatchTests(unittest.TestCase):
    def setUp(self):
        self.h=fixtures.InstalledAdapterTests();self.h.setUp();self.addCleanup(self.h.doCleanups)
        self.h.target['serverUrl']='http://controlled.invalid:4723'
        self.h.adapter._state['targetFingerprint']=self.h.adapter.fingerprint();self.h.adapter.describe('test-only')

    def test_normal_calls_reach_world_factory_then_original_final_installed_guard(self):
        calls=[];settings={'routing-only':'not a configuration verdict'};client=object();run='a'*32;test=self
        class Flow:
            def act(_self,value):calls.append(('act',deepcopy(value)));return {'performed':True}
            def observe(_self,value):calls.append(('observe',deepcopy(value)));return {'routing':'observed'}
            def cleanup(_self,value):calls.append(('cleanup',deepcopy(value)));return {'performed':True}
        def factory(runtime,selector,actual_run,**kwargs):
            test.assertIs(test.h.adapter,runtime.adapter);test.assertEqual(('test-only',run),(selector,actual_run))
            test.assertIs(settings,kwargs['settings']);test.assertIs(client,kwargs['client']);test.assertEqual('primary',kwargs['role'])
            calls.append(('factory',actual_run));return Flow()
        queries=dict(act=dict(contractVersion=16,runId=run,ticket='b'*32,verb='open',inputs={},
            fixtureUrl='http://127.0.0.1:12345/feature-fixture/v1/runs/'+run+'/'),
            observe=dict(contractVersion=16,runId=run,afterSequence=0),cleanup=dict(contractVersion=16,runId=run))
        value=dict(iosFeatureAdapterVersion=5,areas=['world-web'],worldWeb=settings)
        with (patch.object(config,'configuration',return_value=value),patch.object(config,'reader',return_value=client),
              patch.object(config,'capabilities',return_value=['feature.world-web.'+kind for kind in queries]),
              patch('ios.adapters.appium_adapter.WebDriver',return_value=self.h.adapter.client),
              patch.object(self.h.adapter.client,'call',return_value={},create=True) as sdk,
              patch.object(IOSWorldWebRuntime,'_world_web_feature',factory)):
            for kind,query in queries.items():
                result=self.h.adapter.invoke('test-only','feature.world-web.'+kind,query)
                self.assertEqual({'routing':'observed'} if kind=='observe' else {'performed':True},result)
                self.assertIsNone(self.h.adapter._operation)
        self.assertEqual(3,sdk.call_count)
        self.assertEqual(sum(([('factory',run),(kind,query)] for kind,query in queries.items()),[]),calls)
        self.assertEqual('bound',self.h.adapter._binding_store('test-only').read()['phase'])

    def test_forged_finish_cannot_skip_typed_original_end_or_query_a_dead_sdk(self):
        fixture=SealFixture();fixture.setUp();self.addCleanup(fixture.doCleanups);seal=fixture.seal({})
        call=dict(contractVersion=1,runId='a'*32,stage='finish',seal=seal)
        class Forged:
            def terminal(_self,_call):return dict(stage='finish',end={'not':'an original end'})
        value=dict(iosFeatureAdapterVersion=5,areas=['world-web'],worldWeb={});before=deepcopy(self.h.commands)
        with (patch.object(config,'configuration',return_value=value),patch.object(config,'reader',return_value=object()),
              patch.object(config,'capabilities',return_value=['feature.world-web.terminal']),
              patch.object(IOSWorldWebRuntime,'_world_web_feature',return_value=Forged()),
              patch.object(IOSWorldWebRuntime,'_existing',side_effect=AssertionError('Post-end live SDK access'))):
            with self.assertRaises(NativeUIError):self.h.adapter.invoke('test-only','feature.world-web.terminal',call)
        self.assertEqual(before,self.h.commands);self.assertIsNone(self.h.adapter._operation)

    def test_generic_cleanup_preserves_world_orphan_before_unrelated_cleanup_or_sdk_delete(self):
        before=deepcopy(self.h.commands);binding=self.h.adapter._binding_store('test-only').read()
        carrier=PrivateFeatureState(self.h.adapter.state_path('test-only').with_name('world-web-retained-original.json'))
        carrier.write(dict(original=True),None)
        with patch.object(config,'configuration',return_value=None),patch.object(self.h.adapter,'_cleanup_other_features',
                side_effect=AssertionError('Orphan reached unrelated cleanup')),self.assertRaises(NativeUIError):
            self.h.adapter.cleanup('test-only')
        self.assertEqual(before,self.h.commands);self.assertEqual(binding,self.h.adapter._binding_store('test-only').read())
        self.assertEqual(dict(original=True),carrier.read())

    def test_generic_typed_world_end_precedes_other_feature_scans(self):
        from ios.adapters import world_web_finalization
        before=deepcopy(self.h.commands)
        with (patch.object(config,'configuration',return_value=None),
              patch.object(world_web_finalization,'retire_existing',return_value={'cleaned':True}) as typed,
              patch.object(self.h.adapter,'_cleanup_other_features',side_effect=AssertionError('Typed end reached unrelated scan'))):
            self.assertEqual({'cleaned':True},self.h.adapter.cleanup('test-only'))
        typed.assert_called_once();self.assertEqual(before,self.h.commands)


if __name__=='__main__':unittest.main()
