"""Canonical dispatch/refusal with explicit flow/end-verifier test seams.

The actual installed adapter, candidate lease and API decorator execute. Flow
effects and complete end admission are deliberately modeled here; these tests
do not qualify an Avatar journey or native/device behavior.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import ExitStack
from copy import deepcopy
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch
from adapters.normal_feature_state import PrivateFeatureState
from ios.adapters import avatar_api_entry
from ios.adapters.avatar_runtime import IOSAvatarRuntime
from ios.adapters.feature_configuration import COMPLETE_AREAS
from feature_journeys.contract import VERSION
from ios.self_tests.test_ios_installed_adapter import InstalledAdapterTests
from self_tests.test_feature_terminal import Boundary


class AvatarInstalledRoutingTests(unittest.TestCase):
    setUp=InstalledAdapterTests.setUp
    run_id='a'*32
    def routing(self,operation,flow):
        stack=ExitStack();config={'avatarPeople':{'test':'explicit settings boundary'}}
        stack.enter_context(patch('ios.adapters.feature_configuration.configuration',return_value=config))
        stack.enter_context(patch('ios.adapters.feature_configuration.capabilities',return_value=[operation]))
        stack.enter_context(patch('ios.adapters.feature_configuration.reader',return_value=object()))
        factory=stack.enter_context(patch.object(IOSAvatarRuntime,'_avatar_feature',return_value=flow))
        return stack,factory,config
    def test_closed_avatar_capability_remains_unadvertised_before_flow_or_sdk_acquisition(self):
        self.assertNotIn('avatar-people',COMPLETE_AREAS)
        with patch('ios.adapters.feature_configuration.configuration',return_value={'areas':['avatar-people']}),\
                patch.object(IOSAvatarRuntime,'_avatar_feature') as factory:
            with self.assertRaises((ValueError,RuntimeError)):
                self.adapter.invoke('test-only','feature.avatar-people.observe',dict(contractVersion=VERSION,runId=self.run_id,afterSequence=0))
        factory.assert_not_called();self.assertEqual(0,self.sessions);self.assertEqual([],self.commands)
    def test_avatar_factory_and_active_post_binding_share_actual_api_budget(self):
        operation='feature.avatar-people.observe';call=dict(contractVersion=VERSION,runId=self.run_id,afterSequence=0)
        def observe(value):
            self.assertIsNotNone(avatar_api_entry._CURRENT.get());self.assertEqual(call,value);return {'explicit':'modeled flow'}
        flow=SimpleNamespace(observe=observe);guard=SimpleNamespace(verify=Mock())
        stack,factory,config=self.routing(operation,flow)
        with stack,patch.object(IOSAvatarRuntime,'_existing',return_value=(object(),'session',{},self.target,{})) as existing,\
                patch.object(self.adapter,'_binding',return_value=guard):
            self.assertEqual({'explicit':'modeled flow'},self.adapter.invoke('test-only',operation,call))
        factory.assert_called_once_with('test-only',self.run_id,role='primary',client=unittest.mock.ANY,settings=config['avatarPeople'])
        existing.assert_called_once_with('test-only');guard.verify.assert_called_once_with()
        self.assertIsNone(avatar_api_entry._CURRENT.get());self.assertIsNone(self.adapter._operation)
    def test_terminal_finish_uses_historical_qualifier_without_reacquiring_deleted_sdk(self):
        boundary=Boundary();description=deepcopy(boundary.descriptor);description.update(area='avatar-people',runId=self.run_id)
        seal=dict(featureTerminalSealVersion=1,description=description,windowSha256='1'*64,liveOriginalSha256='2'*64)
        call=dict(contractVersion=1,runId=self.run_id,stage='finish',seal=seal);result={'explicit':'modeled end'}
        flow=SimpleNamespace(terminal=Mock(return_value=result));stack,_factory,_config=self.routing('feature.avatar-people.terminal',flow)
        with stack,patch('ios.adapters.avatar_canonical_end.verify') as verify,\
                patch.object(IOSAvatarRuntime,'_existing',side_effect=AssertionError('No live SDK after end')):
            self.assertEqual(result,self.adapter.invoke('test-only','feature.avatar-people.terminal',call))
        verify.assert_called_once_with(flow,call,result);self.assertEqual([],self.commands)
    def test_failed_preparation_cleanup_uses_its_distinct_historical_qualifier(self):
        call=dict(contractVersion=VERSION,runId=self.run_id);result=dict(status='failed',performed=True)
        flow=SimpleNamespace(cleanup=Mock(return_value=result));stack,_factory,_config=self.routing('feature.avatar-people.cleanup',flow)
        with stack,patch('ios.adapters.avatar_canonical_end.verify_failed_cleanup',return_value=True) as verify,\
                patch.object(IOSAvatarRuntime,'_existing',side_effect=AssertionError('No live SDK after failed end')):
            self.assertEqual(result,self.adapter.invoke('test-only','feature.avatar-people.cleanup',call))
        verify.assert_called_once_with(flow,call,result);self.assertEqual([],self.commands)
    def test_existing_avatar_cleanup_precedes_unrelated_finalizers_or_generic_sdk_teardown(self):
        with patch('ios.adapters.avatar_metadata_retirement.retire_existing',return_value={'cleaned':True}) as retire,\
                patch('ios.adapters.emote_rooted_session_cleanup.retire_existing',side_effect=AssertionError('Wrong feature cleanup')):
            self.assertEqual({'cleaned':True},self.adapter.cleanup('test-only'))
        self.assertEqual(1,retire.call_count);self.assertEqual(0,self.sessions);self.assertEqual([],self.commands)
    def test_orphan_avatar_original_blocks_generic_cleanup_without_erasure_or_sdk_input(self):
        store=PrivateFeatureState(self.root/'avatar-unknown-original.json');store.write(dict(unknown=True),None)
        before=(store.path.stat().st_ino,store.path.read_bytes())
        with self.assertRaises((ValueError,RuntimeError)):self.adapter.cleanup('test-only')
        self.assertEqual(before,(store.path.stat().st_ino,store.path.read_bytes()));self.assertEqual(0,self.sessions);self.assertEqual([],self.commands)
    def test_lifecycle_owner_still_blocks_avatar_dispatch_before_any_flow_or_sdk_work(self):
        store=PrivateFeatureState(self.root/'ios-lifecycle-input.json');store.write(dict(unresolved=True),None)
        flow=SimpleNamespace(observe=Mock());stack,factory,_config=self.routing('feature.avatar-people.observe',flow)
        with stack,self.assertRaises((ValueError,RuntimeError)):
            self.adapter.invoke('test-only','feature.avatar-people.observe',dict(contractVersion=VERSION,runId=self.run_id,afterSequence=0))
        factory.assert_not_called();flow.observe.assert_not_called();self.assertEqual([],self.commands)
    def test_historical_installed_decoder_uses_selected_candidate_bundle_without_native_calls(self):
        self.adapter.describe('test-only');record=self.adapter._binding_store('test-only').read()
        # This explicitly models the metadata decoder input, not a process end.
        record=dict(record,phase='retired');before=deepcopy(self.commands)
        actual=self.adapter._avatar_retired_binding_record('test-only',record['scope'],record)
        self.assertEqual(record,actual);self.assertEqual(before,self.commands)
        changed=deepcopy(record);changed['observation']['bundle']['bundleSha256']='f'*64
        with self.assertRaises((ValueError,RuntimeError)):
            self.adapter._avatar_retired_binding_record('test-only',record['scope'],changed)
        self.assertEqual(before,self.commands)
    def test_candidate_change_before_return_fails_and_releases_original_avatar_api_budget(self):
        operation='feature.avatar-people.observe';call=dict(contractVersion=VERSION,runId=self.run_id,afterSequence=0)
        def observe(_call):self.artifact.write_bytes(b'changed candidate');return {'explicit':'modeled flow'}
        flow=SimpleNamespace(observe=observe);stack,_factory,_config=self.routing(operation,flow)
        with stack,patch.object(IOSAvatarRuntime,'_existing',return_value=(object(),'session',{},self.target,{})),\
                patch.object(self.adapter,'_binding',return_value=SimpleNamespace(verify=Mock())):
            with self.assertRaises((ValueError,RuntimeError)):self.adapter.invoke('test-only',operation,call)
        self.assertIsNone(avatar_api_entry._CURRENT.get());self.assertIsNone(self.adapter._operation)


if __name__=='__main__':unittest.main()
