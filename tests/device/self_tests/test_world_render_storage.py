"""Private image-memory protocol counterexamples; no GPU/native execution."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from adapters.world_render_storage import NativeWorldRenderStorage,command,receipt_file
from adapters.world_render_evidence import image_name
from adapters.normal_ui import NativeUIError
from fixture.serve import FixtureState
from self_tests.test_native_feature_observation import probe_source

CAPTURE='a'*32


class Boundary:
    def __init__(self):
        self.raw=bytes(range(256))*520;self.clock=0.;self.sequence=0
        self.commands=[];self.files={};self.present=True;self.callbacks=0
        self.okay=True;self.ignore_release=False;self.partial=0;self.delay=0.;self.mutate=None
    def send(self,value):
        command(value);self.commands.append(deepcopy(value));self.sequence+=1
        if value['operation']=='release' and not self.ignore_release:self.present=False
        sample=dict(storageVersion=1,commandId=value['commandId'],requestId=value['requestId'],instance='b'*32,
            sequence=self.sequence,processId=31,capturedEpochMs=20000,present=self.present,
            callbacks=self.callbacks,pngBytes=len(self.raw) if self.present else 0)
        if value['operation']=='read':
            sample.update(offset=value['offset'],data=base64.b64encode(self.raw[value['offset']:value['offset']+65536]).decode())
        if self.mutate:self.mutate(sample)
        self.files[receipt_file(value['commandId'])]=json.dumps(sample)
    def read(self,name):
        self.clock+=self.delay
        if self.partial:self.partial-=1;return '{'
        return self.files.get(name,'')
    def sleep(self,value):self.clock+=value
    def storage(self,**kwargs):
        result=NativeWorldRenderStorage(self.send,self.read,lambda:20000,lambda:self.okay,31,
            monotonic=lambda:self.clock,sleep=self.sleep,**kwargs)
        capture=('ios-' if kwargs.get('ios') else '')+CAPTURE
        result.bind(dict(processId=31,instance='b'*32,requestId=capture,source=dict(image=dict(name=image_name(capture),
            bytes=len(self.raw),sha256=hashlib.sha256(self.raw).hexdigest()))))
        return result


class WorldRenderStorageTests(unittest.TestCase):
    def test_original_chunks_advance_offsets_without_reencoding_or_expected_pixel_input(self):
        source=Boundary();storage=source.storage()
        self.assertEqual(source.raw,storage.read(image_name(CAPTURE)))
        self.assertEqual([0,65536,131072],[c['offset'] for c in source.commands])
        self.assertTrue(all(c['requestId']==CAPTURE and c['operation']=='read' for c in source.commands))
        self.assertNotIn('expected',json.dumps(source.commands));self.assertNotIn('sha256',json.dumps(source.commands))

    def test_release_requires_a_fresh_independent_inventory_even_when_ack_claims_absence(self):
        source=Boundary();storage=source.storage();value=storage.release(CAPTURE)
        self.assertFalse(value['present']);self.assertIsNone(storage.capture)
        self.assertEqual(['release','inspect'],[c['operation'] for c in source.commands])
        self.assertNotEqual(source.commands[0]['commandId'],source.commands[1]['commandId'])

    def test_ignored_release_or_queued_callback_never_proves_absence(self):
        for fault in ('ignore','queued'):
            with self.subTest(fault=fault):
                source=Boundary();source.ignore_release=fault=='ignore';source.callbacks=int(fault=='queued');storage=source.storage()
                with self.assertRaises(NativeUIError):storage.release(CAPTURE)
                self.assertIsNotNone(storage.capture)
                self.assertEqual(1,sum(c['operation']=='release' for c in source.commands))
                self.assertLessEqual(len(source.commands),52)

    def test_callbacks_can_drain_after_cancellation_but_need_a_later_inventory(self):
        source=Boundary();source.callbacks=1
        def drain(sample):
            if len(source.commands)>3:sample['callbacks']=0
        source.mutate=drain;source.storage().release(CAPTURE)
        self.assertEqual(['release','inspect','inspect','inspect'],[c['operation'] for c in source.commands])

    def test_foreign_context_process_request_and_stale_or_regressing_receipts_fail(self):
        faults=[('instance','c'*32),('processId',32),('requestId','d'*32),('capturedEpochMs',19000),('sequence',0),
                ('present',1),('callbacks',True),('pngBytes',True),('storageVersion',True)]
        for key,value in faults:
            with self.subTest(key=key):
                source=Boundary();source.mutate=lambda s:s.update({key:value})
                with self.assertRaises(NativeUIError):source.storage().read(image_name(CAPTURE))
                self.assertEqual(1,len(source.commands))

    def test_missing_truncated_reordered_or_changed_original_chunks_fail(self):
        for fault in ('empty','offset','short','changed','bytes','base64'):
            with self.subTest(fault=fault):
                source=Boundary()
                def mutate(sample):
                    if fault=='empty':sample['data']=''
                    elif fault=='offset':sample['offset']=1
                    elif fault=='short':sample['data']=base64.b64encode(b'partial').decode()
                    elif fault=='changed':sample['data']=base64.b64encode(b'x'*min(65536,len(source.raw)-sample['offset'])).decode()
                    elif fault=='bytes':sample['pngBytes']+=1
                    elif fault=='base64':sample['data']='!'+sample['data']
                source.mutate=mutate
                with self.assertRaises(NativeUIError):source.storage().read(image_name(CAPTURE))

    def test_chunk_transfer_has_an_overall_budget_not_a_new_budget_per_chunk(self):
        source=Boundary();source.delay=.6
        with self.assertRaises(NativeUIError):source.storage(ios=True).read(image_name(CAPTURE))
        self.assertEqual(3,len(source.commands))

    def test_context_change_after_original_binary_read_fails(self):
        source=Boundary();original=source.read
        def changed(name):
            raw=original(name);source.okay=False;return raw
        source.read=changed
        with self.assertRaises(NativeUIError):source.storage().read(image_name(CAPTURE))

    def test_partial_receipt_retries_only_read_and_never_resends_release(self):
        source=Boundary();source.partial=3;source.storage().release(CAPTURE)
        self.assertEqual(['release','inspect'],[c['operation'] for c in source.commands])

    def test_logical_name_cannot_select_foreign_image_or_arbitrary_files(self):
        source=Boundary();storage=source.storage()
        for name in ('../user.png',image_name('c'*32),'world-render-image-user.png'):
            with self.assertRaises(NativeUIError):storage.read(name)
        self.assertEqual([],source.commands)

    def test_fixture_and_probe_dispatch_only_closed_original_storage_commands(self):
        value=dict(schemaVersion=1,commandId='ios-'+'b'*32,action='feature-world-render-storage',
            requestId='ios-'+CAPTURE,operation='read',offset=0)
        self.assertEqual(value,FixtureState().set_client_command(value))
        for edit in ({'offset':True},{'offset':.5},{'offset':33554432},{'expected':True},{'path':'/user.png'}):
            with self.assertRaises((ValueError,RuntimeError)):FixtureState().set_client_command(value|edit)
        script=r'''
const Uuid={generate:()=>"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"};
const objectKeysMatch=(v,keys)=>JSON.stringify(Object.keys(v).sort())===JSON.stringify(keys.sort());
'''+probe_source()+r'''
const calls=[],files=[];
const original={storageVersion:1,commandId:"b".repeat(32),requestId:"a".repeat(32),data:"original"};
const Test={featureWorldRenderStorage:c=>{calls.push(c);return original;},saveObject:(v,n)=>files.push({v,n})};
applyClientCommand({schemaVersion:1,commandId:"b".repeat(32),requestId:"a".repeat(32),action:"feature-world-render-storage",operation:"read",offset:0});
if(calls.length!==1||files[0].v!==original||files[0].n!=="world-render-storage-"+"b".repeat(32)+".json")throw Error("original transport changed");
for(const edit of [{offset:true},{offset:0.5},{expected:1},{path:"/user.png"}])applyClientCommand(Object.assign({},calls[0],edit));
if(calls.length!==1)throw Error("open command");
'''
        result=subprocess.run(['node','-e',script],capture_output=True,text=True,timeout=5)
        self.assertEqual(0,result.returncode,result.stderr)
