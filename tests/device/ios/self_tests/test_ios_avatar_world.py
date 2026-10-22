"""Synthetic world/native/SDK reads plus actual closed JS/fixture transport."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import json
import subprocess
import hashlib
import uuid
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from fixture.serve import FixtureState
from ios.adapters import avatar_world as world,feature_observation
from ios.self_tests.test_ios_feature_observation import Native
RUN='c'*32
from self_tests.test_native_script_observation import Boundary as Scripts,effect_source,ENTITY
from self_tests.test_native_feature_observation import probe_source

NONCE='d'*32
URL='http://controlled.invalid/feature-fixture/v1/runs/'+RUN+'/tickets/'+'a'*32+'/graphics-marker.v1.html'


def packet(pid=31):
    scripts=Scripts();scripts.mutate=effect_source;scripts.send(dict(schemaVersion=1,commandId='ios-'+'f'*32,action='feature-script-observe'))
    script=scripts.sample;script['processId']=pid;effect=script['source']['effects']['entities'][0]
    effect.update(name='e2e-'+RUN+'-script',type='Web',userData=json.dumps(dict(kind='avatar-marker-v1',runId=RUN,nonce=NONCE)))
    tree=dict(entityInventoryVersion=1,profile='native-entity-edit-wire-v1',treeInstance='b'*32,revisionBefore=1,
        revisionAfter=1,totalEntities=1,complete=True,entities=[dict(id=ENTITY,hostType='local',ready=True,
            createdEpochUs='19000000',lastEditedEpochUs='19000000',lastEditedAfterEpochUs='19000000',semanticBytes=100,semanticSha256='c'*64)])
    marker={k:effect[k] for k in ('id','name','type','hostType','userData')}
    marker.update(sourceUrl=URL,position=[0,1.6,1],rotation=[0,0,0,1],dimensions=[1.6,.4,.01],visible=True,collisionless=True,lastEditedEpochUs='19000000')
    source=dict(complete=True,tree=tree,scriptOriginal=script,markers=[marker],sceneUrl='overte://controlled.test/domain',
        domain=dict(connected=True,serverless=False,domainId='11111111-1111-4111-8111-111111111111',selfSha256='e'*64,avatarMixerSha256='f'*64),
        avatar=dict(feetPosition=[0,0,4],orientation=[0,0,0,1],velocity=[0,0,0],inAir=False,flying=False,modelScale=1,
            boundsReady=True,bounds=dict(corner=[-.3,0,3.7],dimensions=[.6,1.8,.6])),
        view=dict(position=[0,1.6,7],rotation=[0,0,0,1],mode='look at',fieldOfViewDegrees=60,aspectRatio=1.5,perspective=True),
        cameraOrbit=dict(lookAtRotation=[0,0,0,1],boomLength=3,minimumBoomLength=.6,defaultBoomLength=3))
    return dict(iosAvatarWorldVersion=1,requestId='ios-'+'a'*32,runId=RUN,instance='e'*32,sequence=1,processId=pid,
        clockDomain='native-main-avatar-world',clockBefore=dict(epochMs=20000,monotonicMs=1000),
        clockAfter=dict(epochMs=20000,monotonicMs=1000),source=source)


class AvatarWorldTests(unittest.TestCase):
    def physical(self):
        value=packet();identity='00000000-0000-4000-8000-000000000001'
        value['source']['domain']['selfSha256']=hashlib.sha256(uuid.UUID(identity).bytes).hexdigest()
        value['source']['bodies']=dict(avatarBodyCollectionVersion=1,instance='e'*32,sequence=1,capturedEpochMs=20000,
            complete=True,avatars=[dict(sessionId=identity,self=True,replicated=False,position=[1,2,3],orientation=[0,0,0,1],velocity=[0,0,0])])
        return value,identity
    def test_optional_actual_body_collection_preserves_legacy_v1_without_inventing_geometry(self):
        legacy=packet();world.original(legacy);self.assertNotIn('bodies',legacy['source'])
        with self.assertRaises(NativeUIError):world.body(legacy,'00000000-0000-4000-8000-000000000001')
        value,identity=self.physical();value['source']['avatar'].update(boundsReady=False,bounds=None)
        self.assertEqual([1,2,3],world.body(value,identity)['position']);self.assertIsNone(value['source']['avatar']['bounds'])
        self.assertEqual(1,value['iosAvatarWorldVersion'])
    def test_actual_body_collection_cannot_substitute_other_self_or_replicated_or_unknown_rows(self):
        for fault in ('identity','replicated','duplicate','epoch','version','quaternion'):
            value,identity=self.physical();body=value['source']['bodies'];row=body['avatars'][0]
            if fault=='identity':row['sessionId']='00000000-0000-4000-8000-000000000002'
            elif fault=='replicated':row['replicated']=True
            elif fault=='duplicate':body['avatars'].append(deepcopy(row))
            elif fault=='epoch':body['capturedEpochMs']=19999
            elif fault=='version':body['avatarBodyCollectionVersion']=True
            else:row['orientation']=[0,0,0,0]
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):world.body(value,identity)
    def test_once_returned_actual_body_birth_and_sequence_cannot_disappear_or_reset(self):
        before,identity=self.physical();after=deepcopy(before)
        after.update(requestId='ios-'+'b'*32,sequence=2)
        after['source']['bodies']['sequence']=2
        query=dict(schemaVersion=1,commandId=after['requestId'],action=world.ACTION,runId=RUN)
        world.validate(after,query,31,previous=before)
        for fault in ('missing','birth','sequence'):
            value=deepcopy(after)
            if fault=='missing':del value['source']['bodies']
            elif fault=='birth':value['source']['bodies']['instance']='0'*32
            else:value['source']['bodies']['sequence']=1
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):world.validate(value,query,31,previous=before)
    def test_avatar_original_marker_profile_and_source_type_cannot_adopt_emote_facts(self):
        from ios.adapters import emote_world
        value=packet()
        with self.assertRaises(NativeUIError):emote_world.original(value)
        for row in (value['source']['markers'][0],value['source']['scriptOriginal']['source']['effects']['entities'][0]):
            data=json.loads(row['userData']);data['kind']='emote-marker-v1';row['userData']=json.dumps(data)
        with self.assertRaises(NativeUIError):world.original(value)
    def test_actual_owned_marker_joins_original_script_effect_UUID_and_whole_map(self):
        value=packet();original=deepcopy(value)
        self.assertEqual(ENTITY,world.owned_marker(value,NONCE,URL)['id'])
        self.assertEqual(value,original);self.assertTrue(world.actual_domain(value)['connected'])
        for mutate in (lambda v:v['source']['markers'][0].update(sourceUrl=URL+'?requested=1'),
                       lambda v:v['source']['markers'][0].update(id='22222222-2222-4222-8222-222222222222'),
                       lambda v:v['source']['markers'][0].update(lastEditedEpochUs='19000001'),
                       lambda v:v['source']['markers'][0].update(visible=False)):
            current=deepcopy(value);mutate(current)
            with self.assertRaises(NativeUIError):world.owned_marker(current,NONCE,URL)
    def test_serverless_or_mixerless_scene_cannot_replace_real_domain_peer(self):
        for edit in (dict(connected=False),dict(serverless=True),dict(avatarMixerSha256=None)):
            value=packet();value['source']['domain'].update(edit)
            with self.assertRaises(NativeUIError):world.actual_domain(value)
    def test_unchanged_native_tree_cannot_hide_a_changed_or_missing_unowned_entity(self):
        before=packet();self.assertEqual({},world.preserve_unowned(before,deepcopy(before),{ENTITY}))
        after=packet();after['source']['tree']['entities'][0]['semanticSha256']='d'*64
        with self.assertRaises(NativeUIError):world.preserve_unowned(before,after,set())
    def test_stale_nested_script_cannot_be_retimed_in_current_world_envelope(self):
        value=packet();value['clockBefore']['epochMs']=20100;value['clockAfter']['epochMs']=20100
        with self.assertRaises(NativeUIError):world.original(value)
    def test_bounds_unavailable_remains_explicit_unknown_and_is_not_expected_avatar_geometry(self):
        value=packet();value['source']['avatar'].update(boundsReady=False,bounds=None);world.original(value)
        self.assertIsNone(value['source']['avatar']['bounds'])
        value['source']['avatar']['bounds']=dict(corner=[0,0,0],dimensions=[1,2,1])
        with self.assertRaises(NativeUIError):world.original(value)
    def test_actual_fixture_and_probe_keep_closed_original_read_without_resend(self):
        fixture=FixtureState();query=dict(schemaVersion=1,commandId='ios-'+'a'*32,action=world.ACTION,runId=RUN)
        self.assertEqual(query,fixture.set_client_command(query))
        for edit in (dict(expected='Waving'),dict(position=[0,0,4]),dict(schemaVersion=True)):
            with self.assertRaises(ValueError):fixture.set_client_command(query|edit)
        script='''
const Uuid={generate:()=>"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"};
const objectKeysMatch=(v,keys)=>JSON.stringify(Object.keys(v).sort())===JSON.stringify(keys.sort());
let calls=0,files=[];const original=PACKET;
const Test={featureIOSAvatarWorld:q=>{calls++;return {...original,requestId:q.commandId};},saveObject:(v,name)=>files.push({v,name})};
SOURCE
const q=QUERY;applyClientCommand(q);applyClientCommand(q);
if(calls!==1||files.length!==1||files[0].name!=="feature-ios-avatar-world.json")throw Error("read replay/source");
if(JSON.stringify(files[0].v.source)!==JSON.stringify(original.source))throw Error("retimed source");
applyClientCommand({...q,commandId:"ios-"+"b".repeat(32),expected:"Waving"});if(calls!==1)throw Error("desired state accepted");
delete Test.featureIOSAvatarWorld;applyClientCommand({...q,commandId:"ios-"+"c".repeat(32)});
if(files.at(-1).v.status!=="unavailable")throw Error("missing source green");
const count=files.length;applyClientCommand({...q,commandId:"ios-"+"c".repeat(32)});
if(files.length!==count)throw Error("unavailable nonce replayed");
'''.replace('PACKET',json.dumps(packet())).replace('QUERY',json.dumps(query)).replace('SOURCE',probe_source())
        run=subprocess.run(['node','-e',script],capture_output=True,text=True,timeout=5);self.assertEqual(0,run.returncode,run.stderr)
    def test_existing_FeatureObservation_factory_uses_actual_bound_AFC_path_and_native_clock(self):
        native=Native();observer=native.observer();native.value=None
        def post(request,timeout):
            query=native.fixture.set_client_command(json.loads(request.data));native.echo=json.dumps(query).encode()
            native.value=packet(native.pid);native.value.update(requestId=query['commandId']);return native
        def execute(session,operation,arguments):
            self.assertEqual('native-session',session);self.assertEqual('mobile: pullFile',operation)
            self.assertEqual({'remotePath':'@org.example.client:documents/owned-results/'+world.FILE},arguments)
            return base64.b64encode(json.dumps(native.value).encode()).decode()
        native.execute=execute;clock=SimpleNamespace(sequence=0,read=lambda _:dict(capturedEpochMs=20000))
        with patch.object(feature_observation,'post_request',side_effect=post):
            value=observer.avatar_world(clock).read(RUN)
        self.assertEqual(native.pid,value['processId']);self.assertEqual(20000,value['source']['scriptOriginal']['capturedEpochMs'])

if __name__=='__main__':unittest.main()
