"""Actual source lock/validators, with explicit native transport and clock seams."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import subprocess
import unittest
import uuid
from unittest.mock import patch

from adapters.normal_ui import NativeUIError
from adapters.pico4.world_render_retirements import PicoWorldRenderRetirements,command,ACTION
from adapters.script_journey.lock import ScriptSourceLock


def proof(binding,role,index):
    capture=uuid.uuid4().hex;receipt=uuid.uuid4().hex
    memory=dict(storageVersion=1,commandId=receipt,requestId=capture,instance='a'*32,sequence=index*3+1,
        processId=31,capturedEpochMs=19000,present=False,callbacks=0,pngBytes=0)
    source=dict(retired=True,present=False,callbacks=0,pngBytes=0,complete=True,
        receipts=[dict(receiptId=receipt,issued=True,exists=False,originalMatches=False)])
    removed=dict(receiptInventoryVersion=1,commandId=uuid.uuid4().hex,requestId=capture,operation='remove',
        instance='a'*32,sequence=index*3+2,processId=31,capturedEpochMs=19000,source={**source,'performed':True})
    absent={**deepcopy(removed),'commandId':uuid.uuid4().hex,'operation':'inspect','sequence':index*3+3,'source':source}
    owner=dict(ownershipVersion=2,binding=deepcopy(binding),role=role,
        capture=dict(schemaVersion=1,commandId=capture,action='feature-world-render-observe'),receipts=[receipt])
    return dict(memory=memory,files=dict(removed=removed,absent=absent),owner=owner)


class Boundary:
    def __init__(self,root,*,count=2):
        self.binding=dict(sourceRevision='b'*40,artifactSha256='c'*64,processIdentity='31:start',
            sessionId='pico-test',generation=0,targetFingerprint='d'*64)
        self.proofs=[proof(self.binding,'primary' if i%2==0 else 'actor',i) for i in range(count)]
        self.lock=ScriptSourceLock(root/'script-sources.lock')
        self.epoch=20000;self.host=0.;self.sequence=0;self.floor=count*3;self.commands=[]
        self.value=None;self.mutate=None;self.guard_hook=None;self.read_hook=None;self.partial=0
        with self.lock.held():
            self.reader=PicoWorldRenderRetirements(self.send,self.original,lambda:self.epoch,self.guard,31,
                self.binding,self.lock,'e'*32,self.proofs,monotonic=lambda:self.host,sleep=self.sleep)

    def guard(self):
        if self.guard_hook:self.guard_hook()
        return True

    def send(self,request):
        command(request);self.commands.append(deepcopy(request));self.sequence+=1
        captures=[]
        for original in self.proofs:
            self.floor+=1;packet=deepcopy(original['files']['absent'])
            packet.update(commandId=uuid.uuid4().hex,sequence=self.floor,capturedEpochMs=self.epoch)
            captures.append(packet)
        self.value=dict(worldRenderRetirementsVersion=1,requestId=request['commandId'],runId=request['runId'],
            instance='a'*32,sequence=self.sequence,processId=31,requestedEpochMs=self.epoch,
            capturedEpochMs=self.epoch,captures=captures)
        if self.mutate:self.mutate(self.value)

    def original(self):
        if self.read_hook:self.read_hook()
        if self.partial:self.partial-=1;return '{'
        # Whitespace is intentional: the reader must retain these actual bytes.
        return json.dumps(self.value,indent=1)+'\n'

    def sleep(self,seconds):self.host+=seconds;self.epoch+=round(seconds*1000)


class PicoWorldRenderRetirementsTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.root=Path(temp.name)

    def source(self,**kwargs):
        path=self.root/uuid.uuid4().hex;path.mkdir(mode=0o700);return Boundary(path,**kwargs)

    def test_all_original_captures_share_one_request_and_retain_exact_raw_bytes(self):
        source=self.source(count=80);before=deepcopy(source.proofs);result=source.reader.read()
        self.assertEqual(80,len(result['captures']));self.assertEqual(1,len(source.commands))
        self.assertEqual(before,source.proofs);self.assertEqual(before,source.reader.proofs)
        self.assertEqual(source.original().encode(),source.reader.last_raw)
        self.assertEqual(hashlib.sha256(source.reader.last_raw).hexdigest(),source.reader.last_sha256)
        self.assertEqual({'schemaVersion','commandId','action','runId','captures'},set(source.commands[0]))
        result['captures'].clear();self.assertEqual(80,len(json.loads(source.reader.last_raw)['captures']))
        second=source.reader.read();self.assertEqual(2,second['sequence'])
        self.assertEqual(2,len(source.commands));self.assertIsNone(source.reader.pending)

    def test_partial_original_polling_never_resends_the_query(self):
        source=self.source();source.partial=2
        self.assertEqual(2,len(source.reader.read()['captures']));self.assertEqual(1,len(source.commands))

    def test_missing_duplicate_foreign_or_reordered_capture_cannot_prove_whole_absence(self):
        for fault in ('missing','duplicate','foreign','reordered'):
            source=self.source()
            def mutate(value):
                rows=value['captures']
                if fault=='missing':rows.pop()
                elif fault=='duplicate':rows[1]=deepcopy(rows[0])
                elif fault=='foreign':rows[0]['requestId']=uuid.uuid4().hex
                else:rows.reverse()
            source.mutate=mutate
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):source.reader.read()
            self.assertTrue(source.reader.failed);self.assertIsNotNone(source.reader.pending)

    def test_original_issuer_memory_file_and_native_identity_failures_are_not_hidden(self):
        mutations=[lambda p:p.update(instance='f'*32),lambda p:p.update(processId=32),
            lambda p:p.update(sequence=1),lambda p:p.update(operation='remove'),
            lambda p:p['source'].update(retired=False),lambda p:p['source'].update(callbacks=1),
            lambda p:p['source'].update(pngBytes=4),lambda p:p['source'].update(complete=False),
            lambda p:p['source']['receipts'][0].update(exists=True),
            lambda p:p['source']['receipts'][0].update(issued=False)]
        for index,mutate in enumerate(mutations):
            source=self.source();source.mutate=lambda value:mutate(value['captures'][0])
            with self.subTest(index=index),self.assertRaises(NativeUIError):source.reader.read()
            self.assertEqual(0,source.reader.sequence)

    def test_wrapper_types_cursors_epochs_and_schema_are_strict(self):
        changes=[dict(worldRenderRetirementsVersion=True),dict(sequence=True),dict(sequence=0),
            dict(instance='f'*32),dict(processId=32),dict(runId='f'*32),dict(requestedEpochMs=19999),
            dict(capturedEpochMs=19999),dict(extra=True)]
        for change in changes:
            source=self.source();source.mutate=lambda value:value.update(change)
            with self.subTest(change=change),self.assertRaises(NativeUIError):source.reader.read()

    def test_stale_one_capture_or_backward_time_fails_the_entire_batch(self):
        for fault in ('one-old','native-span','slow-read','epoch-backward'):
            source=self.source()
            if fault=='one-old':source.mutate=lambda value:value['captures'][0].update(capturedEpochMs=19999)
            elif fault=='native-span':source.mutate=lambda value:value.update(capturedEpochMs=21500)
            elif fault=='slow-read':source.read_hook=lambda:source.sleep(1.5)
            else:source.read_hook=lambda:setattr(source,'epoch',19999)
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):source.reader.read()
            self.assertIsNone(source.reader.last_raw)

    def test_lost_query_is_not_replayed_even_if_the_original_arrives_later(self):
        source=self.source();original=source.original
        source.reader.original=lambda:''
        with self.assertRaises(NativeUIError):source.reader.read()
        source.reader.original=original
        with self.assertRaises(NativeUIError):source.reader.read()
        self.assertEqual(1,len(source.commands));self.assertIsNotNone(source.reader.pending)

    def test_final_guard_cost_and_actual_lock_exit_are_inside_failure_latch(self):
        for fault in ('guard-time','exit-time','exit-error'):
            source=self.source()
            if fault=='guard-time':
                calls=[0]
                def guard():
                    calls[0]+=1
                    if calls[0]==3:source.sleep(1.5)
                source.guard_hook=guard
            else:
                original=source.lock.held
                @contextmanager
                def held():
                    with original():yield
                    if fault=='exit-time':source.sleep(1.5)
                    else:raise RuntimeError('Original lock exit failed')
                source.lock.held=held
            with self.subTest(fault=fault),self.assertRaises(Exception):source.reader.read()
            self.assertTrue(source.reader.failed);self.assertIsNotNone(source.reader.pending)
            self.assertEqual(0,source.reader.sequence)

    def test_admitted_proof_mutation_is_refused_before_sending(self):
        source=self.source();source.reader.proofs[0]['owner']['role']='actor'
        with self.assertRaises(NativeUIError):source.reader.read()
        self.assertEqual([],source.commands)

    def test_original_query_nonce_cannot_be_reused_inside_fresh_wrapper(self):
        source=self.source();source.mutate=lambda value:value['captures'][0].update(
            commandId=source.proofs[0]['files']['absent']['commandId'])
        with self.assertRaises(NativeUIError):source.reader.read()

    def test_final_result_copy_cost_is_charged_to_original_window(self):
        source=self.source();original=deepcopy
        def copying(value):
            result=original(value)
            if type(value) is dict and 'worldRenderRetirementsVersion' in value:source.sleep(1.5)
            return result
        with patch('adapters.pico4.world_render_retirements.deepcopy',side_effect=copying):
            with self.assertRaises(NativeUIError):source.reader.read()
        self.assertTrue(source.reader.failed);self.assertEqual(0,source.reader.sequence)

    def test_actual_pico_factory_reuses_canonical_lock_binding_and_original_capture_proof(self):
        from self_tests.test_pico_browser_stereo import PicoBrowserStereoTests
        helper=PicoBrowserStereoTests();model=helper.model();self.addCleanup(helper.doCleanups)
        state=model.browser_stereo().acquire('b'*32);original_proof=state['proof']
        # Actual native producers create different UUIDs for their independent
        # generic observer and GPU backend. Sharing one mock UUID hid a bad join.
        model.features.mutate=lambda value:value.update(processId=31,instance='f'*32,
            graphics=deepcopy(model.body['nativeBefore']['graphics']))
        facade,stores=helper.retired_binding(model);native_factory=facade.original._native_feature_observer
        source=self.source();source.proofs=[deepcopy(original_proof)];source.floor=original_proof['files']['absent']['sequence']
        def native(target):
            reader=native_factory(target);send=reader.send
            reader.send=lambda request:source.send(request) if request['action']==ACTION else send(request)
            return reader
        facade.original._native_feature_observer=native
        def read(target,package,path,*,attempts):
            self.assertEqual(('owned','org.overte.pico','files/overte-e2e/feature-pico-world-render-retirements.json',1),
                (target,package,path,attempts));return source.original()
        facade.original.adb.read_debug_app_file=read
        with self.assertRaises(NativeUIError):
            facade._tablet_web_retired_captures_observer('owned',[original_proof],model.lock,'e'*32)
        with model.lock.held():
            reader=facade._tablet_web_retired_captures_observer('owned',[original_proof],model.lock,'e'*32)
        packet=reader.read();self.assertIs(reader.lock,model.lock);self.assertEqual(1,len(packet['captures']))
        self.assertEqual(original_proof['owner']['capture']['commandId'],source.commands[0]['captures'][0]['requestId'])
        self.assertEqual(1,len(source.commands))
        stores[('default','default')].write(dict(foreign=True),None)
        with self.assertRaises(NativeUIError):reader.read()
        self.assertEqual(1,len(source.commands));self.assertTrue(model.artifacts.exists())

    def test_single_original_reader_also_keeps_generic_and_gpu_native_births_distinct(self):
        from self_tests.test_pico_browser_stereo import PicoBrowserStereoTests
        helper=PicoBrowserStereoTests();model=helper.model();self.addCleanup(helper.doCleanups)
        state=model.browser_stereo().acquire('b'*32);original=state['proof']
        model.features.mutate=lambda value:value.update(processId=31,instance='f'*32,
            graphics=deepcopy(model.body['nativeBefore']['graphics']))
        facade,_stores=helper.retired_binding(model)
        with model.lock.held():
            reader=facade._tablet_web_retired_capture_observer('owned',original,model.lock)
            packet=reader.request('inspect')
        self.assertEqual(original['memory']['instance'],packet['instance']);self.assertNotEqual('f'*32,packet['instance'])

    def test_command_never_accepts_requested_verdict_paths_duplicate_ids_or_unbounded_sets(self):
        base=dict(schemaVersion=1,commandId='1'*32,action=ACTION,runId='2'*32,
            captures=[dict(requestId='3'*32,receiptIds=['4'*32])])
        for fault in ('expected','path','duplicate-capture','duplicate-receipt','bool','empty','large'):
            value=deepcopy(base)
            if fault=='expected':value['expectedAbsent']=True
            elif fault=='path':value['captures'][0]['path']='/private/file'
            elif fault=='duplicate-capture':value['captures']*=2
            elif fault=='duplicate-receipt':value['captures'][0]['receiptIds']*=2
            elif fault=='bool':value['schemaVersion']=True
            elif fault=='empty':value['captures']=[]
            else:value['captures']*=257
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):command(value)

    def test_actual_probe_preserves_original_batch_and_refuses_duplicate_or_expected_selectors(self):
        from self_tests.test_native_feature_observation import probe_source
        program=r'''
const Uuid={generate:()=>"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"};
const objectKeysMatch=(v,keys)=>JSON.stringify(Object.keys(v).sort())===JSON.stringify(keys.sort());
let calls=[],files=[];const original={worldRenderRetirementsVersion:1,requestId:"a".repeat(32),capturedEpochMs:17000,captures:[]};
const Test={featurePicoWorldRenderRetirements:v=>{calls.push(v);return original;},saveObject:(v,name)=>files.push({v,name})};
SOURCE
const request={schemaVersion:1,commandId:"a".repeat(32),action:"feature-pico-world-render-retirements",runId:"b".repeat(32),
    captures:[{requestId:"c".repeat(32),receiptIds:["d".repeat(32)]}]};
applyAndroidControlCommand(request);applyAndroidControlCommand(request);
if(calls.length!==1||files.length!==1||files[0].v!==original||original.capturedEpochMs!==17000)throw Error("Original replaced or retimed");
if(files[0].name!=="feature-pico-world-render-retirements.json")throw Error("Wrong private output");
for(const extra of [{expectedAbsent:true},{captures:[request.captures[0],request.captures[0]]},
        {captures:[{requestId:"c".repeat(32),receiptIds:["d".repeat(32),"d".repeat(32)]}]}]) {
    applyClientCommand({...request,commandId:"e".repeat(32),...extra});
}
if(calls.length!==1)throw Error("Invalid selectors reached native source");
delete Test.featurePicoWorldRenderRetirements;applyClientCommand({...request,commandId:"f".repeat(32)});
if(files.length!==2||files[1].v.available!==false)throw Error("Missing original source qualified");
'''.replace('SOURCE',probe_source())
        result=subprocess.run(['node','-e',program],capture_output=True,text=True,timeout=5)
        self.assertEqual(0,result.returncode,result.stderr)
