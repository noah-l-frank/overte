"""Public facts replay genuine archived source schemas; native data is synthetic."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from adapters.native_clock_join import digest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.lock import ScriptSourceLock
from ios.adapters.emote_controls import project
from ios.adapters.emote_observation import IOSEmoteObservationDecoder
from ios.adapters.emote_sources import IOSEmoteSources
from ios.self_tests.test_ios_emote_controls import NativeBoundary
from ios.self_tests.test_ios_emote_sources import BINDING,RUN,phase
from ios.self_tests.test_ios_emote_world import packet as world_packet
from self_tests.test_emote_rig_measurements import RigPackets


from ios.self_tests.emote_original_fixtures import Originals


class ObservationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.root.chmod(0o700)
        self.lock=ScriptSourceLock(self.root/'script-feature-sources.lock');self.held=self.lock.held();self.held.__enter__()
    def tearDown(self):self.held.__exit__(None,None,None);self.temp.cleanup()
    def decoder(self,owner):return IOSEmoteObservationDecoder(owner,BINDING,'primary',self.root,dict(source='world-render-target'),self.lock,phase_instance='3'*32)
    def test_idle_public_result_replays_immutable_originals_without_freshening(self):
        source=Originals(self.root,self.lock);ref=source.append(18800,baseline=True);original=source.owner.frames[-1]
        proof=dict(kind='idle',baseline=ref,before=None,played=None,inputBarrier=None)
        value=dict(iosEmoteObservationOriginalVersion=1,runId=RUN,role='primary',binding=BINDING,primaryBinding=BINDING,
            sequence=1,ticket='4'*32,source=ref,sourceRecovery=None,peerRecovery=None,proof=proof,peerBefore=None,peerAfter=None,marker=None,imageBefore=None,image=None,
            acquisition={k:original['clockJoin'][k] for k in ('hostBeforeEpochMs','hostAfterEpochMs','hostBeforeMonotonic','hostAfterMonotonic')})
        result=self.decoder(source.owner).derive(value)
        self.assertEqual('idle',result['public']['state']['animation']);self.assertEqual([],result['public']['resources'])
        self.assertEqual(90000,result['public']['capturedEpochMs']);self.assertEqual(18800,original['group']['native']['capturedEpochMs'])
        for fault in ('retime','expected','hash','proof'):
            corrupt=deepcopy(value)
            if fault=='retime':corrupt['acquisition']['hostBeforeEpochMs']+=1
            elif fault=='expected':corrupt['state']=dict(animation='Waving')
            elif fault=='hash':corrupt['source']['sha256']='f'*64
            else:corrupt['proof']['played']=ref
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):self.decoder(source.owner).derive(corrupt)
    def test_all_actual_sit_variants_and_measured_early_restore_come_from_independent_source_bytes(self):
        for name in ('Sit1','Sit2','Sit3'):
            with self.subTest(name=name),tempfile.TemporaryDirectory(dir=self.root) as directory:
                root=Path(directory);lock=ScriptSourceLock(root/'script-feature-sources.lock')
                with lock.held():
                    source=Originals(root,lock,name);baseline=source.append(18800,baseline=True);played=source.append(20000,active=True)
                    decoder=IOSEmoteObservationDecoder(source.owner,BINDING,'primary',root,dict(source='world-render-target'),lock,phase_instance='3'*32)
                    proof=dict(kind='playback',baseline=baseline,before=baseline,played=played,inputBarrier=None)
                    state=decoder.state(source.owner.frames[-1],proof,'4'*32)
                    self.assertEqual(name,state['sit']);self.assertEqual('Sit',state['animation'])
                    source.append(20200,restore_epoch=20100);proof.update(kind='restoration',inputBarrier=played)
                    self.assertTrue(decoder.state(source.owner.frames[-1],proof,'4'*32)['restoredBeforeNominalEnd'])

    def test_loaded_playback_and_restoration_are_not_derived_from_ui_name_or_ack(self):
        source=Originals(self.root,self.lock);baseline=source.append(18800,baseline=True);played=source.append(20000,active=True)
        decoder=self.decoder(source.owner);proof=dict(kind='playback',baseline=baseline,before=baseline,played=played,inputBarrier=None)
        state=decoder.state(source.owner.frames[-1],proof,'4'*32)
        self.assertEqual('Waving',state['animation']);self.assertEqual(1.,state['poseProgress']);self.assertTrue(state['override'])
        current=source.append(20200,restore_epoch=20100)
        proof.update(kind='restoration',inputBarrier=played)
        state=decoder.state(source.owner.frames[-1],proof,'4'*32)
        self.assertFalse(state['override']);self.assertTrue(state['restoredBeforeNominalEnd'])
        corrupt=deepcopy(source.owner.frames[-1]);corrupt['group']['native']['animation']['history']['events'][-1]['capturedEpochMs']=21000
        with self.assertRaises(NativeUIError):decoder.state(corrupt,proof,'4'*32)


if __name__=='__main__':unittest.main()
