"""Real cleanup input/source owners at synthetic native and W3C boundaries."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.adapters.avatar_cleanup_controls import IOSAvatarCleanupControls
from ios.adapters.avatar_cleanup_inputs import AvatarCleanupInputOwner,call
from ios.self_tests import test_ios_avatar_action_recovery as active_fixture

URL='https://controlled.invalid/restored-original.fst'


class AvatarCleanupControlsTests(unittest.TestCase):
    def setup_case(self,lost_at=100):
        self.boundary=active_fixture.AvatarActionRecoveryTests();self.boundary.setup_case(lost_at);self.addCleanup(self.boundary.doCleanups)
        f=self.boundary.f;self.f=f
        f.fixture.journal.activate(f.fixture.run,'c'*32,'cleanup')
        self.query=dict(contractVersion=16,runId=f.fixture.run)
    def owner(self):
        f=self.f;active=self.boundary.owner();source=f.source
        inputs=AvatarCleanupInputOwner(PrivateFeatureState(f.path/'ios-avatar-primary-cleanup-inputs.json'),f.lock,
            source.binding,source.run,'primary',source.phase.fixture_url,lambda:True)
        return IOSAvatarCleanupControls(PrivateFeatureState(f.path/'ios-avatar-primary-cleanup-controls.json'),source,
            inputs,f.sdk,active.input_reads)
    def run_model(self,owner):return owner.run(self.query,index=1,step='restore-model',inputs=dict(url=URL))
    def test_new_cleanup_recipe_keeps_original_closed_cleanup_ticket_and_separate_input_namespace(self):
        self.setup_case();owner=self.owner();self.assertEqual({'performed':True},self.run_model(owner))
        self.assertEqual(URL,self.f.fixture.widget.avatar_url)
        self.assertEqual('c'*32,owner.state['calls'][0]['query']['ticket'])
        self.assertEqual([],self.boundary.owner().inputs.state['calls'])
        self.assertTrue(owner.inputs.store.path.name.endswith('-cleanup-inputs.json'))
        self.assertIn('iosAvatarCleanupInputOwnerVersion',owner.inputs.store.read())
    def test_each_lost_cleanup_URL_return_recovers_original_input_without_repeating_any_command(self):
        for position in range(1,5):
            with self.subTest(position=position):
                self.setup_case(position);owner=self.owner()
                with self.assertRaises(NativeUIError):self.run_model(owner)
                before=deepcopy(self.boundary.edits);clock=deepcopy(owner.state['calls'][0]['operationClock'])
                restored=self.owner();self.assertEqual({'performed':True},self.run_model(restored))
                self.assertEqual(before,self.boundary.edits[:position]);self.assertEqual(4,len(self.boundary.edits))
                self.assertEqual(clock,restored.state['calls'][0]['operationClock']);self.assertEqual(URL,self.f.fixture.widget.avatar_url)
    def test_expired_original_cleanup_step_cannot_be_replaced_by_another_step_or_new_deadline(self):
        self.setup_case(1);owner=self.owner()
        with self.assertRaises(NativeUIError):self.run_model(owner)
        self.f.fixture.clock+=26;edits=deepcopy(self.boundary.edits)
        for index in (1,2):
            with self.assertRaises(NativeUIError):self.owner().run(self.query,index=index,step='restore-model',inputs=dict(url=URL))
        self.assertEqual(edits,self.boundary.edits);self.assertEqual([],self.boundary.queries)
    def test_durable_cleanup_input_finish_return_is_adopted_without_repeating_it(self):
        self.setup_case();owner=self.owner();finish=owner.inputs.finish
        def lost():finish();raise OSError('Lost actual cleanup input finish return')
        owner.inputs.finish=lost
        with self.assertRaises(OSError):self.run_model(owner)
        edits=deepcopy(self.boundary.edits);restored=self.owner()
        with patch.object(restored.inputs,'finish',side_effect=AssertionError('Original finish already saved')):
            self.assertEqual({'performed':True},self.run_model(restored))
        self.assertEqual(edits,self.boundary.edits);self.assertEqual([],self.boundary.queries)
    def test_changed_cleanup_operands_cannot_replace_saved_recipe(self):
        self.setup_case(1);owner=self.owner()
        with self.assertRaises(NativeUIError):self.run_model(owner)
        edits=deepcopy(self.boundary.edits)
        with self.assertRaises(NativeUIError):self.owner().run(self.query,index=1,step='restore-model',inputs=dict(url=URL+'/other'))
        self.assertEqual(edits,self.boundary.edits)
    def test_distinct_cleanup_steps_share_actual_ticket_without_replacing_active_input_history(self):
        self.setup_case();owner=self.owner();self.run_model(owner)
        self.assertEqual({'performed':True},owner.run(self.query,index=2,step='restore-scale',inputs=dict(value=1.5)))
        self.assertEqual(1.5,self.f.fixture.widget.scale)
        rebuilt=self.owner();self.assertEqual([1,2],[row['query']['index'] for row in rebuilt.state['calls']])
        self.assertEqual(['c'*32]*2,[row['arguments']['ticket'] for row in rebuilt.inputs.state['calls']])
        self.assertEqual([],self.boundary.owner().inputs.state['calls'])
    def test_cleanup_step_rejects_foreign_replacement_text_before_native_delivery(self):
        self.setup_case();owner=self.owner();intent=owner.inputs.intent
        def altered(value):
            value=deepcopy(value)
            if value['action']=='replace':
                value['value']=URL+'/foreign';value['nativeCommand']['text']=value['value']
            return intent(value)
        owner.inputs.intent=altered
        with self.assertRaises(NativeUIError):self.run_model(owner)
        self.assertFalse(any(row.get('text')==URL+'/foreign' for row in self.boundary.edits))
        self.assertEqual(2,len(self.boundary.edits))
    def test_cleanup_cannot_use_active_phase_as_an_input_authority(self):
        self.setup_case();self.f.fixture.journal.activate(self.f.fixture.run,'d'*32,'avatar-scale',dict(value=1.5))
        with self.assertRaises(NativeUIError):self.run_model(self.owner())
        self.assertEqual([],self.boundary.edits);self.assertEqual([],self.f.sdk.inputs)
    def test_closed_cleanup_descriptor_refuses_legacy_act_extra_fields_and_changed_types(self):
        self.setup_case();owner=self.owner();self.run_model(owner);original=deepcopy(owner.state['calls'][0]['query'])
        for fault in ('version','index','step','extra','owned-name','foreign-account'):
            value=deepcopy(original)
            if fault=='version':value['avatarCleanupInputCallVersion']=True
            elif fault=='index':value['index']=True
            elif fault=='step':value['step']='avatar-url'
            elif fault=='extra':value['verb']='avatar-url'
            elif fault=='owned-name':value.update(step='delete-bookmark',inputs=dict(name='unowned-bookmark'))
            else:value.update(step='remove-connection',inputs=dict(username='unowned-account'))
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):call(value)


if __name__=='__main__':unittest.main()
