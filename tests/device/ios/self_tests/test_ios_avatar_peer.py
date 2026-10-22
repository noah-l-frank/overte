"""Independent native DTO seams: no actual AvatarMixer or renderer claimed."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import base64
import hashlib
import unittest
from adapters.native_clock_join import digest
from adapters.normal_ui import NativeUIError
from ios.adapters import avatar_peer as peer
from ios.self_tests.test_ios_emote_peer import acquisition,native,PRIMARY,ACTOR,reseal
from ios.self_tests.test_ios_avatar_state import packet as state_packet
from ios.self_tests.test_ios_avatar_renderers import SELF,PEER,RESOURCE,WEARABLE,ENTITY,attach


def state_frame(source,binding,self_id):
    state=state_packet();state.update(iosAvatarStateVersion=2,processId=int(binding['processIdentity']),runId=source['world']['runId'])
    state['clockBefore']=dict(epochMs=20020,monotonicMs=2020);state['clockAfter']=deepcopy(state['clockBefore'])
    state['source'].update(sessionId=self_id,requestedUrl=RESOURCE,resourceUrl=RESOURCE,
        bookmarkFile=dict(source='avatar-bookmarks-persistence',status='ready',reason='',bytes=2,
            sha256=hashlib.sha256(b'{}').hexdigest(),contentBase64=base64.b64encode(b'{}').decode(),identity=dict(device='1',inode='1')))
    state['source']['modelHistory']['processId']=int(binding['processIdentity'])
    renderer=deepcopy(source['renderers']);renderer['clockBefore']=dict(epochMs=20020,monotonicMs=2020);renderer['clockAfter']=deepcopy(renderer['clockBefore'])
    for row in renderer['source']['avatars']:
        if row['rigPose']:row['rigPose']['capturedEpochMs']=20020
        if row['externalPose']:row['externalPose']['capturedEpochMs']=20020
    middle=native(20020,4);middle['processId']=int(binding['processIdentity'])
    originals=dict(state=state,renderers=renderer,native=middle)
    join=deepcopy(source['clockJoin']);join.update(nativeBefore=native(20001,3),nativeAfter=native(20050,5),
        hostBeforeEpochMs=91500.,hostAfterEpochMs=91549.,hostBeforeMonotonic=2.5,hostAfterMonotonic=2.549,
        originalsSha256=digest(originals),sourceTimes=[dict(source='native',field='capturedEpochMs',epochMs=20020)])
    for key in ('nativeBefore','nativeAfter'):join[key]['processId']=int(binding['processIdentity'])
    return dict(avatarSourceGroupVersion=2,originals=originals,clockJoin=join)


def setup():
    before,after=acquisition(),acquisition(True)
    after['clockJoin']['nativeBefore']=native(21000,6);after['clockJoin']['nativeAfter']=native(22000,7)
    primary=acquisition()
    for key in ('world','renderers','receive'):
        primary[key]['processId']=31
    for row in primary['renderers']['source']['avatars']:
        row['sessionId']=PEER if row['self'] else SELF
    primary['renderers']['source']['avatars'].sort(key=lambda row:row['sessionId'])
    primary['world']['source']['domain']['selfSha256']=peer.session_sha(PEER)
    primary['world']['source']['scriptOriginal']['processId']=31
    primary['receive']['source'].update(processId=31,selfSha256=peer.session_sha(PEER))
    for key in ('nativeBefore','nativeAfter'):primary['clockJoin'][key]['processId']=31
    reseal(primary)
    return state_frame(primary,PRIMARY,PEER),primary,before,after,state_frame(before,ACTOR,SELF)


def run(values,wearables=None):return peer.replication(*values,PRIMARY,ACTOR,wearables=wearables or {})


class AvatarPeerTests(unittest.TestCase):
    def test_actual_received_identity_scale_and_loaded_remote_geometry_need_no_motion(self):
        values=setup();after=values[3]
        # One actual incoming record is enough for model/scale identity. No
        # emote movement, remote AnimGraph or changed joints are prerequisites.
        after['receive']['source']['records']=after['receive']['source']['records'][:1]
        after['receive']['source']['receiveSequence']=1;reseal(after)
        value=run(values)
        self.assertEqual(PEER,value['remoteSessionId']);self.assertEqual([1],value['receivedSequences'])
        self.assertTrue(value['modelLoaded']);self.assertEqual(RESOURCE,value['resourceUrl'])
        self.assertNotIn('animation',value);self.assertNotIn('graphLoaded',value['externalPose'])

    def test_foreign_sender_candidate_mixer_stale_metadata_or_unloaded_mesh_is_rejected(self):
        for fault in ('sender','mixer','stale','url','scale','mesh','external','bounds','layout','crossedClock'):
            values=list(setup());primary,_,_,after,_actor=values;row=after['renderers']['source']['avatars'][1]
            if fault=='sender':primary['originals']['state']['source']['sessionId']=SELF
            elif fault=='mixer':after['world']['source']['domain']['avatarMixerSha256']='f'*64
            elif fault=='stale':
                for packet in after['receive']['source']['records']:packet['capturedEpochMs']-=1000
            elif fault=='url':after['receive']['source']['records'][-1]['advertisedModelUrl']=RESOURCE+'?old'
            elif fault=='scale':row['modelScale']=1.5
            elif fault=='mesh':row.update(geometryLoaded=False,rigReady=False,boundsReady=False,bounds=None)
            elif fault=='external':row['externalPose']=None
            elif fault=='bounds':row.update(boundsReady=False,bounds=None)
            elif fault=='layout':row['jointIndices']['Hips']=3;row['hipsIndex']=3
            else:after['clockJoin']['nativeBefore']['capturedEpochMs']=19900
            primary['clockJoin']['originalsSha256']=digest(primary['originals']);reseal(after)
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):run(values)

    def test_actual_wearable_id_remote_hips_geometry_and_whole_tree_absence(self):
        values=list(setup());primary,_p,_before,after,_actor=values
        attach(primary['originals']['renderers'],PEER);attach(after['renderers'],PEER)
        after['renderers']['source']['tree'].update(revisionBefore=2,revisionAfter=2)
        primary['clockJoin']['originalsSha256']=digest(primary['originals']);reseal(after)
        self.assertEqual({ENTITY:WEARABLE},run(values,{ENTITY:WEARABLE})['wearables'])
        after['renderers']['source']['avatarEntities'][0]['parentJointIndex']=0;reseal(after)
        with self.assertRaises(NativeUIError):run(values,{ENTITY:WEARABLE})
        with self.assertRaises(NativeUIError):run(values,{ENTITY:None})
        after['renderers']['source']['avatarEntities']=[]
        after['renderers']['source']['tree'].update(totalEntities=0,entities=[]);reseal(after)
        self.assertEqual({ENTITY:None},run(values,{ENTITY:None})['wearables'])

    def test_missing_model_requires_actual_remote_fallback_or_actual_unavailable_geometry(self):
        for loaded in (True,False):
            values=list(setup());primary,_p,_before,after,actor=values
            source=primary['originals']['state']['source'];own=primary['originals']['renderers']['source']['avatars'][1]
            remote=after['renderers']['source']['avatars'][1];missing=RESOURCE+'?missing'
            source.update(requestedUrl=missing,resourceUrl=source['defaultResourceUrl'] if loaded else missing,
                geometryLoaded=loaded,rigReady=loaded)
            own.update(requestedUrl=missing,resourceUrl=source['resourceUrl'],geometryLoaded=loaded,rigReady=loaded)
            actor['originals']['state']['source']['defaultResourceUrl']='file:///actual-actor-default.fst'
            remote.update(requestedUrl=missing,resourceUrl='file:///actual-actor-default.fst' if loaded else missing,
                geometryLoaded=loaded,rigReady=loaded)
            if not loaded:
                for row in (own,remote):row.update(boundsReady=False,bounds=None)
            for record in after['receive']['source']['records']:record['advertisedModelUrl']=missing
            for frame in (primary,actor):frame['clockJoin']['originalsSha256']=digest(frame['originals'])
            reseal(after)
            with self.subTest(loaded=loaded):self.assertIs(loaded,run(values)['modelLoaded'])
            if loaded:
                remote['resourceUrl']=source['defaultResourceUrl'];reseal(after)
                with self.assertRaises(NativeUIError):run(values)

    def test_primary_local_native_epochs_cannot_be_compared_to_actor_epochs(self):
        values=list(setup());primary,source,_before,_after,_actor=values
        # Shift the genuine primary clock domain only, retaining all original
        # primary brackets and source timestamps in that domain.
        for packet in (source['world'],source['renderers']):
            for clock in ('clockBefore','clockAfter'):packet[clock]['epochMs']+=100000
        original=source['world']['source']['scriptOriginal']
        for key in ('requestedEpochMs','capturedEpochMs'):original[key]+=100000
        for packet in (source['receive'],):
            for key in ('requestedEpochMs','capturedEpochMs'):packet[key]+=100000
        for frame in (source,primary):
            packets=[frame['clockJoin'][key] for key in ('nativeBefore','nativeAfter')]
            if 'originals' in frame:packets.append(frame['originals']['native'])
            for packet in packets:
                for field in ('requestedEpochMs','capturedEpochMs'):packet[field]+=100000
                packet['animation']['capturedEpochMs']+=100000;packet['animation']['clip']['evaluatedEpochMs']+=100000
                packet['animationFence']['requestedEpochMs']+=100000
        for packet in (primary['originals']['state'],primary['originals']['renderers']):
            for clock in ('clockBefore','clockAfter'):packet[clock]['epochMs']+=100000
        for rendered in (source['renderers'],primary['originals']['renderers']):
            for row in rendered['source']['avatars']:
                for key in ('rigPose','externalPose'):
                    if row[key]:row[key]['capturedEpochMs']+=100000
        source['clockJoin']['sourceTimes'][0]['epochMs']+=100000
        primary['clockJoin']['sourceTimes'][0]['epochMs']+=100000
        reseal(source);primary['clockJoin']['originalsSha256']=digest(primary['originals'])
        self.assertTrue(run(values)['modelLoaded'])


if __name__=='__main__':unittest.main()
