"""Declared independent SDK source packets; no device, native parser or render.

Templates are instantiated and stamped by this synthetic producer before any
original is acquired. No retained original is rewritten or retimed.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import uuid
from adapters.native_clock_join import digest
from ios.self_tests import test_ios_create_state as create
from ios.self_tests.test_ios_create_files import BINDING
from ios.self_tests.test_ios_create_peer import domain_pair
from ios.self_tests.test_ios_assets_model_origin import Boundary as Origin
from self_tests.test_native_feature_observation import Boundary as Native


def instantiate_native(epoch,pid,instance,sequence):
    producer=Native()
    for number in range(sequence):producer.send(dict(schemaVersion=1,action='feature-native-observe',commandId='ios-'+uuid.uuid4().hex))
    value=deepcopy(producer.sample)
    def stamp(item):
        if type(item) is dict:
            for key,child in item.items():
                if key.endswith('EpochMs') and type(child) is int:item[key]=epoch+(child-20000)
                else:stamp(child)
        elif type(item) is list:
            for child in item:stamp(child)
    stamp(value);value.update(processId=pid,instance=instance);return value


def pair(*,actor_pid=43):
    frames=[];body=None
    for role,pid,session,fingerprint in (('actor-primary',42,create.SESSION,BINDING['targetFingerprint']),
            ('actor',actor_pid,'55555555-5555-4555-8555-555555555555','a'*64)):
        before=create.version2(create.packet());row=create.add_model(before);create.version2(before)
        before.update(iosCreateStateVersion=3,processId=pid,instance=uuid.uuid4().hex,requestId='ios-'+uuid.uuid4().hex)
        before['source']['localSessionId']=session;before['source']['tree']['treeInstance']=uuid.uuid4().hex
        row.update(modelURL='atp:/e2e-'+create.RUN+'/asset-stand.fbx',sourceUrl='',userData='',collisionless=False)
        before['clockBefore'].update(epochMs=create.EPOCH+10,monotonicMs=10);before['clockAfter'].update(epochMs=create.EPOCH+12,monotonicMs=12)
        after=deepcopy(before);after.update(requestId='ios-'+uuid.uuid4().hex,sequence=2)
        after['clockBefore'].update(epochMs=create.EPOCH+50,monotonicMs=50);after['clockAfter'].update(epochMs=create.EPOCH+52,monotonicMs=52)
        domain_stamp=deepcopy(before);domain_stamp['clockAfter']['epochMs']=create.EPOCH+20
        domain=domain_pair(domain_stamp,domain_stamp)[0]
        origin=Origin(create.EPOCH+10);origin.state['tree']=deepcopy(before['source']['tree']);origin.state['localSessionId']=session
        origin.state['history']['instance']=uuid.uuid4().hex;origin.row['id']=uuid.uuid4().hex
        origin.state['models'][0]['origin']['geometry']['readerId']=origin.row['id']
        origin.mutate=lambda value,pid=pid:value.update(processId=pid,instance=uuid.uuid4().hex)
        origin.send(dict(schemaVersion=1,action='feature-ios-assets-model-origin',commandId='ios-'+uuid.uuid4().hex,runId=create.RUN))
        original=json.loads(origin.raw);body=deepcopy(origin.row)
        binding=dict(BINDING,processIdentity=str(pid),targetFingerprint=fingerprint,sessionId='scene-'+role)
        instance=uuid.uuid4().hex;first=instantiate_native(create.EPOCH,pid,instance,1);last=instantiate_native(create.EPOCH+100,pid,instance,2)
        originals=dict(nativeBarrier=first,createBefore=before,domain=domain,origin=original,createAfter=after)
        clock=dict(clockJoinVersion=1,hostBeforeEpochMs=1900000000000,hostAfterEpochMs=1900000000100,
            hostBeforeMonotonic=10.,hostAfterMonotonic=10.1,nativeBefore=first,nativeAfter=last,
            sourceTimes=[dict(source='nativeBarrier',field='capturedEpochMs',epochMs=create.EPOCH)],originalsSha256=digest(originals))
        frames.append(dict(assetSceneSourceFrameVersion=1,binding=binding,runId=create.RUN,role=role,clockJoin=clock,originals=originals))
    a,b=frames
    lineage=dict(assetModelBakedInputProofVersion=1,runId=create.RUN,processId=42,domainId=create.DOMAIN,entityId=create.ID,
        creationRequestId='ios-'+uuid.uuid4().hex,originRequestId='ios-'+uuid.uuid4().hex,readerId=a['originals']['origin']['source']['history']['downloads'][0]['id'],
        nativeGeometryRequestId='ios-'+uuid.uuid4().hex,backendRequestId='assets-'+uuid.uuid4().hex,bakeRequestId='assets-'+uuid.uuid4().hex,
        path='/e2e-'+create.RUN+'/asset-stand.fbx',outputPath='/.baked/'+'f'*64+'/asset.fbx',sha256=body['sha256'],bytes=body['bytes'])
    return a,b,lineage


def reseal(frame):frame['clockJoin']['originalsSha256']=digest(frame['originals'])
