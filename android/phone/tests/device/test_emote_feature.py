"""Public composition over real owners and synthetic target IO; no device claim."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from unittest.mock import patch

import test_emote_actor
import test_emote_retirement
import test_emote_setup_retirement
import test_emote_unissued_retirement
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from overte_phone_emote_actor import PhoneEmoteActor
from overte_phone_emote_feature import PhoneEmoteFeature
from overte_phone_emote_retirement import PhoneEmoteRetirement
from overte_phone_emote_role import PhoneEmoteRole
from overte_phone_emote_run import PhoneEmoteRun
from overte_phone_script_history import unpack
from test_emote_pixels import POLICY
from test_emote_sources import RUN


class EmoteFeatureTests(unittest.TestCase):
    setUp=test_emote_actor.EmoteActorTests.setUp
    prepared=test_emote_actor.EmoteActorTests.prepared
    publication_server=test_emote_actor.EmoteActorTests.publication_server
    actor_run=test_emote_actor.EmoteActorTests.actor_run
    start=test_emote_actor.EmoteActorTests.start
    resource_boundary=test_emote_retirement.EmoteRetirementTests.resource_boundary

    def owner(self):
        run=test_emote_actor.EmoteActorTests.owner(self)
        return PhoneEmoteRun(run.adapter,run.selector,run.phase,run.root,run.extent,run.marker,
            admission=run.policy,image_policy=POLICY,monotonic=run.monotonic,sleep=run.sleep)

    def feature(self,run=None):return PhoneEmoteFeature(self.owner() if run is None else run,POLICY)
    def observation(self,after=0):return dict(contractVersion=17,runId=RUN,afterSequence=after)
    def cleanup_call(self):return dict(contractVersion=17,runId=RUN)

    def test_baseline_prepares_and_each_public_observation_has_a_new_actual_source(self):
        feature=self.feature();first=feature.observe(self.observation())
        second=self.feature().observe(self.observation(first['sequence']))
        self.assertEqual(1,first['sequence']);self.assertEqual(2,second['sequence'])
        self.assertGreater(second['capturedEpochMs'],first['capturedEpochMs'])
        self.assertFalse(second['state']['override']);self.assertEqual([],second['artifacts'])
        self.assertEqual(POLICY,feature.run.store.read()['imagePolicy'])
        self.assertEqual(6,feature.run.store.read()['emoteRunVersion'])

    def test_acknowledged_play_requires_actual_separate_png_motion_and_source_observation(self):
        feature=self.feature();feature.observe(self.observation());call=self.model.call('play',dict(name='Crying'))
        self.assertEqual({'performed':True},feature.act(call));before=deepcopy(self.model.controls.input_requests)
        self.assertEqual({'performed':True},self.feature().act(call));self.assertEqual(before,self.model.controls.input_requests)
        measured=self.feature().observe(self.observation(1))
        self.assertEqual('Crying',measured['state']['animation']);self.assertTrue(measured['state']['override'])
        self.assertEqual(['image','file'],[item['kind'] for item in measured['artifacts']])
        self.assertEqual(before,self.model.controls.input_requests)

    def test_ignored_native_input_is_not_promoted_from_delivery_ack_to_public_success(self):
        feature=self.feature();feature.observe(self.observation());self.model.ignore_native=True
        self.assertEqual({'performed':True},feature.act(self.model.call('play',dict(name='Crying'))))
        with self.assertRaises(NativeUIError):feature.observe(self.observation(1))
        with feature.run.lock.held():
            feature.run.load();role=PhoneEmoteRole(feature.run,'primary',POLICY)
            self.assertEqual(1,role.state['sequence']);self.assertEqual('acquiring',role.state['phase'])

    def test_wrong_run_and_wrong_original_image_policy_fail_before_any_input(self):
        feature=self.feature();feature.observe(self.observation());before=deepcopy(self.model.controls.input_requests)
        wrong=self.observation();wrong['runId']='f'*32
        with self.assertRaises(NativeUIError):feature.observe(wrong)
        policy=deepcopy(POLICY);policy['subject']=[500,200,900,600]
        with self.assertRaises(NativeUIError):PhoneEmoteFeature(self.owner(),policy)
        self.assertEqual(before,self.model.controls.input_requests)

    def test_idle_stop_after_actual_automatic_completion_retains_play_provenance_without_early_cancel(self):
        feature=self.feature();value=feature.observe(self.observation());m=self.model
        feature.act(m.call('play',dict(name='Crying')));value=feature.observe(self.observation(value['sequence']))
        m.epoch+=2100;m.restore();feature.act(m.call('wait-complete'))
        value=feature.observe(self.observation(value['sequence']));self.assertFalse(value['state']['override'])
        for _ in range(2):
            feature=self.feature();feature.act(m.call('cancel'));before=len(m.events)
            value=feature.observe(self.observation(value['sequence']))
            self.assertEqual(before,len(m.events));self.assertEqual('idle',value['state']['animation'])
            self.assertFalse(value['state']['restoredBeforeNominalEnd'])
            self.assertEqual([],value['artifacts'])
            with feature.run.lock.held():
                feature.run.load();role=PhoneEmoteRole(feature.run,'primary',POLICY);row=role.stored(value['sequence'])
                self.assertEqual('idle-reset',row['effect']['kind']);self.assertIsNotNone(row['played'])
                self.assertEqual('restoration',row['effect']['proof']['kind'])

    def test_idle_stop_cannot_borrow_a_foreign_retained_play_reference(self):
        feature=self.feature();value=feature.observe(self.observation());m=self.model
        feature.act(m.call('play',dict(name='Crying')));value=feature.observe(self.observation(value['sequence']))
        m.epoch+=2100;m.restore();feature.act(m.call('wait-complete'));value=feature.observe(self.observation(value['sequence']))
        feature.act(m.call('cancel'))
        with feature.run.lock.held():
            feature.run.load();role=PhoneEmoteRole(feature.run,'primary',POLICY)
            role.state['played']['reference']['inputTicket']='f'*32;role.save()
        with self.assertRaises(NativeUIError):self.feature().observe(self.observation(value['sequence']))

    def test_changed_durable_policy_cannot_be_adopted_by_reconstructed_owner(self):
        feature=self.feature();feature.observe(self.observation());value=feature.run.store.read()
        value['imagePolicy']['subject']=[500,200,900,600];feature.run.store.write(value,feature.run.previous)
        before=self.model.calls[:]
        with self.assertRaises(NativeUIError):self.feature().observe(self.observation(1))
        self.assertEqual(before,self.model.calls)

    def test_cleanup_restores_resources_and_completes_real_primary_quiet_before_ack(self):
        feature=self.feature();feature.observe(self.observation())
        feature.act(self.model.call('play',dict(name='Crying')));feature.observe(self.observation(1))
        self.model.journal.activate(RUN,'a'*32,'cleanup',{});before=len(self.model.work_commands)
        self.assertEqual({'performed':True},feature.cleanup(self.cleanup_call()))
        self.assertGreater(len(self.model.work_commands),before)
        measured=feature.observe(self.observation(2));self.assertEqual('idle',measured['state']['animation'])
        self.assertFalse(measured['state']['panel']);self.assertEqual([],measured['resources'])
        self.assertIsNotNone(feature.run.store.read())

    def test_incomplete_actual_resource_restoration_cannot_return_public_cleanup_ack(self):
        feature=self.feature();feature.observe(self.observation());self.setup_fault='scene-cleanup'
        self.model.journal.activate(RUN,'a'*32,'cleanup',{})
        with self.assertRaises(NativeUIError):feature.cleanup(self.cleanup_call())
        self.assertEqual('restoring-resources',unpack(feature.run.store.read()['payload'])[0]['phase'])

    def test_rotation_waits_outside_lock_for_actual_actor_namespace_proof(self):
        actor=self.start();feature=self.feature(self.primary);self.assertFalse(actor.step())
        feature.observe(self.observation());feature.act(self.model.call('open'))
        call=self.model.call('play',dict(name='Crying'));sleep=self.model.sleep;waited=[]
        def advance(seconds):
            with self.assertRaises(NativeUIError):self.primary.lock.assert_held()
            waited.append(seconds);actor.step();sleep(seconds)
        with patch.object(feature,'rotation_needed',return_value=True),patch.object(self.primary,'sleep',side_effect=advance):
            self.assertEqual({'performed':True},feature.act(call))
        self.assertTrue(waited);self.assertEqual(1,self.primary.state['segment'])
        measured=feature.observe(self.observation(1));self.assertEqual('Crying',measured['state']['animation'])

    def test_finalization_waits_for_actual_actor_termination_and_preserves_real_originals(self):
        actor=self.start();feature=self.feature(self.primary);self.assertFalse(actor.step())
        feature.observe(self.observation());self.model.journal.activate(RUN,'a'*32,'cleanup',{})
        feature.cleanup(self.cleanup_call());self.assertFalse(actor.step());feature.observe(self.observation(1))
        self.reader.request('/runs/'+RUN,method='DELETE');sleep=self.model.sleep;waited=[]
        def advance(seconds):
            with self.assertRaises(NativeUIError):self.primary.lock.assert_held()
            waited.append(seconds);self.assertTrue(actor.step());sleep(seconds)
        def resource(owner):return self.resource_boundary(owner)
        with patch.object(self.primary,'sleep',side_effect=advance),patch.object(PhoneEmoteRetirement,'retire_resources',resource):
            self.assertEqual({'performed':True},feature.finalize())
        self.assertTrue(waited);self.assertEqual([],list(self.model.root.glob('phone-emote-*.json')))
        self.assertTrue(list(self.model.root.glob('emote-retirement-handoff-*.json')))

    def test_active_fixture_cannot_finalize_even_after_resource_restoration(self):
        feature=self.feature();feature.observe(self.observation());self.model.journal.activate(RUN,'a'*32,'cleanup',{})
        feature.cleanup(self.cleanup_call())
        with self.assertRaises(NativeUIError):feature.finalize()
        self.assertIsNotNone(feature.run.store.read())

    def test_public_finalizer_recovers_after_run_and_child_metadata_are_already_removed(self):
        actor=self.start();feature=self.feature(self.primary);actor.step();feature.observe(self.observation())
        self.model.journal.activate(RUN,'a'*32,'cleanup',{});feature.cleanup(self.cleanup_call())
        actor.step();feature.observe(self.observation(1));self.reader.request('/runs/'+RUN,method='DELETE');actor.step()
        discard=PrivateFeatureState.discard
        def lost(store,value):
            if store.path.name=='phone-emote-retirement.json':raise OSError('Synthetic lost final retirement removal')
            return discard(store,value)
        def resource(owner):return self.resource_boundary(owner)
        with patch.object(PhoneEmoteRetirement,'retire_resources',resource):
            with patch.object(PrivateFeatureState,'discard',lost),self.assertRaises(NativeUIError):feature.finalize()
            self.assertIsNone(self.primary.store.read());before=self.model.calls.count('native-read')
            self.assertEqual({'performed':True},self.feature().finalize())
            self.assertGreater(self.model.calls.count('native-read'),before)
        self.assertEqual([],list(self.model.root.glob('phone-emote-*.json')))

    def test_public_finalizer_handles_unissued_admission_failure_without_native_verdict(self):
        # The original failed setup and closed actor are real; the helper only
        # supplies the controlled loopback fixture and synthetic target failure.
        test_emote_unissued_retirement.UnissuedRetirementTests.closed(self)
        feature=self.feature(self.primary);before=self.model.calls.count('native-read')
        with patch.object(self.model,'_native_feature_observer',side_effect=AssertionError('Unissued cleanup invented native restoration')):
            self.assertEqual({'performed':True},feature.finalize())
        self.assertEqual(before,self.model.calls.count('native-read'))
        self.assertEqual([],list(self.model.root.glob('phone-emote-*.json')))

    failed=test_emote_unissued_retirement.UnissuedRetirementTests.failed

    def test_public_finalizer_retires_partial_setup_with_actual_primary_quiet(self):
        test_emote_setup_retirement.SetupRetirementTests.closed(self,'view')
        feature=self.feature(self.primary)
        def resource(owner):return test_emote_setup_retirement.SetupRetirementTests.resource_boundary(self,owner)
        with patch.object(PhoneEmoteRetirement,'retire_resources',resource):
            self.assertEqual({'performed':True},feature.finalize())
        self.assertEqual([],list(self.model.root.glob('phone-emote-*.json')))


if __name__=='__main__':unittest.main()
