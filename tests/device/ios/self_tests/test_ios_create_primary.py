"""Real source/file journals at synthetic native SDK boundaries only."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from unittest.mock import patch

from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import pack,unpack
from ios.adapters.create_primary import CreatePrimary
from ios.adapters.create_primary_measurements import compose
from ios.self_tests import test_ios_create_sources as source_tests
from ios.self_tests.test_ios_create_sources import RUN,BINDING


class CreatePrimaryTests(unittest.TestCase):
    def setUp(self):
        self.h=source_tests.CreateSourcesTests();self.h.setUp();self.addCleanup(self.h.doCleanups)
        self.store=PrivateFeatureState(self.h.root/'ios-create-primary.json')
    def owner(self,source):return CreatePrimary(self.store,self.h.lock,BINDING,RUN,source,lambda:True)
    def test_initial_clean_baseline_uses_two_actual_source_groups_and_historical_reconstruction_reads_no_sdk(self):
        with self.h.held():
            source=self.h.owner();owner=self.owner(source);value=owner.capture()
            self.assertEqual([],value['resources']);self.assertEqual([],value['state']['objects']);self.assertEqual(1,value['sequence'])
            self.assertEqual(2,len(source.frames));counts=deepcopy(self.h.sdk.counts)
            reconstructed=self.owner(source);self.assertEqual(owner.previous,reconstructed.previous);self.assertEqual(counts,self.h.sdk.counts)
            second=owner.capture();self.assertEqual(2,second['sequence']);self.assertGreater(second['capturedEpochMs'],value['capturedEpochMs'])
            self.assertEqual(4,len(source.frames))
    def test_interrupted_observation_keeps_original_packet_and_new_read_never_relabels_old_clocks(self):
        with self.h.held():
            source=self.h.owner();owner=self.owner(source);capture=source.capture;calls=[]
            def fail(label):
                calls.append(label)
                if len(calls)==2:raise NativeUIError('Lost readonly source return')
                return capture(label)
            with patch.object(source,'capture',side_effect=fail),self.assertRaises(NativeUIError):owner.capture()
            retained=deepcopy(owner.state['pending']);self.assertIsNotNone(retained['before']);self.assertIsNone(retained['after'])
            old=owner.frame(retained['before']);owner=self.owner(source);value=owner.capture()
            self.assertEqual(retained,owner.state['interrupted'][0]);self.assertEqual(1,value['sequence'])
            self.assertGreater(value['capturedEpochMs'],old['clockJoin']['hostBeforeEpochMs']);self.assertEqual(3,len(source.frames))
    def test_committed_record_before_index_adoption_recovers_without_repeating_record_acquisition(self):
        with self.h.held():
            source=self.h.owner();owner=self.owner(source);write=self.store.write
            def lose(value,previous):
                state=unpack(value['payload'])[0]
                if state['records']:raise NativeUIError('Lost index adoption')
                return write(value,previous)
            with patch.object(self.store,'write',side_effect=lose),self.assertRaises(NativeUIError):owner.capture()
            self.assertEqual(2,len(source.frames));owner=self.owner(source);value=owner.capture()
            self.assertEqual(2,value['sequence']);self.assertEqual(4,len(source.frames));self.assertEqual(2,len(owner.state['records']))
            self.assertEqual([],owner.state['interrupted'])
    def test_changed_actual_record_or_mutated_source_frame_never_survives_reconstruction(self):
        with self.h.held():
            source=self.h.owner();owner=self.owner(source);owner.capture();record=owner.record_store(1);old=record.read();changed=deepcopy(old)
            entry=unpack(changed['payload'])[0];entry['ticket']='f'*32;changed['payload']=pack([entry]);record.write(changed,old)
            with self.assertRaises(NativeUIError):self.owner(source)
            record.write(old,changed);source.frames[0]['originals']['createAfter']['source']['canRez']=False
            with self.assertRaises(NativeUIError):self.owner(source)
    def test_warm_current_cache_cannot_use_a_mutated_predecessor_as_its_original_native_floor(self):
        with self.h.held():
            source=self.h.owner();owner=self.owner(source);owner.capture();reference=deepcopy(source.state['records'][1])
            owner.frame(reference);before=source.record_store(1).read()
            source.frames[0]['label']='forged-unarchived-predecessor'
            with self.assertRaises(NativeUIError):owner.frame(reference)
            self.assertEqual(before,source.record_store(1).read())
    def test_original_phase_clock_birth_and_lifecycle_joins_reject_stale_or_foreign_groups(self):
        with self.h.held():
            source=self.h.owner();before=source.capture('before');after=source.capture('after');baseline=before['originals']['createBefore']
            for fault in ('ticket','phase','birth','counter','lifecycle','host-duration','host-order','native-order'):
                other=deepcopy(after)
                if fault=='ticket':other['ticket']='f'*32
                elif fault=='phase':other['phaseAfter']['activations'][-1]['ticket']='f'*32
                elif fault=='birth':other['clockJoin']['nativeBefore']['instance']='f'*32
                elif fault=='counter':other['clockJoin']['nativeBefore']['sequence']=before['clockJoin']['nativeAfter']['sequence']
                elif fault=='lifecycle':other['clockJoin']['nativeAfter']['lifecycle']['backgrounds']+=1
                elif fault=='host-duration':other['clockJoin']['hostAfterEpochMs']+=1500;other['clockJoin']['hostAfterMonotonic']+=1.5
                elif fault=='host-order':other['clockJoin']['hostBeforeEpochMs']=before['clockJoin']['hostAfterEpochMs']-1
                else:other['clockJoin']['nativeBefore']['capturedEpochMs']=before['clockJoin']['nativeAfter']['capturedEpochMs']-1
                with self.subTest(fault=fault),self.assertRaises(NativeUIError):compose(RUN,BINDING,1,before,other,baseline,owned_ids=[])


if __name__=='__main__':unittest.main()
