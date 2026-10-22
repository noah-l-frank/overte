"""Owned marker input bytes, actual execution identity and terminal counterexamples."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.adapters import create_marker_measurements as marker
from ios.adapters.create_marker_files import originals,OwnedCreateMarkerFiles
from ios.adapters.create_marker_identity import PreparedCreateMarker
from ios.self_tests.test_ios_create_state import packet,version2,add_model,RUN,EPOCH,ID
from ios.self_tests.test_ios_create_files import URL,BINDING
from ios.self_tests.test_ios_create_peer import domain_pair
from ios.self_tests.test_ios_emote_world import packet as domain_packet
from self_tests.test_native_script_files import Boundary as FilesBoundary
from self_tests.test_native_script_terminal import packet as terminal_packet

DIRECTORY='file:///actual/feature-script-'+RUN
FILES=dict(runId=RUN,fixtureUrl=URL,ticket='a'*32,nonce='d'*32)


def frames():
    before=version2(packet());before['iosCreateStateVersion']=3;after=deepcopy(before)
    after.update(sequence=2,requestId='ios-'+'2'*32);after['clockBefore'].update(epochMs=EPOCH+10,monotonicMs=10);after['clockAfter'].update(epochMs=EPOCH+11,monotonicMs=11)
    entity=add_model(after);version2(after);after['iosCreateStateVersion']=3
    entity.update(type='Web',model={},hostType='local',collisionless=True,sourceUrl=URL+'tickets/'+FILES['ticket']+'/graphics-marker.v1.html',
                  userData=json.dumps(dict(kind='create-marker-v1',runId=RUN,nonce=FILES['nonce'])),name='e2e-'+RUN+'-script')
    after['source']['tree']['entities'][0]['hostType']='local'
    scripts=domain_packet(42)['source']['scriptOriginal'];scripts.update(requestedEpochMs=EPOCH+10,capturedEpochMs=EPOCH+10)
    source=scripts['source'];source['sourceIdentityVersion']=1;engine=source['engines'][0]
    engine['url']=DIRECTORY+'/script-bundle/main.js';engine['required']['modules'][0]['url']=DIRECTORY+'/script-bundle/companion.js'
    raw=originals(RUN,URL,FILES['ticket'],FILES['nonce'])['script-bundle/main.js'].decode().encode('utf-16le')
    engine['code']=dict(submitted=True,encoding='utf-16le-code-units',codeUnits=len(raw)//2,sha256=hashlib.sha256(raw).hexdigest(),submittedEpochMs=EPOCH-10)
    assigned=dict(instance=engine['required']['instance'],assigned=True,url=engine['url'],loadGeneration=1,assignedEpochMs=EPOCH-20)
    source.update(membershipSourceVersion=1,membership=dict(complete=True,revision=1,managers=[assigned]))
    return before,after,scripts


class CreateMarkerTests(unittest.TestCase):
    def test_prepared_lease_requires_candidate_owned_source_admission_and_returns_independent_copies(self):
        before,after,scripts=frames();domain_before,domain_after=domain_pair(before,after)
        raw=originals(RUN,URL,FILES['ticket'],FILES['nonce'])
        files=dict(contractVersion=1,markerFilesVersion=1,binding=deepcopy(BINDING),ownerToken='f'*64,
            **FILES,hashes={name:hashlib.sha256(data).hexdigest() for name,data in raw.items()})
        def lease(**changes):
            values=dict(before=before,after=after,scripts=scripts,files=files,directory=DIRECTORY,after_epoch=EPOCH-30,
                domain_before=domain_before,domain_after=domain_after);values.update(changes)
            return PreparedCreateMarker(BINDING,RUN,URL,**values)
        value=lease();self.assertEqual(ID,value.state['admission']['marker']['id'])
        modified=value.state;modified['admission']['marker']['name']='foreign';self.assertEqual('e2e-'+RUN+'-script',value.state['admission']['marker']['name'])
        for fault in ('candidate','hash','version','source','domain'):
            current=deepcopy(files);script=deepcopy(scripts);domain=deepcopy(domain_after)
            if fault=='candidate':current['binding']['artifactSha256']='0'*64
            elif fault=='hash':current['hashes']['script-bundle/main.js']='0'*64
            elif fault=='version':current['markerFilesVersion']=True
            elif fault=='source':script['source']['engines'][0]['url']='file:///foreign.js'
            else:domain['source']['avatar']['modelScale']=2
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):lease(files=current,scripts=script,domain_after=domain)
    def test_actual_assigned_source_exact_submitted_utf16_and_unique_new_native_uuid_join(self):
        before,after,scripts=frames();owned=marker.admitted(before,after,scripts,FILES,DIRECTORY,after_epoch=EPOCH-30)
        self.assertEqual(ID,owned['marker']['id']);self.assertEqual(DIRECTORY+'/script-bundle/main.js',owned['sourceUrl'])
    def test_old_script_wrong_bytes_missing_companion_or_requested_marker_cannot_authorize(self):
        for fault in ('old','code','companion','assigned','preexisting','nonce','view'):
            before,after,scripts=frames()
            if fault=='old':scripts.update(requestedEpochMs=EPOCH-2000,capturedEpochMs=EPOCH-2000)
            elif fault=='code':scripts['source']['engines'][0]['code']['sha256']='f'*64
            elif fault=='companion':scripts['source']['engines'][0]['required']['modules'][0]['loaded']=False
            elif fault=='assigned':scripts['source']['membership']['managers'][0]['assignedEpochMs']=EPOCH-40
            elif fault=='preexisting':before=deepcopy(after)
            elif fault=='nonce':after['source']['entities'][0]['userData']=after['source']['entities'][0]['userData'].replace(FILES['nonce'],'0'*32)
            else:after['source']['view']['position'][0]=1
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):marker.admitted(before,after,scripts,FILES,DIRECTORY,after_epoch=EPOCH-30)
    def test_marker_bytes_execute_one_local_web_and_delete_only_actual_returned_uuid_without_pose_writes(self):
        source=originals(RUN,URL,FILES['ticket'],FILES['nonce'])['script-bundle/main.js'].decode()
        program=r'''
const vm=require('node:vm'),assert=require('node:assert/strict');
const source=JSON.parse(require('node:fs').readFileSync(0,'utf8'));
let added=[],deleted=[],ending;
const context={Script:{require:path=>{assert.equal(path,'./companion.js');return{};},scriptEnding:{connect:fn=>ending=fn}},
Camera:Object.freeze({position:Object.freeze({x:0,y:1.6,z:0}),orientation:Object.freeze({x:0,y:0,z:0,w:1})}),
Vec3:{sum:(a,b)=>({x:a.x+b.x,y:a.y+b.y,z:a.z+b.z}),multiplyQbyV:(_,b)=>b},
Entities:{addEntity:(properties,host)=>{added.push({properties,host});return 'actual-returned-uuid';},deleteEntity:id=>deleted.push(id)}};
vm.runInNewContext(source,context);assert.equal(added.length,1);assert.equal(added[0].host,'local');
assert.equal(added[0].properties.type,'Web');assert.equal(added[0].properties.position.x,-1.25);
assert.equal(JSON.parse(added[0].properties.userData).kind,'create-marker-v1');
ending();assert.deepEqual(deleted,['actual-returned-uuid']);assert.equal(context.MyAvatar,undefined);
'''
        result=subprocess.run(['node','-e',program],input=json.dumps(source),capture_output=True,text=True,timeout=5)
        self.assertEqual(0,result.returncode,result.stderr)
    def test_actual_private_marker_bundle_transport_and_modified_bytes_refuse_retirement(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);root.chmod(0o700);seam=FilesBoundary(root)
            # The native SDK seam owns another actual PID; the candidate binds
            # that PID explicitly rather than rewriting native packets.
            owner=OwnedCreateMarkerFiles(seam.native(),PrivateFeatureState(root/'marker-files.json'),BINDING|dict(processIdentity='31'))
            metadata=owner.reserve_marker(RUN,URL,FILES['ticket']);location=owner.stage_reserved()
            self.assertEqual(seam.root.as_uri(),location);self.assertEqual(4,len(list(seam.root.rglob('*.js'))))
            (seam.root/'companion.js').write_bytes(b'foreign')
            with self.assertRaises(NativeUIError):owner.verify()
            self.assertEqual(metadata,owner.owned());self.assertTrue(seam.root.exists())
    def test_original_body_camera_and_actual_domain_are_preserved(self):
        before=domain_packet();self.assertTrue(marker.body_preserved(before,deepcopy(before)))
        for field,updates in (('domain',dict(serverless=True)),('avatar',dict(feetPosition=[1,0,4])),('avatar',dict(inAir=True)),
                              ('avatar',dict(flying=True)),('avatar',dict(modelScale=2)),('cameraOrbit',dict(boomLength=4))):
            after=deepcopy(before);after['source'][field].update(updates)
            with self.subTest(field=field,updates=updates),self.assertRaises(NativeUIError):marker.body_preserved(before,after)
    def test_empty_map_needs_real_shutdown_drained_and_actual_thread_exit_not_stop_ack(self):
        before,after,scripts=frames();owned=marker.admitted(before,after,scripts,FILES,DIRECTORY,after_epoch=EPOCH-30)
        empty=deepcopy(scripts);empty['source']['engines']=[];empty['source']['membership'].update(revision=2,managers=[])
        clean=deepcopy(before);proof=terminal_packet();proof.update(processId=42,requestedEpochMs=EPOCH+20,capturedEpochMs=EPOCH+20);proof['source']['processId']=42
        for index,event in enumerate(proof['source']['events']):
            event['manager']=deepcopy(owned['manager']);event['capturedEpochMs']=(EPOCH-15 if index==0 else EPOCH+index)
            if event['code'] is not None:event['code']=deepcopy(owned['code'])
        self.assertEqual(3,len(marker.restored(before,clean,empty,owned,proof,after_sequence=1,after_epoch=EPOCH)))
        for fault in ('thread','callback','manager','view'):
            current=deepcopy(clean);terminal=deepcopy(proof);observed=deepcopy(empty)
            if fault=='thread':terminal['source']['events'].pop();terminal['source']['eventSequence']-=1
            elif fault=='callback':terminal['source']['events'][1]['work']['timerCallbacks']=1
            elif fault=='manager':observed=deepcopy(scripts)
            else:current['source']['view']['position'][0]+=1
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):marker.restored(before,current,observed,owned,terminal,after_sequence=1,after_epoch=EPOCH)


if __name__=='__main__':unittest.main()
