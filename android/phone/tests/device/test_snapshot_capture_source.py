"""Fresh original capture-file envelopes; no ACK/old identity adoption."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
import subprocess
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT/'tests/device'),str(ROOT/'tests/device/adapters/android-phone')]
from adapters.normal_ui import NativeUIError
from overte_phone_snapshot_capture_source import PhoneSnapshotCaptureFileSource,command,source
RUN='a'*32;PLAN='b'*32;FILE='c'*32;CAPTURE='actual_native_capture_1';PREFIX='e2e-'+RUN
PATH='/data/user/0/io.github.noah_be.overte.phone/files/Snapshots/'+PREFIX+'-'+CAPTURE+'.png'

class Boundary:
    def __init__(self):
        self.epoch=100000;self.time=0;self.sent=[];self.last=None;self.sequence=0
        plan=dict(id=PLAN,runId=RUN,prefix=PREFIX,event=1,checkedEpochMs=self.epoch-20,rootPresent=True,rootDevice=7,rootInode=9,sealed=False,sealId='',sealedEpochMs=0)
        capture=dict(captureId=CAPTURE,event=2,beganEpochMs=self.epoch-10,terminal='complete',terminalPath=PATH,terminalEpochMs=self.epoch-1)
        row=dict(id=FILE,captureId=CAPTURE,path=PATH,planId=PLAN,runId=RUN,sha256=hashlib.sha256(b'original').hexdigest(),retireId='',deleteIssued=False,deleteResult=-2,absent=False,checkedEpochMs=0,phase='closed',preexisting=False,rootDevice=7,rootInode=9,device=7,inode=10,uid=10001,links=1,opened=True,closed=True,bytes=8,createdEpochMs=self.epoch-9,closedEpochMs=self.epoch-2,removeAttempted=False,removeAttempts=0,nativeRemoved=False)
        self.source=dict(phoneSnapshotCaptureFilesVersion=1,instance='d'*32,complete=True,sequence=0,capturedEpochMs=self.epoch,rows=[row],captures=[capture],plans=[plan])
    def send(self,request):self.sent.append(deepcopy(request));self.last=deepcopy(request)
    def read(self):
        self.sequence+=1;self.source.update(sequence=self.sequence,capturedEpochMs=self.epoch)
        return json.dumps(dict(schemaVersion=1,requestId=self.last['commandId'],runId=self.last['runId'],instance='e'*32,sequence=self.sequence,processId=77,requestedEpochMs=self.epoch,capturedEpochMs=self.epoch,accepted=True,source=self.source))
    def sleep(self,seconds):self.time+=seconds
    def reader(self,read_only=True):
        return PhoneSnapshotCaptureFileSource(self.send,self.read,lambda:self.epoch,lambda:True,77,read_only=read_only,monotonic=lambda:self.time,sleep=self.sleep)

class SnapshotCaptureSourceTests(unittest.TestCase):
    def test_probe_forwards_original_packets_once_and_missing_source_remains_unavailable(self):
        raw=(ROOT/'tests/device/probe/overte_e2e_probe.js').read_text()
        start=raw.index('        if (command && command.schemaVersion === 1 && command.action === "phone-snapshot-files-control"')
        block=raw[start:raw.index('        if (command && command.schemaVersion === 1 && command.action === "phone-snapshot-upload-observe"',start)]
        script='''const assert=require('node:assert/strict');
function objectKeysMatch(v,k){return v&&JSON.stringify(Object.keys(v).sort())===JSON.stringify(k.slice().sort());}
let lastPhoneSnapshotCaptureFilesRequest='',calls=[],saved=[];
let original={requestId:'1'.repeat(32),accepted:false,source:{originalNativeOnly:true}};
const Test={phoneSnapshotCaptureFiles(c){calls.push(c);return original;},saveObject(v,f){saved.push([v,f]);}};
function applyClientCommand(command){'''+block+'''}
const observe={schemaVersion:1,action:'phone-snapshot-files-observe',commandId:'1'.repeat(32),runId:'2'.repeat(32)};
applyClientCommand(observe);applyClientCommand(observe);assert.equal(calls.length,1);assert.equal(saved[0][0],original);
for(const change of [{path:'foreign'},{expected:'green'},{bytes:42}])applyClientCommand({...observe,commandId:'3'.repeat(32),...change});
assert.equal(calls.length,1);assert.equal(saved[0][1],'phone-snapshot-files-observation.json');
delete Test.phoneSnapshotCaptureFiles;applyClientCommand({...observe,commandId:'4'.repeat(32)});
assert.deepEqual(saved[1][0],{schemaVersion:1,requestId:'4'.repeat(32),available:false});
Test.phoneSnapshotCaptureFiles=c=>{calls.push(c);return {requestId:c.commandId,accepted:true};};
applyClientCommand({...observe,action:'phone-snapshot-files-control',commandId:'5'.repeat(32),operation:'retire',prefix:'',fileId:'6'.repeat(32),operationId:'7'.repeat(32)});
assert.equal(calls.length,2);assert.deepEqual(saved[2][0],{requestId:'5'.repeat(32),accepted:true});
'''
        subprocess.run(['node','-e',script],check=True,timeout=10)
    def test_original_closed_fd_native_scope_and_current_sampling_are_distinct(self):
        value=Boundary();reader=value.reader();first=reader.request(RUN);second=reader.request(RUN)
        self.assertEqual(10,first['source']['rows'][0]['inode']);self.assertNotEqual(first['requestId'],second['requestId']);self.assertLess(first['sequence'],second['sequence'])
    def test_foreign_scope_prior_capture_missing_fd_and_unclosed_stream_are_rejected(self):
        for fault in ('scope','capture-event','inode','closed','hash','root','unknown-field'):
            value=Boundary();row=value.source['rows'][0]
            if fault=='scope':row['runId']='f'*32
            elif fault=='capture-event':value.source['captures'][0]['event']=1
            elif fault=='inode':row['inode']=0
            elif fault=='closed':row['closed']=False
            elif fault=='hash':row['sha256']=''
            elif fault=='root':row['rootInode']=12
            else:row['expected']='green'
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):value.reader().request(RUN)
    def test_native_original_identity_and_closed_bytes_cannot_be_replaced_between_reads(self):
        for key,item in (('inode',11),('bytes',9),('sha256','1'*64),('captureId','different_capture')):
            value=Boundary();reader=value.reader();reader.request(RUN);value.source['rows'][0][key]=item
            with self.subTest(key=key),self.assertRaises(NativeUIError):reader.request(RUN)
    def test_retirement_requires_original_owned_intent_and_fresh_absence_not_empty_files(self):
        value=Boundary();row=value.source['rows'][0];row.update(retireId='f'*32,deleteIssued=True,deleteResult=0,absent=True,checkedEpochMs=value.epoch)
        value.reader().request(RUN)
        for key,item in (('absent',False),('deleteIssued',False),('preexisting',True),('retireId',''),('checkedEpochMs',0)):
            changed=deepcopy(value.source);changed['rows'][0][key]=item
            with self.subTest(key=key),self.assertRaises(NativeUIError):source(changed,value.epoch)
    def test_sealed_namespace_keeps_all_native_histories_and_cannot_hide_old_owned_rows(self):
        value=Boundary();row=value.source['rows'][0];row.update(retireId='f'*32,deleteIssued=True,deleteResult=0,absent=True,checkedEpochMs=value.epoch)
        value.source['plans'][0].update(sealed=True,sealId='1'*32,sealedEpochMs=value.epoch)
        reader=value.reader();reader.request(RUN);value.source['rows']=[]
        with self.assertRaises(NativeUIError):reader.request(RUN)
    def test_readonly_actor_observes_but_cannot_plan_retire_or_seal(self):
        from appium_adapter import readonly_feature_command
        value=Boundary();reader=value.reader();reader.request(RUN);readonly_feature_command(value.sent[0])
        for operation in ('plan','retire','seal'):
            with self.subTest(operation=operation),self.assertRaises(NativeUIError):reader.request(RUN,operation,prefix=PREFIX if operation=='plan' else '',file_id='' if operation=='plan' else FILE,operation_id='1'*32)
            request=dict(schemaVersion=1,commandId='1'*32,runId=RUN,action='phone-snapshot-files-control',operation=operation,prefix=PREFIX if operation=='plan' else '',fileId='' if operation=='plan' else FILE,operationId='2'*32)
            command(request)
            with self.assertRaises((RuntimeError,ValueError)):readonly_feature_command(request)
        self.assertEqual(1,len(value.sent))
    def test_closed_command_rejects_caller_path_digest_unknown_scope_and_bad_nonce(self):
        request=dict(schemaVersion=1,commandId='1'*32,runId=RUN,action='phone-snapshot-files-control',operation='plan',prefix=PREFIX,fileId='',operationId='2'*32)
        command(request)
        for field in ('path','sha256','bytes','expected'):
            with self.subTest(field=field),self.assertRaises(NativeUIError):command(dict(request,**{field:'foreign'}))
        for changed in (dict(request,prefix='user-photos'),dict(request,operation='set-result'),dict(request,fileId=FILE),dict(request,operationId='old')):
            with self.assertRaises(NativeUIError):command(changed)
    def test_stale_request_and_ack_without_original_source_never_pass(self):
        value=Boundary();value.read=lambda:json.dumps(dict(schemaVersion=1,requestId='f'*32,available=False))
        with self.assertRaises(NativeUIError):value.reader().request(RUN)
        self.assertLessEqual(value.time,5.1)
        value=Boundary();value.read=lambda:json.dumps(dict(schemaVersion=1,requestId=value.last['commandId'],accepted=True))
        with self.assertRaises(NativeUIError):value.reader().request(RUN)

if __name__=='__main__':unittest.main()
