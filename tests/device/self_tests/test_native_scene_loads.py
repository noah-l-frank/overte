"""Synthetic original request/closure lifetimes; no C++ build or device run."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from adapters.native_scene_loads import NativeSceneLoads,command,committed,continuity,resource_hash
from adapters.normal_ui import NativeUIError
from self_tests.test_native_feature_observation import probe_source

RUN='b'*32
URL='http://controlled.invalid/feature-fixture/v1/runs/'+RUN+'/tickets/'+'c'*32+'/graphics-scene.v1.json'


def row(identifier='d'*32,**changes):
    value=dict(id=identifier,kind='request',generation=1,resourceSha256=resource_hash(URL),startedEpochMs=20000,
        updatedEpochMs=20000,releasedEpochMs=20000,phase='committed',pending=False,result=0,bytes=1234)
    value.update(changes);return value


class Boundary:
    def __init__(self):
        self.clock=0.;self.epoch=20000;self.okay=True;self.sequence=0;self.generation=1;self.rows=[row()]
        self.complete=True;self.sample=None;self.commands=[];self.mutate=None;self.partial=0;self.ignore=False
    def send(self,request):
        command(request,ios=request['commandId'].startswith('ios-'));self.commands.append(deepcopy(request))
        if self.ignore:return
        self.sequence+=1
        self.sample=dict(sceneLoadVersion=1,commandId=request['commandId'],runId=request['runId'],instance='a'*32,
            sequence=self.sequence,processId=31,capturedEpochMs=self.epoch,currentGeneration=self.generation,
            pendingLeases=sum(item['pending'] for item in self.rows),complete=self.complete,requests=deepcopy(self.rows))
        if self.mutate:self.mutate(self.sample)
    def original(self):
        if self.partial:self.partial-=1;return '{'
        return json.dumps(self.sample) if self.sample is not None else ''
    def sleep(self,seconds):self.clock+=seconds
    def reader(self,**options):return NativeSceneLoads(self.send,self.original,lambda:self.epoch,lambda:self.okay,31,
        monotonic=lambda:self.clock,sleep=self.sleep,**options)


class SceneLoadTests(unittest.TestCase):
    def test_ios_nonce_preserves_original_native_clock_and_request_history(self):
        source=Boundary();source.epoch+=86400000
        reader=source.reader(ios=True);value=reader.read(RUN)
        self.assertTrue(value['commandId'].startswith('ios-'))
        self.assertEqual(source.epoch,value['capturedEpochMs']);self.assertEqual(source.rows,value['requests'])
        self.assertEqual(20000,value['requests'][0]['startedEpochMs'])
        self.assertEqual(source.rows[0],committed(value,URL))
        source.mutate=lambda value:value.update(capturedEpochMs=20000)
        with self.assertRaises(NativeUIError):reader.read(RUN)

    def test_ios_fixture_admits_only_closed_original_source_queries(self):
        from fixture.serve import FixtureState
        source=FixtureState();request=dict(schemaVersion=1,commandId='ios-'+'a'*32,action='feature-scene-load-observe',runId=RUN)
        self.assertEqual(request,source.set_client_command(request))
        for changes in (dict(expectedGeneration=1),dict(commandId='a'*32),dict(runId=True)):
            with self.assertRaises((NativeUIError,ValueError)):source.set_client_command(request|changes)

    def test_original_committed_record_requires_actual_released_request_group(self):
        source=Boundary();reader=source.reader();value=reader.read(RUN)
        self.assertEqual(source.sample,value);self.assertEqual(source.rows[0],committed(value,URL))
        self.assertEqual({'schemaVersion','commandId','action','runId'},set(source.commands[0]))
        self.assertNotIn('expected',json.dumps(source.commands));self.assertNotIn('passed',value)
        self.assertEqual(20000,value['capturedEpochMs'])

    def test_commit_ack_with_a_still_held_callback_group_is_not_retirement(self):
        source=Boundary();source.rows[0].update(pending=True,releasedEpochMs=None)
        reader=source.reader()
        with self.assertRaises(NativeUIError):committed(reader.read(RUN),URL)
        source.rows[0].update(pending=False,releasedEpochMs=20000)
        self.assertEqual('committed',committed(reader.read(RUN),URL)['phase'])

    def test_an_older_queued_group_cannot_hide_behind_a_newer_committed_scene(self):
        source=Boundary();source.rows[0].update(phase='queued',pending=True,releasedEpochMs=None)
        source.generation=2;source.rows.append(row('e'*32,generation=2));reader=source.reader()
        with self.assertRaises(NativeUIError):committed(reader.read(RUN),URL)
        source.rows[0].update(phase='stale',pending=False,releasedEpochMs=20000)
        self.assertEqual(2,committed(reader.read(RUN),URL)['generation'])

    def test_owner_thread_delivery_is_counted_until_its_original_closure_retires(self):
        source=Boundary();source.rows.append(row('e'*32,kind='delivery',generation=0,phase='running',pending=True,
            releasedEpochMs=None,result=None,bytes=None));reader=source.reader()
        with self.assertRaises(NativeUIError):committed(reader.read(RUN),URL)
        source.rows[-1].update(phase='delivered',pending=False,releasedEpochMs=20000)
        self.assertEqual('committed',committed(reader.read(RUN),URL)['phase'])

    def test_failed_destroyed_empty_or_noncurrent_generation_is_not_loaded_scene_proof(self):
        for phase in ('failed','destroyed','empty','queued'):
            source=Boundary();source.rows[0]['phase']=phase
            if phase=='empty':source.rows[0].update(result=None,bytes=None)
            if phase=='queued':source.rows[0].update(pending=True,releasedEpochMs=None)
            with self.subTest(phase=phase),self.assertRaises(NativeUIError):committed(source.reader().read(RUN),URL)
        source=Boundary();source.generation=2
        with self.assertRaises(NativeUIError):committed(source.reader().read(RUN),URL)

    def test_resource_identity_ignores_only_viewpoint_and_preserves_other_original_query_bytes(self):
        self.assertEqual(resource_hash(URL),resource_hash(URL+'?location=%2F0%2C0%2C0%2F0%2C0%2C0%2C1'))
        self.assertEqual(resource_hash(URL+'?value=%2F&flag'),resource_hash(URL+'?location=/0,0,0&value=%2F&flag'))
        self.assertNotEqual(resource_hash(URL),resource_hash(URL+'?token=other'))
        source=Boundary()
        with self.assertRaises(NativeUIError):committed(source.reader().read(RUN),URL+'-foreign')
        self.assertEqual(hashlib.sha256(URL.encode()).hexdigest(),resource_hash(URL))

    def test_missing_native_source_ignored_delivery_or_incomplete_inventory_stays_unavailable(self):
        for fault in ('ignored','quota','empty'):
            source=Boundary();source.ignore=fault=='ignored';source.complete=fault!='quota'
            reader=source.reader()
            if fault=='empty':reader.original=lambda:'{}'
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):reader.read(RUN)
            self.assertIsNone(reader.last);self.assertEqual(1,len(source.commands))

    def test_foreign_nonce_pid_context_clock_or_cursor_cannot_replace_original_history(self):
        for key,value in (('processId',32),('instance','f'*32),('capturedEpochMs',19999),('sequence',1),('sceneLoadVersion',2)):
            source=Boundary();reader=source.reader();reader.read(RUN)
            source.mutate=lambda packet:packet.update({key:value})
            with self.subTest(key=key),self.assertRaises(NativeUIError):reader.read(RUN)
            self.assertEqual(1,reader.last['sequence'])
        source=Boundary();source.mutate=lambda packet:packet.update(commandId='f'*32)
        with self.assertRaises(NativeUIError):source.reader().read(RUN)

    def test_duplicate_missing_or_changed_request_prefix_is_not_original_continuity(self):
        for fault in ('id','resource','start','truncate','generation','revive','result'):
            source=Boundary();reader=source.reader();reader.read(RUN)
            if fault=='id':source.rows[0]['id']='f'*32
            elif fault=='resource':source.rows[0]['resourceSha256']='f'*64
            elif fault=='start':source.rows[0]['startedEpochMs']=19999
            elif fault=='truncate':source.rows=[]
            elif fault=='generation':source.generation=0
            elif fault=='revive':source.rows[0].update(pending=True,releasedEpochMs=None)
            else:source.rows[0]['bytes']=4321
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):reader.read(RUN)

    def test_pending_count_boolean_types_result_and_release_fields_must_be_consistent(self):
        for fault in ('count','pending','complete','missing-result','bad-result','release','duplicate','kind'):
            source=Boundary()
            def bad(packet):
                item=packet['requests'][0]
                if fault=='count':packet['pendingLeases']=1
                elif fault=='pending':item['pending']=0
                elif fault=='complete':packet['complete']=1
                elif fault=='missing-result':item['result']=None
                elif fault=='bad-result':item['result']=True
                elif fault=='release':item['releasedEpochMs']=None
                elif fault=='duplicate':packet['requests'].append(deepcopy(item))
                else:item['kind']='all-callbacks'
            source.mutate=bad
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):source.reader().read(RUN)

    def test_partial_writes_retry_original_reads_without_reissuing_observation(self):
        source=Boundary();source.partial=2;value=source.reader().read(RUN)
        self.assertEqual('committed',committed(value,URL)['phase']);self.assertEqual(1,len(source.commands))

    def test_closed_grammar_rejects_expected_scene_values_and_other_platform_nonces(self):
        request=dict(schemaVersion=1,commandId='a'*32,action='feature-scene-load-observe',runId=RUN)
        self.assertEqual(request,command(request))
        for change in (dict(expectedGeneration=3),dict(url=URL),dict(commandId='ios-'+'a'*32),dict(schemaVersion=True)):
            with self.subTest(change=change),self.assertRaises(NativeUIError):command(request|change)

    def test_freshness_query_and_final_guard_cannot_hide_clock_regression_or_scope_loss(self):
        for fault in ('clock','guard','latency'):
            source=Boundary();reader=source.reader();calls=[]
            def epoch():
                calls.append(True)
                if len(calls)==3:
                    if fault=='clock':return 19999
                    if fault=='guard':source.okay=False
                    else:source.clock+=1.6
                return 20000
            reader.clock_ms=epoch
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):reader.read(RUN)
            self.assertIsNone(reader.last)

    def test_actual_probe_preserves_native_lifetime_object_and_deduplicates_only_its_command(self):
        program=r'''
const Uuid={generate:()=>"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"};
const objectKeysMatch=(v,k)=>JSON.stringify(Object.keys(v).sort())===JSON.stringify(k.sort());
let files=[],calls=[];
const original={sceneLoadVersion:1,commandId:"a".repeat(32),capturedEpochMs:17000,pendingLeases:3,requests:[]};
const Test={featureSceneLoadObservation:c=>{calls.push(c);return original;},saveObject:(v,name)=>files.push({v,name})};
SOURCE
const request={schemaVersion:1,commandId:"a".repeat(32),action:"feature-scene-load-observe",runId:"b".repeat(32)};
applyAndroidControlCommand(request);applyAndroidControlCommand(request);
if(calls.length!==1||files.length!==1||files[0].v!==original||original.pendingLeases!==3||original.capturedEpochMs!==17000)throw Error("Original lifetime altered or replayed");
if(files[0].name!=="feature-scene-load.json")throw Error("wrong original path");
applyAndroidControlCommand({...request,commandId:"c".repeat(32),expectedGeneration:1});
if(calls.length!==1)throw Error("expected state reached native");
delete Test.featureSceneLoadObservation;applyAndroidControlCommand({...request,commandId:"d".repeat(32)});
if(files.length!==2||files[1].v.available!==false)throw Error("missing source green");
'''.replace('SOURCE',probe_source())
        result=subprocess.run(['node','-e',program],capture_output=True,text=True,timeout=5)
        self.assertEqual(0,result.returncode,result.stderr)
