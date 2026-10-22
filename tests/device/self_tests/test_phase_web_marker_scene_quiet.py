"""Real authenticated scene-stage HTTP; native lifecycle decoder is modeled."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from unittest.mock import patch
from adapters.native_clock_join import digest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.phase_retirement_publisher import PhaseRetirementPublisher,PublicationPending
from adapters.phase_retirement_reader import PhaseRetirementReader
from feature_journeys.retirement_receipts import WEB_SCENE_STAGE,WEB_SCENE_CLASSES,body
from self_tests.test_completed_frame_lease import BINDING
from self_tests.test_phase_retirement_publisher import PhaseRetirementTests


class WebMarkerSceneQuietTests(unittest.TestCase):
    def setUp(self):
        self.f=PhaseRetirementTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.f.attach('world-web')
    def scene(self,sequence=1):
        original=self.f.original(sequence);derived=self.f.known[digest(original)];public=derived.pop('public')
        derived['scene']=dict(webMarkerSceneQuietVersion=1,runId=self.f.run,sequence=sequence,capturedEpochMs=public['capturedEpochMs'],
            quiet=list(WEB_SCENE_CLASSES),remaining=['native-process-resources'],lifecycle=public['lifecycle'])
        return original
    def owner(self):
        return PhaseRetirementPublisher(PrivateFeatureState(self.f.root/('phase-retirement-'+self.f.area+'-'+self.f.run+'-actor.json')),
            BINDING,self.f.phase,self.f.lock,lambda:True,self.f.validate_original,epoch_ms=lambda:self.f.now,monotonic=lambda:10.1,stage=WEB_SCENE_STAGE)
    def reader(self,*,path=None):
        template=self.f.primary_reader()
        return PhaseRetirementReader(PrivateFeatureState(path or self.f.root/('web-marker-scene-reader-'+self.f.area+'-'+self.f.run+'.json')),template.binding,
            template.phase,template.guard,template.admitted_original,template.validate_admission,
            epoch_ms=lambda:self.f.now,monotonic=lambda:10.1,stage=WEB_SCENE_STAGE)
    def test_explicit_two_areas_keep_native_process_owned_and_default_complete_reader_refuses_scene(self):
        for area in ('world-web','emotes'):
            self.f.attach(area)
            with self.subTest(area=area),self.f.lock.held():
                owner=self.owner();self.assertEqual(1,owner.publish(self.scene()))
                self.assertEqual(3,owner.previous['phaseRetirementPublisherVersion'])
            journal=self.f.adapter.request('/runs/'+self.f.run+'/retirements');entry=journal['entries'][0]
            self.assertEqual(3,journal['phaseRetirementJournalVersion']);self.assertEqual(WEB_SCENE_STAGE,entry['stage'])
            self.assertEqual(['native-process-resources'],entry['scene']['remaining']);self.assertNotIn('cleanup',entry)
            self.assertNotIn('state',entry['scene']);self.assertNotIn('resources',entry['scene']);self.assertNotIn('artifacts',entry['scene'])
            self.assertEqual(entry,self.reader().read()['entry'])
            with self.assertRaises(PublicationPending):self.f.primary_reader().read()
    def test_default_complete_writer_stays_two_and_mixed_original_versions_survive_explicit_scene_then_complete(self):
        with self.f.lock.held():
            self.owner().publish(self.scene());self.assertEqual(2,self.f.owner().publish(self.f.original(2)))
        journal=self.f.adapter.request('/runs/'+self.f.run+'/retirements')
        self.assertEqual([3,2],[entry['phaseRetirementVersion'] for entry in journal['entries']])
        reader=self.f.primary_reader();self.assertEqual('complete',reader.read()['entry']['stage'])
        self.assertEqual(3,reader.previous['phaseRetirementReaderVersion'])
        self.f.attach('create')
        with self.f.lock.held():
            owner=self.f.owner();owner.publish(self.f.original());self.assertEqual(2,owner.previous['phaseRetirementPublisherVersion'])
        self.assertEqual(2,self.f.adapter.request('/runs/'+self.f.run+'/retirements')['phaseRetirementJournalVersion'])
    def test_unknown_committed_POST_uses_original_read_resolution_without_new_scene_send(self):
        with self.f.lock.held():
            original=self.scene();owner=self.owner();calls,request=self.f.posts('lost-after')
            with patch.object(self.f.actor,'request',side_effect=request),self.assertRaises(OSError):owner.publish(original)
            again,request=self.f.posts('normal')
            with patch.object(self.f.actor,'request',side_effect=request):self.assertTrue(self.owner().resolve())
            self.assertEqual(1,len(calls));self.assertEqual([],again)
        self.assertEqual(['native-process-resources'],self.reader().read()['entry']['scene']['remaining'])
    def test_unknown_uncommitted_scene_blocks_new_scene_or_complete_without_resending(self):
        with self.f.lock.held():
            original=self.scene();calls,request=self.f.posts('lost-before')
            with patch.object(self.f.actor,'request',side_effect=request),self.assertRaises(OSError):self.owner().publish(original)
            again,request=self.f.posts('normal')
            with patch.object(self.f.actor,'request',side_effect=request):
                for value in (original,self.scene(2)):
                    with self.assertRaises(PublicationPending):self.owner().publish(value)
                with self.assertRaises(PublicationPending):self.f.owner().publish(self.f.original(3))
            self.assertEqual(1,len(calls));self.assertEqual([],again)
    def test_closed_summary_foreign_area_full_complete_claim_version_or_missing_quiet_cannot_be_published(self):
        with self.f.lock.held():_derived,valid=self.owner().original(self.scene())
        variants=[]
        for edit in ({'remaining':[]},{'remaining':['account-session']},{'resources':[]},{'state':{}},
            {'webMarkerSceneQuietVersion':True},{'quiet':list(WEB_SCENE_CLASSES)[:-1]},{'sequence':True}):
            value=deepcopy(valid);value['scene'].update(edit);variants.append(value)
        for edit in ({'area':'create'},{'area':'avatar-people'},{'phaseRetirementVersion':2},{'phaseRetirementVersion':1},
            {'stage':'complete'},{'stage':'avatar-scene-retired'},{'cleanup':{}},{'stage':'anything'}):
            value=deepcopy(valid);value.update(edit);variants.append(value)
        for value in variants:
            with self.subTest(value=value),self.assertRaises(ValueError):body(value)
        self.f.attach('create')
        with self.f.lock.held(),self.assertRaises(NativeUIError):self.owner()
    def test_scene_after_complete_duplicate_scene_and_wrong_credentials_have_no_new_commit(self):
        with self.f.lock.held():
            self.owner().publish(self.scene());_derived,duplicate=self.owner().original(self.scene(2))
        for client in (self.f.actor,self.f.reader,self.f.adapter):
            with self.subTest(client=client is self.f.actor),self.assertRaises(ValueError):client.request('/runs/'+self.f.run+'/retirements',duplicate)
        self.assertEqual(1,len(self.f.adapter.request('/runs/'+self.f.run+'/retirements')['entries']))
        self.f.attach('emotes')
        with self.f.lock.held():
            self.f.owner().publish(self.f.original());_derived,late=self.owner().original(self.scene(2))
        with self.assertRaises(ValueError):self.f.actor.request('/runs/'+self.f.run+'/retirements',late)
    def test_new_scene_still_requires_original_native_quiet_and_does_not_upgrade_default_writer(self):
        with self.f.lock.held():
            original=self.scene()
            with self.assertRaises(NativeUIError):self.f.owner().publish(original)
            self.f.known[digest(original)]['retirement']['quiet']['nativeBeforeLastMonotonicMs']-=1
            with self.assertRaises(ValueError):self.owner().publish(original)
        self.assertEqual([],self.f.adapter.request('/runs/'+self.f.run+'/retirements')['entries'])
    def test_real_reader_metadata_from_another_area_run_cannot_be_reused_as_current_admission(self):
        with self.f.lock.held():self.owner().publish(self.scene())
        old=self.reader();old.read();path=old.store.path;original=deepcopy(old.previous)
        self.f.attach('emotes')
        with self.assertRaises(NativeUIError):self.reader(path=path)
        self.assertEqual(original,PrivateFeatureState(path).read())


if __name__=='__main__':unittest.main()
