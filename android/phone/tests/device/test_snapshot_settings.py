"""Explicit transport/typed-serialization seams; actual Qt semantics tested separately."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
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
from appium_adapter import readonly_feature_command
from overte_phone_snapshot_settings import PhoneSnapshotSettings,KEYS,command,validate

RUN='a'*32


class Boundary:
    def __init__(self):
        self.clock=0.;self.epoch=20000;self.calls=[];self.sequence=0;self.raw='';self.fault=None
        self.original=dict(entries={k:dict(present=False,value=None) for k in KEYS},format=dict(set=False,value=''))
        self.current=deepcopy(self.original);self.opened=0;self.handback=0;self.retired=False;self.restoring=False;self.restore_id='';self.expected=''
    @staticmethod
    def serialized(value):return json.dumps(value,sort_keys=True,separators=(',',':')).encode() # Explicit Qt serialization seam.
    def digest(self,value):return hashlib.sha256(self.serialized(value)).hexdigest()
    def sleep(self,seconds):self.clock+=seconds;self.epoch+=round(seconds*1000)
    def send(self,request):
        self.calls.append(deepcopy(request));self.sequence+=1
        if self.fault=='ignored':return
        op=request['operation']
        if op=='capture':self.opened=self.epoch
        if op=='restore':
            self.restoring=True;self.restore_id=request['restoreId'];self.expected=request['expectedSha256']
            if self.fault!='unrestored':self.current=deepcopy(self.original);self.handback=self.handback or self.epoch
        if op=='retire':self.retired=True
        source=dict(scopePresent=not self.retired,closed=True,restoring=self.restoring,restored=bool(self.handback),retired=self.retired,
            openedEpochMs=self.opened,handbackEpochMs=self.handback,originalSha256=self.digest(self.original),currentSha256=self.digest(self.current),
            restoreId=self.restore_id,expectedSha256=self.expected,current=deepcopy(self.current),
            currentSerializedBase64=base64.b64encode(self.serialized(self.current)).decode())
        value=dict(snapshotSettingsLeaseVersion=1,instance='b'*32,runId=request['runId'],commandId=request['commandId'],sequence=self.sequence,
            processId=123,capturedEpochMs=self.epoch,operation=op,source=source)
        if self.fault=='stale':value['capturedEpochMs']-=2000
        if self.fault=='foreign-pid':value['processId']=124
        if self.fault=='foreign-run':value['runId']='c'*32
        if self.fault=='same-sequence':value['sequence']=1
        if self.fault=='changed-original':source['originalSha256']='0'*64
        if self.fault=='corrupt-bytes':source['currentSerializedBase64']=base64.b64encode(b'foreign').decode()
        if self.fault=='unclosed':source['closed']=False
        if self.fault=='unretired':source.update(retired=False,scopePresent=True)
        if self.fault=='slow':self.clock+=5.01
        if self.fault=='rewound':self.clock-=1
        self.raw=json.dumps(value)
    def reader(self,readonly=False):
        return PhoneSnapshotSettings(self.send,lambda:self.raw,lambda:self.epoch,lambda:self.fault!='guard',123,
            monotonic=lambda:self.clock,sleep=self.sleep,read_only=readonly)


class SnapshotSettingsTests(unittest.TestCase):
    def test_real_lifecycle_preserves_original_typed_digest_and_handback(self):
        boundary=Boundary();reader=boundary.reader();first=reader.request(RUN,'capture')
        boundary.current['format'].update(set=True,value='png')
        boundary.current['entries']['snapshotFormat'].update(present=True,value='png')
        changed=reader.request(RUN,'observe');self.assertNotEqual(first['source']['currentSha256'],changed['source']['currentSha256'])
        restored=reader.request(RUN,'restore',restore_id='d'*32,expected_sha256=changed['source']['currentSha256'])
        self.assertEqual(first['source']['currentSha256'],restored['source']['currentSha256'])
        last=reader.request(RUN,'retire');self.assertTrue(last['source']['retired'])
        self.assertEqual(restored['source']['handbackEpochMs'],last['source']['handbackEpochMs'])
        last['source']['originalSha256']='f'*64;self.assertNotEqual(last,reader.last)

    def test_ignored_stale_foreign_missing_and_slow_source_cannot_pass(self):
        for fault in ('ignored','stale','foreign-pid','foreign-run','corrupt-bytes','unclosed','slow','rewound','guard'):
            boundary=Boundary();boundary.fault=fault
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):boundary.reader().request(RUN,'capture')
            self.assertEqual(0 if fault=='guard' else 1,len(boundary.calls))

    def test_same_sequence_changed_original_and_ignored_restore_are_red(self):
        for fault in ('same-sequence','changed-original','unrestored','corrupt-bytes','unclosed'):
            boundary=Boundary();reader=boundary.reader();reader.request(RUN,'capture')
            boundary.current['format'].update(set=True,value='png');boundary.fault=fault
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):
                reader.request(RUN,'restore',restore_id='d'*32,expected_sha256=boundary.digest(boundary.current))

    def test_incomplete_retirement_is_red(self):
        boundary=Boundary();reader=boundary.reader();reader.request(RUN,'capture')
        reader.request(RUN,'restore',restore_id='d'*32,expected_sha256=boundary.digest(boundary.current))
        boundary.fault='unretired'
        with self.assertRaises(NativeUIError):reader.request(RUN,'retire')

    def test_readonly_source_cannot_capture_restore_or_retire(self):
        for op in ('capture','restore','retire'):
            boundary=Boundary();reader=boundary.reader(readonly=True)
            with self.subTest(operation=op),self.assertRaises(NativeUIError):reader.request(RUN,op)
            self.assertEqual([],boundary.calls)

    def test_readonly_command_whitelist_admits_only_fixed_original_observe(self):
        request=dict(schemaVersion=1,commandId='e'*32,runId=RUN,action='phone-snapshot-settings',operation='observe')
        readonly_feature_command(request)
        for op in ('capture','retire','restore'):
            with self.subTest(operation=op),self.assertRaises(Exception):readonly_feature_command(dict(request,operation=op))

    def test_desired_values_unknown_keys_and_unversioned_commands_refused(self):
        request=dict(schemaVersion=1,commandId='e'*32,runId=RUN,action='phone-snapshot-settings',operation='capture')
        for value in (dict(request,desired={}),dict(request,schemaVersion=True),dict(request,runId='foreign'),dict(request,operation='set')):
            with self.subTest(value=value),self.assertRaises(Exception):command(value)

    def test_durable_original_source_restores_same_reader_continuity(self):
        boundary=Boundary();first=boundary.reader().request(RUN,'capture');reader=boundary.reader();reader.restore_source(first)
        self.assertGreater(reader.request(RUN,'observe')['sequence'],first['sequence'])
        with self.assertRaises(Exception):reader.restore_source(first)

    def test_native_endpoint_measures_closure_and_has_no_caller_supplied_values(self):
        text=(ROOT/'interface/src/scripting/TestScriptingInterface.cpp').read_text()
        body=text[text.index('QVariantMap TestScriptingInterface::phoneSnapshotSettings('):text.index('QVariantMap TestScriptingInterface::phoneSnapshotReadback(')]
        for original in ('phoneSnapshotReviewObservation','featureSnapshotObservation','"pending"','"processing"','featureSnapshotSettings(command,closed)'):
            self.assertIn(original,body)
        self.assertNotIn('command.value("closed")',body)
        lease=(ROOT/'tests/device/native/PhoneSnapshotSettingsLease.h').read_text();self.assertIn('validCommand(input)',lease)
        native=(ROOT/'interface/src/ui/Snapshot.cpp').read_text();self.assertIn('if (!Lease::validCommand(command))',native)

    def test_probe_passes_original_native_source_or_explicitly_unavailable_without_desired_results(self):
        text=(ROOT/'tests/device/probe/overte_e2e_probe.js').read_text()
        start=text.index('        if (command && command.schemaVersion === 1 && command.action === "phone-snapshot-settings"')
        body=text[start:text.index('        if (command && command.schemaVersion === 1 && command.action === "phone-snapshot-cancel"',start)]
        harness='''const assert=require('node:assert/strict');let lastPhoneSnapshotSettingsRequest='';let calls=0;let saved=[];
function objectKeysMatch(v,keys){return JSON.stringify(Object.keys(v).sort())===JSON.stringify(keys.sort());}
let original={commandId:'b'.repeat(32),source:{independent:'original'}};
const Test={phoneSnapshotSettings:()=>{calls++;return original;},saveObject:(value,path)=>saved.push({value,path})};
function apply(command){'''+body+'''}
const base={schemaVersion:1,commandId:'b'.repeat(32),runId:'a'.repeat(32),action:'phone-snapshot-settings',operation:'capture'};
apply({...base,expected:{restored:true}});assert.equal(calls,0);assert.equal(saved.length,0);
apply(base);assert.equal(calls,1);assert.equal(saved[0].value,original);assert.equal(saved[0].path,'phone-snapshot-settings.json');
apply(base);assert.equal(calls,1);
Test.phoneSnapshotSettings=()=>({});apply({...base,commandId:'c'.repeat(32),operation:'observe'});
assert.deepEqual(saved[1].value,{available:false,commandId:'c'.repeat(32)});
delete Test.phoneSnapshotSettings;apply({...base,commandId:'d'.repeat(32),operation:'observe'});
assert.deepEqual(saved[2].value,{available:false,commandId:'d'.repeat(32)});
'''
        subprocess.run(['node','-e',harness],check=True,timeout=10)


if __name__=='__main__':unittest.main()
