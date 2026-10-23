"""Actual canonical dispatch and cleanup fences; effects are explicit spies.

The separate whole cases qualify original scene/PNG/end behavior. Routing spies
cannot enable complete capability admission or substitute for that graph.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from unittest.mock import patch

from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.adapters import feature_configuration as config
from ios.adapters.navigation_runtime import IOSNavigationRuntime
from ios.adapters import navigation_failed_preparation_cleanup as failed_cleanup
from ios.self_tests import test_ios_installed_adapter as fixtures
from self_tests.test_feature_terminal import Boundary


class NavigationInstalledRoutingTests(unittest.TestCase):
    def setUp(self):
        self.h=fixtures.InstalledAdapterTests();self.h.setUp();self.addCleanup(self.h.doCleanups)
        self.h.target['serverUrl']='http://controlled.invalid:4723'
        self.h.adapter._state['targetFingerprint']=self.h.adapter.fingerprint();self.h.adapter.describe('test-only')

    def test_actual_invoke_routes_original_calls_and_retains_final_candidate_binding_check(self):
        calls=[];settings={'private-root':'routing-only'};test=self;client=object();run='a'*32
        class Flow:
            def act(_self,value):calls.append(('act',deepcopy(value)));return {'performed':True}
            def observe(_self,value):calls.append(('observe',deepcopy(value)));return {'routing':'observed'}
            def cleanup(_self,value):calls.append(('cleanup',deepcopy(value)));return {'performed':True}
        def factory(runtime,selector,actual_run,**kwargs):
            test.assertIs(runtime.adapter,test.h.adapter);test.assertEqual(('test-only',run),(selector,actual_run))
            test.assertIs(settings,kwargs['settings']);test.assertIs(client,kwargs['client']);test.assertEqual('primary',kwargs['role'])
            calls.append(('factory',actual_run));return Flow()
        queries=dict(act=dict(contractVersion=16,runId=run,ticket='b'*32,verb='open',inputs={},
            fixtureUrl='http://127.0.0.1:12345/feature-fixture/v1/runs/'+run+'/'),
            observe=dict(contractVersion=16,runId=run,afterSequence=0),cleanup=dict(contractVersion=16,runId=run))
        value=dict(iosFeatureAdapterVersion=5,areas=['world-navigation'],worldNavigation=settings)
        with (patch.object(config,'configuration',return_value=value),patch.object(config,'reader',return_value=client),
              patch.object(config,'capabilities',return_value=['feature.world-navigation.'+kind for kind in queries]),
              patch('ios.adapters.appium_adapter.WebDriver',return_value=self.h.adapter.client),
              patch.object(self.h.adapter.client,'call',return_value={},create=True) as sdk,
              patch.object(failed_cleanup,'verify',return_value=False),
              patch.object(IOSNavigationRuntime,'_navigation_feature',factory)):
            for kind,query in queries.items():
                result=self.h.adapter.invoke('test-only','feature.world-navigation.'+kind,query)
                self.assertEqual({'routing':'observed'} if kind=='observe' else {'performed':True},result)
                self.assertIsNone(self.h.adapter._operation)
        self.assertEqual(3,sdk.call_count)
        self.assertEqual(sum(([('factory',run),(kind,query)] for kind,query in queries.items()),[]),calls)
        self.assertEqual('bound',self.h.adapter._binding_store('test-only').read()['phase'])

    def test_public_finish_response_cannot_skip_typed_original_end_or_reenter_live_session_verify(self):
        model=Boundary();model.journey().execute();end=deepcopy(model.reports[-1]['terminalRetirement']['end'])
        from feature_journeys import terminal
        call=dict(contractVersion=terminal.VERSION,runId=model.run,stage='finish',seal=end['seal'])
        class ForgedFlow:
            def terminal(_self,_call):return dict(stage='finish',end=end)
        value=dict(iosFeatureAdapterVersion=5,areas=['world-navigation'],worldNavigation={})
        before=deepcopy(self.h.commands)
        with (patch.object(config,'configuration',return_value=value),patch.object(config,'reader',return_value=object()),
              patch.object(config,'capabilities',return_value=['feature.world-navigation.terminal']),
              patch.object(IOSNavigationRuntime,'_navigation_feature',return_value=ForgedFlow()),
              patch.object(IOSNavigationRuntime,'_existing',side_effect=AssertionError('Post-finish live session verification'))):
            with self.assertRaises(NativeUIError):self.h.adapter.invoke('test-only','feature.world-navigation.terminal',call)
        self.assertEqual(before,self.h.commands);self.assertIsNone(self.h.adapter._operation)

    def test_generic_cleanup_preserves_orphan_originals_before_stop_or_sdk_delete(self):
        before=deepcopy(self.h.commands);binding=self.h.adapter._binding_store('test-only').read()
        path=self.h.adapter.state_path('test-only').with_name('ios-navigation-whole-preparation.json')
        store=PrivateFeatureState(path);store.write(dict(incomplete=True),None)
        with patch.object(config,'configuration',return_value=None),self.assertRaises(NativeUIError):self.h.adapter.cleanup('test-only')
        self.assertEqual(before,self.h.commands);self.assertEqual(binding,self.h.adapter._binding_store('test-only').read())
        self.assertEqual(dict(incomplete=True),store.read())

    def test_public_cleanup_ack_cannot_substitute_for_a_typed_failed_end(self):
        run='a'*32;call=dict(contractVersion=16,runId=run)
        class ForgedFlow:
            def cleanup(_self,_call):return {'performed':True}
        value=dict(iosFeatureAdapterVersion=5,areas=['world-navigation'],worldNavigation={})
        before=deepcopy(self.h.commands)
        with (patch.object(config,'configuration',return_value=value),patch.object(config,'reader',return_value=object()),
              patch.object(config,'capabilities',return_value=['feature.world-navigation.cleanup']),
              patch.object(IOSNavigationRuntime,'_navigation_feature',return_value=ForgedFlow()),
              patch.object(IOSNavigationRuntime,'_existing',side_effect=AssertionError('Forged cleanup reached live SDK'))):
            with self.assertRaises(NativeUIError):self.h.adapter.invoke('test-only','feature.world-navigation.cleanup',call)
        self.assertEqual(before,self.h.commands);self.assertIsNone(self.h.adapter._operation)

    def test_generic_typed_navigation_branch_precedes_unrelated_gpu_scans(self):
        # The real generic entry is exercised here; the separate original-file
        # tests qualify the typed Navigation verdict supplied by this spy.
        from ios.adapters import navigation_session_cleanup as navigation
        from ios.adapters import emote_session_cleanup as emotes
        before=deepcopy(self.h.commands)
        with (patch.object(config,'configuration',return_value=None),
              patch.object(navigation,'retire_existing',return_value={'cleaned':True}) as typed,
              patch.object(emotes,'owned',side_effect=AssertionError('Typed end reached unrelated GPU scan'))):
            self.assertEqual({'cleaned':True},self.h.adapter.cleanup('test-only'))
        typed.assert_called_once();self.assertEqual(before,self.h.commands)


if __name__=='__main__':unittest.main()
