"""Fixed getter/probe/HTTP/AFC causal source, using a fresh empty native model.

An empty ledger is only an original fact. No branch, upload or cleanup result
is inferred from it. Node executes the actual once-only production probe.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import json
import subprocess
import unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from fixture.serve import FixtureState
from ios.adapters import feature_observation,snapshot_causal_dispatch as source
from ios.self_tests.test_ios_keyboard_runtime import KeyboardRuntimeTests
from self_tests.test_native_feature_observation import probe_source

RUN='a'*32


class CausalSourceBoundary:
    def __init__(self):self.time=1000;self.sequence=0;self.queries=[];self.raw='';self.mutate=None
    def send(self,query):
        self.queries.append(deepcopy(query));self.time+=1;before=dict(epochMs=20000+self.time,monotonicMs=self.time)
        self.time+=1;self.sequence+=1
        value=dict(iosSnapshotCausalDispatchVersion=1,requestId=query['commandId'],runId=query['runId'],instance='6'*32,
            sequence=self.sequence,processId=42,clockDomain='native-process-snapshot-causal-dispatch',clockBefore=before,
            clockAfter=dict(epochMs=20000+self.time,monotonicMs=self.time),source=dict(complete=True,calls=[]))
        if self.mutate:self.mutate(value)
        self.raw=json.dumps(value)


class SnapshotCausalProbeTests(unittest.TestCase):
    def test_actual_fixed_probe_consumes_success_unavailable_and_throwing_nonce_once(self):
        boundary=CausalSourceBoundary();query=dict(schemaVersion=1,commandId='ios-'+'a'*32,action=source.ACTION,runId=RUN);boundary.send(query)
        self.assertEqual(query,FixtureState().set_client_command(query))
        for extra in (dict(caller={}),dict(upload='b'*32),dict(pid=42),dict(stage='window'),dict(file='wanted.png')):
            with self.subTest(extra=extra),self.assertRaises(ValueError):FixtureState().set_client_command(dict(query,**extra))
        program='''const Uuid={generate:()=>"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"};
const objectKeysMatch=(v,k)=>JSON.stringify(Object.keys(v).sort())===JSON.stringify(k.sort());
const original=PACKET;let calls=0,files=[];
const Test={featureIOSSnapshotCausalDispatch:q=>{calls++;return {...original,requestId:q.commandId};},saveObject:(v,f)=>files.push({v,f})};
SOURCE
const q=QUERY;applyClientCommand(q);applyClientCommand(q);
if(calls!==1||files.length!==1||files[0].f!=="feature-ios-snapshot-causal-dispatch.json"||JSON.stringify(files[0].v.source)!==JSON.stringify(original.source))throw Error("original changed or queried twice");
applyClientCommand({...q,commandId:"ios-"+"b".repeat(32),caller:{}});if(calls!==1)throw Error("requested caller accepted");
delete Test.featureIOSSnapshotCausalDispatch;applyClientCommand({...q,commandId:"ios-"+"c".repeat(32)});
if(files.at(-1).v.status!=="unavailable"||files.at(-1).v.source)throw Error("missing source became quiet");
Test.featureIOSSnapshotCausalDispatch=()=>{calls++;throw Error("native getter unavailable")};
const failed={...q,commandId:"ios-"+"d".repeat(32)};applyClientCommand(failed);applyClientCommand(failed);
if(calls!==2||files.length!==3||files.at(-1).v.status!=="unavailable")throw Error("uncertain read repeated");
'''.replace('PACKET',boundary.raw).replace('QUERY',json.dumps(query)).replace('SOURCE',probe_source())
        result=subprocess.run(['node','-'],input=program,capture_output=True,text=True,timeout=5)
        self.assertEqual(0,result.returncode,result.stderr)


class SnapshotCausalRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.k=KeyboardRuntimeTests();self.k.setUp();self.addCleanup(self.k.doCleanups);self.f=self.k.f
        self.boundary=CausalSourceBoundary();self.afc=[]
        def clock(value):self.k.b.time=self.boundary.time;self.k.native_clock(value)
        self.f.clock.mutate=clock
        def post(request,timeout):
            query=json.loads(request.data)
            if query['action']!=source.ACTION:return self.k.post(request,timeout)
            FixtureState().set_client_command(query);self.boundary.send(query);raw=json.dumps(query).encode()
            class Response:
                status=200
                def __enter__(self):return self
                def __exit__(self,*args):return False
                def read(self,limit):return raw[:limit]
            return Response()
        self.enterContext(patch.object(feature_observation,'post_request',side_effect=post));execute=self.k.client.execute
        def read(session,operation,values):
            if operation=='mobile: pullFile' and values['remotePath'].endswith('/'+source.FILE):
                self.afc.append(values['remotePath']);return base64.b64encode(self.boundary.raw.encode()).decode()
            return execute(session,operation,values)
        self.k.client.execute=read;self.sources=self.k.fixture.runtime._sources('test-only')
    def reader(self):return self.sources['observer'].snapshot_causal_dispatch(clock_source=self.sources['clock_source'])
    def test_bound_factory_reads_only_actual_original_without_launch_and_preserves_clock_domain(self):
        before=self.f.sessions,self.f.launches;reader=self.reader();value=reader.read(RUN)
        self.assertEqual([],value['source']['calls']);self.assertEqual(before,(self.f.sessions,self.f.launches))
        self.assertEqual((1,1),(len(self.afc),len(self.boundary.queries)))
        self.assertEqual(1,reader.acquisition['iosSnapshotCausalDispatchAcquisitionVersion'])
        self.assertGreaterEqual(value['clockBefore']['epochMs'],reader.acquisition['nativeRequestedEpochMs'])
    def test_foreign_candidate_pid_and_foreground_refuse_before_source_dispatch(self):
        for update in (dict(pid=43),dict(foreground=False)):
            before=deepcopy(self.f.process);reader=self.reader();self.f.process.update(update)
            with self.subTest(update=update),self.assertRaises(NativeUIError):reader.read(RUN)
            self.f.process=before;self.assertEqual([],self.boundary.queries);self.assertEqual([],self.afc)
        reader=self.reader();self.f.artifact.write_bytes(b'changed actual candidate')
        with self.assertRaises(NativeUIError):reader.read(RUN)
        self.assertEqual([],self.boundary.queries);self.assertEqual([],self.afc)
    def test_actual_foreign_or_oversized_reply_does_not_repeat_original_query(self):
        self.boundary.mutate=lambda value:value.update(processId=43)
        with self.assertRaises(NativeUIError):self.reader().read(RUN)
        self.assertEqual((1,1),(len(self.boundary.queries),len(self.afc)))
        self.boundary.mutate=lambda value:value['source'].update(unknown='x'*(source.LIMIT+1))
        with self.assertRaises(NativeUIError):self.reader().read(RUN)
        self.assertEqual((2,2),(len(self.boundary.queries),len(self.afc)))


if __name__=='__main__':unittest.main()
