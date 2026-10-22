"""Real host weak capture owners and strict original native work codecs."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import base64
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace
import unittest
import uuid
import weakref
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from fixture.serve import FixtureState
from ios.adapters import snapshot_file_work as source,feature_observation
from ios.self_tests.test_ios_feature_observation import Native as Transport
from self_tests.test_native_feature_observation import probe_source

RUN='a'*32


def query():return dict(schemaVersion=1,action=source.ACTION,commandId='ios-'+uuid.uuid4().hex,runId=RUN)


class Token:pass


class Jobs:
    def __init__(self):self.now=10000;self.sequence=0;self.jobs={}
    def tick(self):self.now+=1;return self.now
    def clock(self):return dict(epochMs=self.tick(),monotonicMs=self.now-10000)
    def queued(self):
        token=Token();identifier=uuid.uuid4().hex
        command=dict(schemaVersion=1,commandId='ios-'+uuid.uuid4().hex,action='snapshot-files',operation='list',prefix='parity-'+RUN[:16]+'-still-png')
        row=dict(id=identifier,query=command,queuedEpochMs=self.tick(),enteredEpochMs=None,returnedEpochMs=None,
            finallyEpochMs=None,expiredEpochMs=None,publication=None,publishedEpochMs=None,alive=True)
        self.jobs[identifier]=(weakref.ref(token),row)
        def actual_job():
            held=token
            row.update(enteredEpochMs=self.tick());row.update(publication=True,publishedEpochMs=self.tick())
            row.update(returnedEpochMs=self.tick());row.update(finallyEpochMs=self.tick())
            return held
        return actual_job,command
    def read(self,command=None,after_snapshot=None):
        command=command or query();before=self.clock();rows=[];self.sequence+=1
        for weak,record in self.jobs.values():
            if weak() is None and record['expiredEpochMs'] is None:record['expiredEpochMs']=self.tick()
            rows.append(dict(deepcopy(record),alive=weak() is not None))
        if after_snapshot is not None:after_snapshot()
        return dict(iosSnapshotFileWorkVersion=1,requestId=command['commandId'],runId=RUN,instance='b'*32,sequence=self.sequence,
            processId=42,clockDomain='native-main-snapshot-file-work',clockBefore=before,clockAfter=self.clock(),
            source=dict(complete=True,jobs=sorted(rows,key=lambda row:row['id'])))


class SnapshotFileWorkTests(unittest.TestCase):
    def test_actual_cached_functor_keeps_weak_job_alive_after_success_return_and_finally(self):
        native=Jobs();callback,command=native.queued();before=native.read();callback()
        returned=native.read();source.validate(returned,dict(query(),commandId=returned['requestId']),42,previous=before)
        with self.assertRaises(NativeUIError):source.drained(returned,[command])
        held=callback;del callback
        with self.assertRaises(NativeUIError):source.drained(native.read(),[command])
        del held;expired=native.read();source.drained(expired,[command])
        self.assertIsNotNone(expired['source']['jobs'][0]['expiredEpochMs'])

    def test_actual_worker_event_inside_previous_getter_bracket_keeps_original_time(self):
        native=Jobs();callback,command=native.queued();before=native.read(after_snapshot=callback);after=native.read()
        row=after['source']['jobs'][0]
        self.assertLess(row['enteredEpochMs'],before['clockAfter']['epochMs'])
        source.validate(after,dict(query(),commandId=after['requestId']),42,previous=before)
        changed=deepcopy(after);changed['source']['jobs'][0]['enteredEpochMs']=before['clockBefore']['epochMs']-1
        with self.assertRaises(NativeUIError):source.validate(changed,dict(query(),commandId=changed['requestId']),42,previous=before)

    def test_wrong_query_failed_publication_missing_expiry_and_incomplete_source_do_not_drain(self):
        native=Jobs();callback,command=native.queued();callback();del callback;packet=native.read()
        source.drained(packet,[command])
        for fault in ('nonce','publication','expiry','complete','returned','alive'):
            value=deepcopy(packet)
            if fault=='nonce':value['source']['jobs'][0]['query']['commandId']='ios-'+'f'*32
            elif fault=='publication':value['source']['jobs'][0]['publication']=False
            elif fault=='expiry':value['source']['jobs'][0]['expiredEpochMs']=None
            elif fault=='complete':value['source']['complete']=False
            elif fault=='returned':value['source']['jobs'][0]['returnedEpochMs']=None
            else:value['source']['jobs'][0]['alive']=True
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):source.drained(value,[command])

    def test_history_cannot_forget_job_rewrite_original_or_resurrect_weak_capture(self):
        native=Jobs();callback,command=native.queued();callback();del callback;before=native.read();after=native.read()
        for fault in ('forgot','query','birth','publication','resurrect','pid','instance'):
            value=deepcopy(after)
            if fault=='forgot':value['source']['jobs']=[]
            elif fault=='query':value['source']['jobs'][0]['query']['commandId']='ios-'+'f'*32
            elif fault=='birth':value['source']['jobs'][0]['queuedEpochMs']+=1
            elif fault=='publication':value['source']['jobs'][0]['publishedEpochMs']+=1
            elif fault=='resurrect':value['source']['jobs'][0]['alive']=True;value['source']['jobs'][0]['expiredEpochMs']=None
            elif fault=='pid':value['processId']=43
            else:value['instance']='f'*32
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):source.validate(value,dict(query(),commandId=value['requestId']),42,previous=before)

    def test_actual_native_callsite_binds_weak_token_to_queued_functor_not_source_reader(self):
        root=Path(__file__).resolve().parents[4];native=(root/'tests/device/native/IOSSnapshotFileWorkObservation.h').read_text()
        caller=(root/'interface/src/scripting/TestScriptingInterface.cpp').read_text()
        section=caller[caller.index('bool TestScriptingInterface::iosSnapshotFilesRequest'):caller.index('bool TestScriptingInterface::iosTextTest')]
        self.assertIn('std::weak_ptr<Token> actual',native);self.assertIn('nativeFileResponsibility\n#endif\n            ]',section)
        self.assertIn('const QSemaphoreReleaser release',section);self.assertIn('Body originalNativeFileJob(nativeFileResponsibility)',section)
        self.assertIn('publication(nativeFileResponsibility,published)',section)
        self.assertIn('#if defined(OVERTE_E2E_FEATURE_TESTS)',section)


class SnapshotFileWorkTransportTests(unittest.TestCase):
    def test_closed_actual_fixture_never_accepts_expected_job_absence(self):
        fixture=FixtureState();value=query();self.assertEqual(value,fixture.set_client_command(value))
        for edit in ({'jobs':[]},{'expectedPending':0},{'complete':True},{'schemaVersion':True}):
            with self.subTest(edit=edit),self.assertRaises(ValueError):fixture.set_client_command(value|edit)

    def test_actual_node_probe_preserves_original_jobs_and_reads_once_per_nonce(self):
        original=Jobs().read();program='''
const Uuid={generate:()=>"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"};
const objectKeysMatch=(v,keys)=>JSON.stringify(Object.keys(v).sort())===JSON.stringify(keys.sort());
let calls=0,files=[];const original=PACKET;
const Test={featureIOSSnapshotFileWork:q=>{calls++;return {...original,requestId:q.commandId};},saveObject:(v,n)=>files.push({v,n})};
SOURCE
const q=QUERY;applyClientCommand(q);applyClientCommand(q);
applyClientCommand({...q,commandId:"ios-"+"c".repeat(32)});applyClientCommand(q);
if(calls!==2||files.length!==2||files[0].n!=="feature-ios-snapshot-file-work.json")throw Error("job source replay");
if(JSON.stringify(files[0].v.source)!==JSON.stringify(original.source))throw Error("native work rewritten");
delete Test.featureIOSSnapshotFileWork;applyClientCommand({...q,commandId:"ios-"+"d".repeat(32)});
if(files.at(-1).v.status!=="unavailable"||files.at(-1).v.source)throw Error("missing hook forged absence");
'''.replace('PACKET',json.dumps(original)).replace('QUERY',json.dumps(query())).replace('SOURCE',probe_source())
        result=subprocess.run(['node','-e',program],capture_output=True,text=True,timeout=5)
        self.assertEqual(0,result.returncode,result.stderr)

    def test_actual_factory_afc_and_independent_native_clock_keep_original_work(self):
        native=Transport();observer=native.observer();model=Jobs();calls=[];reads=[]
        def post(request,timeout):
            value=native.fixture.set_client_command(json.loads(request.data));calls.append(value);native.echo=json.dumps(value).encode()
            native.value=model.read(value);return native
        def execute(session,operation,arguments):
            self.assertEqual('mobile: pullFile',operation)
            self.assertEqual(dict(remotePath='@org.example.client:documents/owned-results/'+source.FILE),arguments)
            reads.append(arguments);return base64.b64encode(json.dumps(native.value).encode()).decode()
        native.execute=execute;clock=SimpleNamespace(sequence=0,read=lambda _:dict(capturedEpochMs=model.now))
        with patch.object(feature_observation,'post_request',post):value=observer.snapshot_file_work(clock).read(RUN)
        self.assertEqual(native.value,value);self.assertEqual(1,len(calls));self.assertEqual(1,len(reads))


if __name__=='__main__':unittest.main()
