"""Fresh original Create source counterexamples; no device/product simulation claims."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
import base64
import struct
import zlib
import subprocess
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT/'tests/device'))
sys.path.insert(0,str(ROOT/'tests/device/adapters/android-phone'))
from overte_phone_create_source import PhoneCreateSource,command,validate
from adapters.normal_ui import NativeUIError
from overte_phone_create_fixture import documents,voxel_document
from self_tests.test_native_feature_observation import probe_source

RUN='b'*32
ID='12345678-1234-4234-8234-123456789abc'
DOMAIN='12345678-1234-4234-8234-000000000001'


def entity(kind='Model'):
    return dict(id=ID,name='e2e-'+RUN+'-'+('voxel' if kind=='PolyVox' else 'model'),type=kind,host='domain',parentId=None,
        position=[0.,1.,-2.],rotation=[0.,0.,0.,1.],dimensions=[1.,1.,1.],visible=True,locked=False,
        modelUrl='http://controlled.invalid/model.gltf' if kind=='Model' else '',textures='',
        voxel=dict(savedSha256=hashlib.sha256(b'actual-saved').hexdigest(),savedBytes=12,ready=True,volumeSize=[8,8,8]) if kind=='PolyVox' else None)


class Boundary:
    def __init__(self):
        self.value=None;self.sequence=0;self.clock=0.;self.epoch=20000;self.commands=[];self.fault=None
        self.rows=[];self.missing=[];self.permissions=[True,False,True]
        self.guard_ok=True;self.read_hook=None;self.send_hook=None
    def send(self,request):
        command(request);self.commands.append(deepcopy(request));self.sequence+=1
        self.value=dict(schemaVersion=1,requestId=request['commandId'],runId=request['runId'],instance='a'*32,
            sequence=self.sequence,processId=31,requestedEpochMs=self.epoch,capturedEpochMs=self.epoch,
            source=dict(phoneCreateObservationVersion=1,connected=True,domainId=DOMAIN,
                canRez=self.permissions[0],canRezTmp=self.permissions[1],canRezAvatarEntities=self.permissions[2],
                scan=dict(center=[0,0,0],radiusMeters=128,scannedEntities=len(self.rows),complete=True,
                    inventory=[dict(id=row['id'],type=row['type'],host=row['host'],nameSha256=hashlib.sha256(row['name'].encode()).hexdigest()) for row in self.rows]),
                entities=deepcopy(self.rows),absentIds=deepcopy(self.missing)))
        if self.fault:self.fault(self.value)
        if self.send_hook:self.send_hook()
    def read(self):
        if self.read_hook:self.read_hook()
        return json.dumps(self.value)
    def sleep(self,delay):self.clock+=delay
    def reader(self):
        return PhoneCreateSource(self.send,self.read,lambda:self.epoch,lambda:self.guard_ok,31,
                                 monotonic=lambda:self.clock,sleep=self.sleep)


class CreateSourceTests(unittest.TestCase):
    def test_inventory_and_permission_values_are_actual_not_requests(self):
        boundary=Boundary();boundary.rows=[entity()];boundary.permissions=[False,False,True]
        value=boundary.reader().read(RUN)
        self.assertFalse(value['source']['canRez']);self.assertFalse(value['source']['canRezTmp'])
        self.assertEqual('http://controlled.invalid/model.gltf',value['source']['entities'][0]['modelUrl'])
        self.assertEqual(set(boundary.commands[0]),{'schemaVersion','commandId','action','runId','trackedIds'})
    def test_saved_voxel_bytes_ready_and_volume_are_distinct_originals(self):
        boundary=Boundary();boundary.rows=[entity('PolyVox')]
        boundary.rows[0]['voxel']['ready']=False
        value=boundary.reader().read(RUN)
        self.assertFalse(value['source']['entities'][0]['voxel']['ready'])
        self.assertEqual(hashlib.sha256(b'actual-saved').hexdigest(),value['source']['entities'][0]['voxel']['savedSha256'])
    def test_direct_tracked_id_can_be_renamed_and_moved_without_becoming_absent(self):
        boundary=Boundary();row=entity();row.update(name='foreign-replacement',position=[900,1,-2]);boundary.rows=[row]
        self.assertEqual([row],boundary.reader().read(RUN,[ID])['source']['entities'])
    def test_absence_requires_explicit_direct_id_partition(self):
        boundary=Boundary()
        with self.assertRaises(NativeUIError):boundary.reader().read(RUN,[ID])
        boundary.missing=[ID]
        self.assertEqual([ID],boundary.reader().read(RUN,[ID])['source']['absentIds'])
    def test_discovered_name_does_not_authorize_unrelated_rows(self):
        boundary=Boundary();row=entity();row['name']='unrelated';boundary.rows=[row]
        with self.assertRaises(NativeUIError):boundary.reader().read(RUN)
    def test_missing_unavailable_and_partial_scan_never_prove_empty(self):
        for fault in (lambda v:v.pop('source'),lambda v:v['source']['scan'].update(complete=False),
                      lambda v:v['source']['scan'].update(scannedEntities=1025),lambda v:v['source'].update(entities=None)):
            with self.subTest(fault=fault):
                boundary=Boundary();boundary.fault=fault
                with self.assertRaises(NativeUIError):boundary.reader().read(RUN)
    def test_duplicate_present_absent_and_entity_ids_are_rejected(self):
        for rows,missing in (([entity(),entity()],[]),([entity()],[ID]),([],[ID,ID])):
            boundary=Boundary();boundary.rows=rows;boundary.missing=missing
            with self.assertRaises(NativeUIError):boundary.reader().read(RUN,[ID])
    def test_foreign_run_request_pid_instance_and_regressed_cursor_are_rejected(self):
        for field,value in (('runId','f'*32),('requestId','f'*32),('processId',32),('instance','f'*32),('sequence',1)):
            with self.subTest(field=field):
                boundary=Boundary();reader=boundary.reader();reader.read(RUN)
                boundary.fault=lambda v:v.update({field:value})
                with self.assertRaises(NativeUIError):reader.read(RUN)
    def test_source_version_and_false_numeric_types_reject(self):
        mutations=(lambda v:v['source'].update(phoneCreateObservationVersion=True),
                   lambda v:v['source'].update(canRez=1),lambda v:v['source']['scan'].update(radiusMeters=128.0),
                   lambda v:v.update(sequence=True),lambda v:v['source'].update(domainId=None))
        for mutate in mutations:
            boundary=Boundary();boundary.fault=mutate
            with self.assertRaises(NativeUIError):boundary.reader().read(RUN)
    def test_stale_future_and_rollback_original_epochs_are_rejected(self):
        for epoch in (18499,20251,19999):
            boundary=Boundary();boundary.fault=lambda v:v.update(capturedEpochMs=epoch,requestedEpochMs=min(epoch,20000))
            with self.assertRaises(NativeUIError):boundary.reader().read(RUN)
    def test_final_readback_io_time_counts_against_original_freshness(self):
        boundary=Boundary();boundary.read_hook=lambda:setattr(boundary,'epoch',22000)
        with self.assertRaises(NativeUIError):boundary.reader().read(RUN)
    def test_lost_candidate_guard_and_slow_delivery_remain_red(self):
        for fault in ('guard','slow'):
            boundary=Boundary()
            if fault=='guard':boundary.send_hook=lambda:setattr(boundary,'guard_ok',False)
            else:boundary.read_hook=lambda:setattr(boundary,'clock',5.)
            with self.assertRaises(NativeUIError):boundary.reader().read(RUN)
    def test_duplicate_json_keys_are_rejected(self):
        boundary=Boundary();reader=boundary.reader()
        reader.original=lambda:'{"requestId":"x","requestId":"y"}'
        with self.assertRaises(NativeUIError):reader.read(RUN)
    def test_commands_refuse_expectations_urls_mutations_and_unsorted_ids(self):
        base=dict(schemaVersion=1,commandId='a'*32,action='phone-create-observe',runId=RUN,trackedIds=[])
        for change in ({'expected':[]},{'url':'http://external.invalid/'},{'action':'phone-create-direct'},
                       {'trackedIds':[ID,ID]},{'trackedIds':[True]},{'runId':'0'*32}):
            with self.assertRaises(NativeUIError):command(base|change)
    def test_closed_inputs_use_actual_owned_fixture_and_the_normal_central_cube_format(self):
        url='http://controlled.invalid/feature-fixture/v1/runs/'+RUN+'/'
        originals=documents(RUN,'c'*32,url)
        self.assertEqual({'entity-import.json','voxel-import.json'},set(originals))
        model=json.loads(originals['entity-import.json'])
        self.assertEqual(3,model['DataVersion']);self.assertNotIn('textures',model['Entities'][0])
        self.assertEqual(url+'tickets/'+'c'*32+'/gltf-bundle/main.gltf',model['Entities'][0]['modelURL'])
        voxel=json.loads(originals['voxel-import.json'])['Entities'][0]
        self.assertEqual('e2e-'+RUN+'-voxel',voxel['name']);self.assertEqual(dict(x=8.,y=8.,z=8.),voxel['voxelVolumeSize'])
        raw=base64.b64decode(voxel['voxelData'],validate=True)
        x,y,z,length=struct.unpack('>HHHI',raw[:10]);self.assertEqual((8,8,8),(x,y,z));self.assertEqual(len(raw)-10,length)
        self.assertEqual(512,struct.unpack('>I',raw[10:14])[0]);data=zlib.decompress(raw[14:])
        self.assertEqual(64,data.count(255));self.assertEqual(448,data.count(0))
        for z in range(8):
            for y in range(8):
                for x in range(8):self.assertEqual(255 if all(2<=v<6 for v in (x,y,z)) else 0,data[z*64+y*8+x])

    def test_actual_probe_routes_new_original_reads_and_closed_widget_inputs(self):
        program=r'''const Uuid={generate:()=>"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"};
const objectKeysMatch=(v,k)=>JSON.stringify(Object.keys(v).sort())===JSON.stringify(k.sort());
let calls=[],files=[],next=0;
const Test={phoneCreateObservation:r=>{calls.push(r);return {requestId:r.commandId,source:{actual:true}};},
 phoneCreateUi:r=>{calls.push(r);return {commandId:r.commandId,performed:true};},saveObject:(v,n)=>files.push({v,n})};
SOURCE
let nonce=()=> (++next).toString(16).padStart(32,"0");
let read={schemaVersion:1,commandId:nonce(),action:"phone-create-observe",runId:"b".repeat(32),trackedIds:[]};
applyAndroidControlCommand(read);applyAndroidControlCommand(read);
if(calls.length!==1||files[0].n!=="phone-create-observation.json"||!files[0].v.source.actual)throw Error("read routing");
applyAndroidControlCommand({...read,commandId:nonce(),expected:[]});
if(calls.length!==1)throw Error("expected-state input accepted");
for (let [controlId,action,value] of [["create-file.name","replace","/private/feature-create-"+"b".repeat(32)+"/entity-import.json"],
 ["create-file.accept","activate",null],["create-file.cancel","activate",null],["create.voxel-shape","select-index",2],
 ["create.voxel-remove","activate",null],["create.voxel-diameter","replace","0.5"]]) {
 let commandId=nonce(),r={schemaVersion:1,commandId,action,controlId,instance:"c".repeat(32),generation:"d".repeat(32),
  controlToken:"e".repeat(32),sequence:1,observedElapsedMs:0};
 if(action==="replace")r.text=value;if(action==="select-index")r.index=value;
 let before=calls.length;applyAndroidControlCommand({schemaVersion:1,commandId,action:"phone-create-ui",request:r});
 if(calls.length!==before+1)throw Error("new control refused: "+controlId);
}
delete Test.phoneCreateObservation;applyAndroidControlCommand({...read,commandId:nonce()});
if(files.at(-1).v.available!==false)throw Error("missing native source green");
'''.replace('SOURCE',probe_source())
        result=subprocess.run(['node','-e',program],capture_output=True,text=True,timeout=5)
        self.assertEqual(0,result.returncode,result.stderr)

    def test_returned_original_is_not_the_readers_retained_reference(self):
        boundary=Boundary();reader=boundary.reader();value=reader.read(RUN)
        value['source']['canRez']=False
        self.assertTrue(reader.last['source']['canRez'])


if __name__=='__main__':unittest.main()
