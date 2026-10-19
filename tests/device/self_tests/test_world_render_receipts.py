"""Native cleanup protocol on original local receipt files; no C++/device run."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from adapters.normal_ui import NativeUIError
from adapters.world_render_receipts import NativeWorldReceiptCleanup,command
from fixture.serve import FixtureState
from self_tests.test_native_feature_observation import probe_source


class Boundary:
    def __init__(self,path,ios=False):
        prefix='ios-' if ios else ''
        self.owner=dict(capture=dict(commandId=prefix+'a'*32),receipts=[prefix+'b'*32])
        self.name='world-render-storage-'+'b'*32+'.json'
        self.path=path/self.name;self.path.write_text('original private receipt bytes')
        self.commands=[];self.sample=None;self.clock=0.;self.sequence=0;self.partial=0
        self.okay=True;self.ignore_remove=False;self.mutate=None;self.delay=0.
        self.native=NativeWorldReceiptCleanup(self.send,self.original,lambda:20000,lambda:self.okay,31,
            lambda:deepcopy(self.owner),lambda:'c'*32,ios=ios,monotonic=lambda:self.clock,sleep=self.sleep)
    def send(self,value):
        command(value);self.commands.append(deepcopy(value));self.sequence+=1
        if value['operation']=='remove':
            if not self.ignore_remove:self.path.unlink(missing_ok=True)
            source=dict(performed=True)
        else:source=dict(exists=self.path.exists())
        self.sample=dict(receiptVersion=1,commandId=value['commandId'],requestId=value['requestId'],receiptId=value['receiptId'],
            operation=value['operation'],instance='c'*32,sequence=self.sequence,processId=31,capturedEpochMs=20000,source=source)
        if self.mutate:self.mutate(self.sample)
    def original(self):
        self.clock+=self.delay
        if self.partial:self.partial-=1;return '{'
        return json.dumps(self.sample)
    def sleep(self,value):self.clock+=value


class WorldRenderReceiptTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        self.source=Boundary(Path(tmp.name));self.native=self.source.native

    def test_native_remove_ack_and_independent_actual_file_absence_are_separate(self):
        self.native.remove(self.source.name);self.assertTrue(self.native.absent(self.source.name))
        self.assertEqual(['remove','inspect'],[c['operation'] for c in self.source.commands])
        self.assertNotEqual(self.source.commands[0]['commandId'],self.source.commands[1]['commandId'])
        self.assertFalse(self.source.path.exists())

    def test_ignored_delete_with_successful_ack_remains_present(self):
        self.source.ignore_remove=True;self.native.remove(self.source.name)
        self.assertFalse(self.native.absent(self.source.name));self.assertTrue(self.source.path.exists())

    def test_unissued_or_foreign_path_never_reaches_native_deletion(self):
        for name in ('../user.json','world-render-storage-'+'d'*32+'.json','/user/image.png'):
            with self.assertRaises(NativeUIError):self.native.remove(name)
        self.assertEqual([],self.source.commands);self.assertTrue(self.source.path.exists())

    def test_foreign_process_context_request_receipt_or_operation_is_rejected(self):
        for key,value in (('processId',32),('instance','d'*32),('requestId','d'*32),('receiptId','e'*32),
                          ('operation','inspect'),('sequence',0),('capturedEpochMs',19000),('receiptVersion',True)):
            with self.subTest(key=key):
                self.source.mutate=lambda sample:sample.update({key:value})
                with self.assertRaises(NativeUIError):self.native.remove(self.source.name)

    def test_numeric_existence_or_performed_cannot_qualify_an_inventory(self):
        for operation in ('remove','inspect'):
            self.source.mutate=lambda sample:sample.update(source={('performed' if operation=='remove' else 'exists'):1})
            with self.assertRaises(NativeUIError):self.native.request(operation,self.source.name)

    def test_original_incomplete_reads_retry_without_replaying_mutation(self):
        self.source.partial=3;self.native.remove(self.source.name)
        self.assertEqual(1,len(self.source.commands))

    def test_process_or_ownership_change_after_native_read_refuses_receipt(self):
        def change(sample):self.source.owner['capture']['commandId']='d'*32
        self.source.mutate=change
        with self.assertRaises(NativeUIError):self.native.remove(self.source.name)

    def test_ios_nonce_causality_includes_the_entire_receipt_transfer_budget(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);source=Boundary(Path(tmp.name),ios=True)
        source.delay=1.51
        with self.assertRaises(NativeUIError):source.native.remove(source.name)
        self.assertEqual(1,len(source.commands))

    def test_fixture_rejects_paths_expected_results_foreign_versions_and_extra_fields(self):
        request=dict(schemaVersion=1,commandId='ios-'+'a'*32,action='feature-world-render-receipt',
            requestId='ios-'+'b'*32,receiptId='ios-'+'c'*32,operation='inspect')
        self.assertEqual(request,FixtureState().set_client_command(request))
        for edit in ({'schemaVersion':True},{'path':'/user.png'},{'expected':False},{'receiptId':'user.json'},{'operation':'erase'}):
            with self.assertRaises((ValueError,RuntimeError)):FixtureState().set_client_command(request|edit)

    def test_original_probe_preserves_native_inventory_and_deduplicates_cleanup_requests(self):
        script=r'''
const Uuid={generate:()=>"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"};
const objectKeysMatch=(v,k)=>JSON.stringify(Object.keys(v).sort())===JSON.stringify(k.sort());
'''+probe_source()+r'''
const calls=[],files=[];const original={receiptVersion:1,source:{exists:true},capturedEpochMs:17000};
const Test={featureWorldRenderReceipt:c=>{calls.push(c);return original;},saveObject:(v,n)=>files.push({v,n})};
const request={schemaVersion:1,commandId:"a".repeat(32),requestId:"b".repeat(32),receiptId:"c".repeat(32),action:"feature-world-render-receipt",operation:"inspect"};
applyAndroidControlCommand(request);applyAndroidControlCommand(request);
if(calls.length!==1||files.length!==1||files[0].v!==original||files[0].n!=="world-render-receipt-result.json")throw Error("native inventory altered/replayed");
applyClientCommand(Object.assign({},request,{commandId:"d".repeat(32),expected:false}));
if(calls.length!==1)throw Error("expected existence entered native query");
'''
        result=subprocess.run(['node','-e',script],capture_output=True,text=True,timeout=5)
        self.assertEqual(0,result.returncode,result.stderr)
