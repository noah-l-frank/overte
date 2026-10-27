"""Actual closed probe/fixture/HTTP/AFC entrypoints over declared native DTOs."""
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
from ios.adapters import feature_observation,snapshot_preflight_http as source
from ios.self_tests.snapshot_preflight_http_fixture import SnapshotPreflightHttpBoundary,RUN
from ios.self_tests.test_ios_keyboard_runtime import KeyboardRuntimeTests
from self_tests.test_native_feature_observation import probe_source


class SnapshotPreflightHttpProbeTests(unittest.TestCase):
    def test_actual_getter_preserves_original_and_consumes_nonce_once_even_on_failure(self):
        boundary=SnapshotPreflightHttpBoundary(self);query=dict(schemaVersion=1,commandId='ios-'+'a'*32,action=source.ACTION,runId=RUN);boundary.send(query)
        self.assertEqual(query,FixtureState().set_client_command(query))
        for extra in (dict(canShare=True),dict(url='https://wanted.invalid'),dict(pid=42),dict(responseId='0'*32)):
            with self.subTest(extra=extra),self.assertRaises(ValueError):FixtureState().set_client_command(dict(query,**extra))
        program='''const Uuid={generate:()=>"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"};
const objectKeysMatch=(v,k)=>JSON.stringify(Object.keys(v).sort())===JSON.stringify(k.sort());
const original=PACKET;let calls=0,files=[];
const Test={featureIOSSnapshotPreflightHttp:q=>{calls++;return {...original,requestId:q.commandId};},saveObject:(v,f)=>files.push({v,f})};
SOURCE
const q=QUERY;applyClientCommand(q);applyClientCommand(q);
if(calls!==1||files.length!==1||files[0].f!=="feature-ios-snapshot-preflight-http.json"||JSON.stringify(files[0].v.events)!==JSON.stringify(original.events))throw Error("original changed or queried twice");
applyClientCommand({...q,commandId:"ios-"+"b".repeat(32),canShare:true});if(calls!==1)throw Error("requested sharing accepted");
delete Test.featureIOSSnapshotPreflightHttp;applyClientCommand({...q,commandId:"ios-"+"c".repeat(32)});
if(files.at(-1).v.status!=="unavailable"||files.at(-1).v.events)throw Error("missing source became empty/quiet");
Test.featureIOSSnapshotPreflightHttp=()=>{calls++;throw Error("declared native getter failure")};
const failed={...q,commandId:"ios-"+"d".repeat(32)};applyClientCommand(failed);applyClientCommand(failed);
if(calls!==2||files.length!==3||files.at(-1).v.status!=="unavailable")throw Error("uncertain read repeated or qualified");
'''.replace('PACKET',boundary.raw).replace('QUERY',json.dumps(query)).replace('SOURCE',probe_source())
        result=subprocess.run(['node','-'],input=program,capture_output=True,text=True,timeout=5);self.assertEqual(0,result.returncode,result.stderr)


class SnapshotPreflightHttpRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.k=KeyboardRuntimeTests();self.k.setUp();self.addCleanup(self.k.doCleanups);self.f=self.k.f
        self.boundary=SnapshotPreflightHttpBoundary(self,epoch=20000);self.afc=[]
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
    def reader(self):return self.sources['observer'].snapshot_preflight_http(clock_source=self.sources['clock_source'])
    def test_existing_bound_factory_reads_original_on_independent_native_clock_without_launch(self):
        before=self.f.sessions,self.f.launches;reader=self.reader();value=reader.read(RUN)
        self.assertEqual(1,len(source.response_reads(value)));self.assertEqual(before,(self.f.sessions,self.f.launches));self.assertEqual(1,len(self.afc));self.assertEqual(1,len(self.boundary.queries))
        self.assertEqual(1,reader.acquisition['iosSnapshotPreflightHttpAcquisitionVersion']);self.assertLess(value['clockAfter']['epochMs'],100000)
        self.assertGreaterEqual(value['clockBefore']['epochMs'],reader.acquisition['nativeRequestedEpochMs'])
    def test_foreign_candidate_process_and_foreground_refuse_before_dispatch_or_afc(self):
        for update in (dict(pid=43),dict(foreground=False)):
            before=deepcopy(self.f.process);reader=self.reader();self.f.process.update(update)
            with self.subTest(update=update),self.assertRaises(NativeUIError):reader.read(RUN)
            self.f.process=before;self.assertEqual([],self.boundary.queries);self.assertEqual([],self.afc)
        reader=self.reader();self.f.artifact.write_bytes(b'foreign candidate after independent admission')
        with self.assertRaises(NativeUIError):reader.read(RUN)
        self.assertEqual([],self.boundary.queries);self.assertEqual([],self.afc)
    def test_wrong_actual_pid_and_oversized_original_remain_unavailable_without_second_dispatch(self):
        self.boundary.mutate=lambda value:value.update(processId=43)
        with self.assertRaises(NativeUIError):self.reader().read(RUN)
        self.assertEqual((1,1),(len(self.boundary.queries),len(self.afc)))
        self.boundary.mutate=lambda value:value['events'][0]['details'].update(unexpected='x'*(source.LIMIT+1))
        with self.assertRaises(NativeUIError):self.reader().read(RUN)
        self.assertEqual((2,2),(len(self.boundary.queries),len(self.afc)))


if __name__=='__main__':unittest.main()
