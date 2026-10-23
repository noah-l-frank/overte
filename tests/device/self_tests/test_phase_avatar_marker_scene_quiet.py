"""Explicit Avatar marker quiet stage retains account/Login/process duties."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from unittest.mock import patch
from adapters.native_clock_join import digest
from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.phase_retirement_publisher import PhaseRetirementPublisher,PublicationPending
from adapters.phase_retirement_reader import PhaseRetirementReader
from feature_journeys import retirement_receipts as rules
from self_tests import test_phase_retirement_publisher as old
from self_tests.test_completed_frame_lease import BINDING


class AvatarMarkerSceneQuietTests(unittest.TestCase):
    def setUp(self):
        self.f=old.PhaseRetirementTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.f.attach('avatar-people')
    def scene(self,sequence=1):
        original=self.f.original(sequence);derived=self.f.known[digest(original)];public=derived.pop('public')
        derived['scene']=dict(avatarMarkerSceneQuietVersion=1,runId=self.f.run,sequence=sequence,capturedEpochMs=public['capturedEpochMs'],
            quiet=list(rules.AVATAR_SCOPED_CLASSES),remaining=list(rules.AVATAR_SCOPED_REMAINING),lifecycle=public['lifecycle'])
        return original
    def owner(self):
        return PhaseRetirementPublisher(PrivateFeatureState(self.f.root/('phase-retirement-'+self.f.area+'-'+self.f.run+'-actor.json')),
            BINDING,self.f.phase,self.f.lock,lambda:True,self.f.validate_original,epoch_ms=lambda:self.f.now,monotonic=lambda:10.1,stage=rules.AVATAR_SCOPED_STAGE)
    def reader(self):
        template=self.f.primary_reader()
        return PhaseRetirementReader(PrivateFeatureState(self.f.root/'avatar-marker-scene-reader.json'),template.binding,
            template.phase,template.guard,template.admitted_original,template.validate_admission,
            epoch_ms=lambda:self.f.now,monotonic=lambda:10.1,stage=rules.AVATAR_SCOPED_STAGE)
    def test_actual_authenticated_stage4_retains_login_roots_and_default_complete_reader_refuses(self):
        with self.f.lock.held():owner=self.owner();self.assertEqual(1,owner.publish(self.scene()))
        entry=self.reader().read()['entry'];self.assertEqual(4,entry['phaseRetirementVersion'])
        self.assertEqual(list(rules.AVATAR_SCOPED_REMAINING),entry['scene']['remaining']);self.assertNotIn('resources',entry['scene'])
        self.assertNotIn('qt-ui',entry['scene']['quiet']);self.assertIn('avatar-people-qt-ui',entry['scene']['quiet'])
        for key in ('state','facts','artifacts','cleanup'):self.assertNotIn(key,entry['scene'])
        with self.assertRaises(PublicationPending):self.f.primary_reader().read()
    def test_lost_committed_post_resolves_once_from_unchanged_actual_receipt(self):
        with self.f.lock.held():
            original=self.scene();owner=self.owner();calls,request=self.f.posts('lost-after')
            with patch.object(self.f.actor,'request',side_effect=request),self.assertRaises(OSError):owner.publish(original)
            again,request=self.f.posts('normal')
            with patch.object(self.f.actor,'request',side_effect=request):self.assertTrue(self.owner().resolve())
            self.assertEqual(1,len(calls));self.assertEqual([],again)
        self.assertEqual(rules.AVATAR_SCOPED_STAGE,self.reader().read()['entry']['stage'])
    def test_lost_uncommitted_post_owns_the_send_and_blocks_any_new_scene_or_complete(self):
        with self.f.lock.held():
            original=self.scene();calls,request=self.f.posts('lost-before')
            with patch.object(self.f.actor,'request',side_effect=request),self.assertRaises(OSError):self.owner().publish(original)
            again,request=self.f.posts('normal')
            with patch.object(self.f.actor,'request',side_effect=request):
                for value in (original,self.scene(2)):
                    with self.assertRaises(PublicationPending):self.owner().publish(value)
                with self.assertRaises(PublicationPending):self.f.owner().publish(self.f.original(3))
            self.assertEqual(1,len(calls));self.assertEqual([],again)
    def test_wrong_area_stage_legacy_version_or_empty_remaining_cannot_relabel_new_summary(self):
        with self.f.lock.held():_derived,valid=self.owner().original(self.scene())
        for edit in ({'remaining':[]},{'remaining':['account-session']},{'resources':[]},{'state':{}},
            {'avatarMarkerSceneQuietVersion':True},{'quiet':list(rules.SCENE_CLASSES)},{'sequence':True}):
            value=deepcopy(valid);value['scene'].update(edit)
            with self.subTest(edit=edit),self.assertRaises(ValueError):rules.body(value)
        for edit in ({'area':'emotes'},{'area':'world-web'},{'stage':rules.SCENE_STAGE},{'stage':rules.WEB_SCENE_STAGE},
            {'stage':'complete'},{'phaseRetirementVersion':1},{'phaseRetirementVersion':2},{'phaseRetirementVersion':3}):
            value=deepcopy(valid);value.update(edit)
            with self.subTest(edit=edit),self.assertRaises(ValueError):rules.body(value)
        self.f.attach('create')
        with self.f.lock.held(),self.assertRaises(NativeUIError):self.owner()
    def test_rehashed_historical_duplicate_or_scene_after_complete_is_rejected_like_live_journal(self):
        with self.f.lock.held():
            owner=self.owner();owner.publish(self.scene());journal=self.f.server.phase_retirements.snapshot(self.f.run)
            duplicate=deepcopy(journal['entries'][0]);duplicate.update(sequence=2,actorSequence=2);duplicate['scene']['sequence']=2
            duplicate['receiptSha256']=digest({key:value for key,value in duplicate.items() if key not in ('sequence','receivedEpochMs','receiptSha256')})
            bad=deepcopy(journal);bad['entries'].append(duplicate)
            with self.assertRaises((ValueError,RuntimeError)):owner.journal(bad)
            _derived,complete=self.f.owner().original(self.f.original(2));complete['actorSequence']=1;complete['cleanup']['sequence']=1
            bad['entries']=[dict(complete,sequence=1,receivedEpochMs=self.f.now,receiptSha256=digest(complete)),duplicate]
            with self.assertRaises((ValueError,RuntimeError)):owner.journal(bad)
    def test_old_default_complete_stays_writer2_and_new_scene_cannot_qualify_without_original_native_quiet(self):
        with self.f.lock.held():
            original=self.scene()
            with self.assertRaises((ValueError,RuntimeError)):self.f.owner().publish(original)
            self.f.known[digest(original)]['retirement']['quiet']['nativeBeforeLastMonotonicMs']-=1
            with self.assertRaises(ValueError):self.owner().publish(original)
        self.assertEqual([],self.f.server.phase_retirements.snapshot(self.f.run)['entries'])
        self.f.attach('create')
        with self.f.lock.held():
            owner=self.f.owner();owner.publish(self.f.original());self.assertEqual(2,owner.previous['phaseRetirementPublisherVersion'])
    def test_literal_v1_original_journal_files_stay_readable_without_conversion_or_http(self):
        from ios.self_tests import test_ios_avatar_scene_retirement as legacy
        legacy.AvatarSceneRetirementTests.test_v1_original_writer_files_and_wire_are_read_without_conversion_or_http(self)
    def test_an_old_scene_or_completed_ticket_cannot_be_given_a_new_scoped_scene(self):
        with self.f.lock.held():
            original=self.f.original();derived=self.f.known[digest(original)];public=derived.pop('public')
            derived['scene']=dict(sceneRetirementVersion=1,runId=self.f.run,sequence=1,capturedEpochMs=public['capturedEpochMs'],
                retired=list(rules.SCENE_CLASSES),remaining=['account-session'],lifecycle=public['lifecycle'])
            self.f.owner().publish(original);_derived,late=self.owner().original(self.scene(2))
        for client in (self.f.actor,self.f.reader,self.f.adapter):
            with self.subTest(reader=client is self.f.reader),self.assertRaises(ValueError):client.request('/runs/'+self.f.run+'/retirements',late)
        self.assertEqual(1,len(self.f.server.phase_retirements.snapshot(self.f.run)['entries']))


if __name__=='__main__':unittest.main()
