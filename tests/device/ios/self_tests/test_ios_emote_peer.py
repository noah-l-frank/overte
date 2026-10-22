"""Actual source schema counterexamples at synthetic independent peer bounds."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from adapters.native_clock_join import digest
from adapters.normal_ui import NativeUIError
from ios.adapters import emote_peer as peer
from ios.self_tests.test_ios_emote_world import packet as world_packet,RUN
from ios.self_tests.test_ios_avatar_renderers import packet as renderer_packet,SELF,PEER,RESOURCE
from ios.self_tests.test_ios_emote_sources import BINDING
from self_tests.test_native_avatar_receive import Boundary as ReceiveBoundary,record
from self_tests.test_native_feature_observation import Boundary as NativeBoundary

PRIMARY=BINDING|dict(processIdentity='31',sessionId='primary-sdk',targetFingerprint='1'*64)
ACTOR=BINDING|dict(processIdentity='42',sessionId='actor-sdk',targetFingerprint='2'*64)


def native(epoch,sequence):
    boundary=NativeBoundary();boundary.sequence=sequence-1;boundary.send(dict(commandId='ios-'+format(sequence,'032x')))
    value=boundary.sample;value.update(processId=42,requestedEpochMs=epoch,capturedEpochMs=epoch)
    value['animation']['capturedEpochMs']=epoch;value['animation']['clip']['evaluatedEpochMs']=epoch
    value['animationFence']['requestedEpochMs']=epoch;return value


def acquisition(later=False):
    start,end=(21000,22000) if later else (19000,20000);base=21000 if later else 20000
    world=world_packet(42);world['source']['domain']['selfSha256']=peer.session_sha(SELF)
    world['source']['domain']['avatarMixerSha256']='c'*64
    for clock in ('clockBefore','clockAfter'):world[clock]['epochMs']=base;world[clock]['monotonicMs']+=base-20000
    scripts=world['source']['scriptOriginal'];scripts.update(requestedEpochMs=base,capturedEpochMs=base)
    if later:world.update(requestId='ios-'+'1'*32,sequence=2)
    renderer=renderer_packet();renderer['runId']=RUN
    renderer['clockBefore']=dict(epochMs=base,monotonicMs=base-18000)
    renderer['clockAfter']=dict(epochMs=base,monotonicMs=base-18000)
    for row in renderer['source']['avatars']:
        if row['rigPose']:row['rigPose'].update(capturedEpochMs=base,evaluationSequence=101 if later else 100)
        if row['externalPose']:
            pose=row['externalPose'];pose.update(capturedEpochMs=base,evaluationSequence=11 if later else 10,totalJoints=3,
                joints=[[0,0,0,1,.1 if later else 0,0,0],[0,0,0,1,0,0,0],[0,0,0,1,0,0,0]])
    if later:renderer.update(requestId='ios-'+'2'*32,sequence=2)
    boundary=ReceiveBoundary()
    if later:
        boundary.records=[record(1,.1),record(2,.2)]
        for row in boundary.records:
            row.update(capturedEpochMs=20000+row['receiveSequence'],avatarSha256=peer.session_sha(PEER),jointCount=3,
                advertisedModelUrl=RESOURCE)
            row['joints']=[dict(index=i,rotation=[0,0,0,1],translation=[.1*row['receiveSequence'],0,0]) for i in range(3)]
        boundary.sequence=1
    boundary.send(dict(schemaVersion=1,commandId='ios-'+('4' if later else '3')*32,action='feature-avatar-receive-observe'))
    receive=boundary.current;receive.update(processId=42,requestedEpochMs=base,capturedEpochMs=base)
    receive['source'].update(processId=42,selfSha256=peer.session_sha(SELF))
    originals=dict(world=world,receive=receive,renderers=renderer)
    join=dict(clockJoinVersion=1,hostBeforeEpochMs=93000. if later else 90000.,hostAfterEpochMs=94000. if later else 91000.,
        hostBeforeMonotonic=4. if later else 1.,hostAfterMonotonic=5. if later else 2.,
        nativeBefore=native(start,3 if later else 1),nativeAfter=native(end,4 if later else 2),
        originalsSha256=digest(originals),sourceTimes=[dict(source='receive',field='capturedEpochMs',epochMs=base)])
    return dict(originals,clockJoin=join)


def setup():
    primary=world_packet();primary['source']['domain'].update(selfSha256=peer.session_sha(PEER),avatarMixerSha256='c'*64)
    return primary,acquisition(),acquisition(True)


def reseal(value):value['clockJoin']['originalsSha256']=digest({k:value[k] for k in ('world','receive','renderers')})


class PeerTests(unittest.TestCase):
    def test_actual_sender_mixer_received_motion_and_external_rendered_pose_join(self):
        primary,before,after=setup();value=peer.movement(primary,PRIMARY,before,after,ACTOR)
        self.assertEqual(PEER,value['remoteSessionId']);self.assertEqual([1,2],value['receivedSequences'])
        self.assertNotIn('animation',value);self.assertNotIn('sit',value)
        self.assertEqual(21000,value['renderedAfter']['capturedEpochMs'])

    def test_foreign_self_serverless_and_other_candidate_cannot_supply_independent_peer(self):
        for fault in ('self','mixer','serverless','domain','sameTarget','candidate'):
            primary,before,after=setup();binding=deepcopy(ACTOR)
            if fault=='self':primary['source']['domain']['selfSha256']=peer.session_sha(SELF)
            elif fault=='mixer':primary['source']['domain']['avatarMixerSha256']='f'*64
            elif fault=='serverless':after['world']['source']['domain']['serverless']=True
            elif fault=='domain':after['world']['source']['domain']['domainId']='11111111-2222-4111-8111-111111111111'
            elif fault=='sameTarget':binding['targetFingerprint']=PRIMARY['targetFingerprint']
            else:binding['artifactSha256']='f'*64
            reseal(after)
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):peer.movement(primary,PRIMARY,before,after,binding)

    def test_frozen_local_rig_advertised_pose_or_retimed_remote_serial_never_proves_peer_motion(self):
        for fault in ('legacy','noExternal','frozen','antipodal','retimed','noPackets','oldPackets','local','replica','wrongModel','layout'):
            primary,before,after=setup();row=after['renderers']['source']['avatars'][1]
            if fault=='legacy':
                after['renderers']['iosAvatarRenderersVersion']=2
                for item in after['renderers']['source']['avatars']:item.pop('externalPose')
            elif fault=='noExternal':row['externalPose']=None
            elif fault=='frozen':row['externalPose']['joints']=deepcopy(before['renderers']['source']['avatars'][1]['externalPose']['joints'])
            elif fault=='antipodal':
                row['externalPose']['joints']=deepcopy(before['renderers']['source']['avatars'][1]['externalPose']['joints'])
                for joint in row['externalPose']['joints']:joint[:4]=[-n for n in joint[:4]]
            elif fault=='retimed':row['externalPose']['evaluationSequence']=10
            elif fault=='noPackets':after['receive']['source'].update(receiveSequence=0,records=[])
            elif fault=='oldPackets':
                for record in after['receive']['source']['records']:record['capturedEpochMs']-=1000
            elif fault=='local':row['self']=True
            elif fault=='replica':row['replicated']=True
            elif fault=='wrongModel':row['resourceUrl']=RESOURCE+'?different'
            else:row['jointIndices']['Hips']=3;row['hipsIndex']=3
            reseal(after)
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):peer.movement(primary,PRIMARY,before,after,ACTOR)


if __name__=='__main__':unittest.main()
