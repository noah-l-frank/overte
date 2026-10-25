"""Explicit Avatar held-marker stage preserves all complete/legacy meanings.

These tests require the actual held-stage protocol integration. A separate
subprocess may qualify an unintegrated patch in memory, without changing the
repository or claiming that its production entrypoint is integrated.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from unittest.mock import patch
from adapters.native_clock_join import digest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.phase_retirement_publisher import PhaseRetirementPublisher,PublicationPending
from adapters.phase_retirement_reader import PhaseRetirementReader
from feature_journeys.retirement_receipts import AVATAR_HELD_STAGE,AVATAR_HELD_CLASSES,AVATAR_HELD_REMAINING,body
from self_tests.test_completed_frame_lease import BINDING
from self_tests import test_phase_retirement_publisher as legacy

class AvatarHeldStage5Tests(unittest.TestCase):
    def setUp(self):
        self.f=legacy.PhaseRetirementTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.f.attach('avatar-people')
    def owner(self):
        f=self.f
        return PhaseRetirementPublisher(PrivateFeatureState(f.root/('phase-retirement-'+f.area+'-'+f.run+'-actor.json')),
            BINDING,f.phase,f.lock,lambda:True,f.validate_original,epoch_ms=lambda:f.now,monotonic=lambda:10.1,stage=AVATAR_HELD_STAGE)
    def original(self,sequence=1):
        original=self.f.original(sequence);proof=self.f.known[digest(original)];public=proof.pop('public')
        proof['scene']=dict(avatarHeldMarkerSceneQuietVersion=1,runId=self.f.run,sequence=sequence,capturedEpochMs=public['capturedEpochMs'],
            quiet=list(AVATAR_HELD_CLASSES),remaining=list(AVATAR_HELD_REMAINING),lifecycle=deepcopy(public['lifecycle']))
        return original
    def reader(self,stage):
        f=self.f;t=f.primary_reader()
        return PhaseRetirementReader(PrivateFeatureState(f.root/'held-scene-reader.json'),t.binding,t.phase,t.guard,t.admitted_original,t.validate_admission,
            epoch_ms=lambda:f.now,monotonic=lambda:10.1,stage=stage)
    def test_real_scene5_POST_and_read_never_satisfy_default_complete(self):
        with self.f.lock.held():self.assertEqual(1,self.owner().publish(self.original()))
        value=self.reader(AVATAR_HELD_STAGE).read()['entry'];self.assertEqual(5,value['phaseRetirementVersion']);self.assertEqual(AVATAR_HELD_STAGE,value['stage'])
        self.assertEqual(list(AVATAR_HELD_REMAINING),value['scene']['remaining'])
        with self.assertRaises(PublicationPending):self.f.primary_reader().read()
    def test_lost_real_POST_return_resolves_without_second_publication(self):
        with self.f.lock.held():
            original=self.original();calls,request=self.f.posts('lost-after')
            with patch.object(self.f.actor,'request',side_effect=request),self.assertRaises(OSError):self.owner().publish(original)
            later,request=self.f.posts('normal')
            with patch.object(self.f.actor,'request',side_effect=request):self.assertTrue(self.owner().resolve());self.assertEqual(1,self.owner().publish(original))
            self.assertEqual(1,len(calls));self.assertEqual([],later)
    def test_unknown_actual_POST_cannot_reissue_or_change_to_complete(self):
        with self.f.lock.held():
            original=self.original();calls,request=self.f.posts('lost-before')
            with patch.object(self.f.actor,'request',side_effect=request),self.assertRaises(OSError):self.owner().publish(original)
            again,request=self.f.posts('normal')
            with patch.object(self.f.actor,'request',side_effect=request):
                for candidate in (original,self.f.original(2)):
                    with self.assertRaises(PublicationPending):self.owner().publish(candidate)
            self.assertEqual(1,len(calls));self.assertEqual([],again)
    def test_version_stage_area_and_actual_remaining_grammar_remain_closed(self):
        with self.f.lock.held():_proof,good=self.owner().original(self.original())
        variants=[]
        for change in ({'stage':'complete'},{'area':'emotes'},{'area':'world-web'},{'phaseRetirementVersion':4},{'phaseRetirementVersion':True}):
            value=deepcopy(good);value.update(change);variants.append(value)
        for change in ({'remaining':[]},{'quiet':list(AVATAR_HELD_CLASSES)+['native-process-resources']},{'resources':[]},{'avatarHeldMarkerSceneQuietVersion':True}):
            value=deepcopy(good);value['scene'].update(change);variants.append(value)
        for value in variants:
            with self.subTest(value=value),self.assertRaises(ValueError):body(value)
    def test_rehashed_second_scene_in_same_ticket_remains_invalid(self):
        with self.f.lock.held():
            owner=self.owner();owner.publish(self.original());journal=self.f.server.phase_retirements.snapshot(self.f.run)
            row=deepcopy(journal['entries'][0]);row.update(sequence=2,actorSequence=2);row['scene']['sequence']=2
            row['receiptSha256']=digest({key:value for key,value in row.items() if key not in ('sequence','receivedEpochMs','receiptSha256')})
            journal['entries'].append(row)
            with self.assertRaises((ValueError,RuntimeError)):owner.journal(journal)

if __name__=='__main__':unittest.main()
