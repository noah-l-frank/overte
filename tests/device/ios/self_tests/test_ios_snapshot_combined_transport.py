"""Fixed combined source route through existing probe and bound HTTP/AFC."""
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
from ios.adapters import feature_observation,snapshot_combined_work as source
from ios.self_tests.snapshot_combined_work_fixture import Boundary,RUN,URL
from ios.self_tests.test_ios_keyboard_runtime import KeyboardRuntimeTests
from self_tests.test_native_feature_observation import probe_source


class SnapshotCombinedProbeTests(unittest.TestCase):
    def test_fixed_actual_probe_passes_original_once_and_keeps_missing_source_unknown(self):
        boundary=Boundary();query=dict(schemaVersion=1,commandId='ios-'+'a'*32,action=source.ACTION,runId=RUN);boundary.send(query)
        self.assertEqual(query,FixtureState().set_client_command(query))
        for extra in (dict(combined=True),dict(manager='wanted'),dict(quiet=True),dict(profile='default')):
            with self.subTest(extra=extra),self.assertRaises(ValueError):FixtureState().set_client_command(dict(query,**extra))
        program='''const Uuid={generate:()=>"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"};
const objectKeysMatch=(v,k)=>JSON.stringify(Object.keys(v).sort())===JSON.stringify(k.sort());
const original=PACKET;let calls=0,files=[];
const Test={featureIOSSnapshotCombinedWork:q=>{calls++;return {...original,requestId:q.commandId};},saveObject:(v,f)=>files.push({v,f})};
SOURCE
const q=QUERY;applyClientCommand(q);applyClientCommand(q);
if(calls!==1||files.length!==1||files[0].f!=="feature-ios-snapshot-combined-work.json"||JSON.stringify(files[0].v.source)!==JSON.stringify(original.source))throw Error("source changed/replayed");
applyClientCommand({...q,commandId:"ios-"+"b".repeat(32),combined:true});if(calls!==1)throw Error("wanted manager profile accepted");
delete Test.featureIOSSnapshotCombinedWork;applyClientCommand({...q,commandId:"ios-"+"c".repeat(32)});
if(files.at(-1).v.status!=="unavailable"||files.at(-1).v.source)throw Error("missing original became quiet");
Test.featureIOSSnapshotCombinedWork=()=>{calls++;throw Error("declared original failure")};
const failed={...q,commandId:"ios-"+"d".repeat(32)};applyClientCommand(failed);applyClientCommand(failed);
if(calls!==2||files.length!==3||files.at(-1).v.status!=="unavailable")throw Error("failed query repeated");
'''.replace('PACKET',boundary.raw).replace('QUERY',json.dumps(query)).replace('SOURCE',probe_source())
        result=subprocess.run(['node','-'],input=program,capture_output=True,text=True,timeout=5);self.assertEqual(0,result.returncode,result.stderr)


class SnapshotCombinedRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.k=KeyboardRuntimeTests();self.k.setUp();self.addCleanup(self.k.doCleanups);self.f=self.k.f;self.boundary=Boundary();self.afc=[]
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
    def reader(self):return self.sources['observer'].snapshot_combined_work(clock_source=self.sources['clock_source'])
    def test_existing_factory_observes_real_default_manager_model_without_new_session_or_launch(self):
        before=self.f.sessions,self.f.launches;reader=self.reader();value=reader.read(RUN)
        self.assertEqual(URL+'defaultScripts.js',source.admit(value,URL,quiet=True)['manager']['url']);self.assertEqual(before,(self.f.sessions,self.f.launches))
        self.assertEqual((1,1),(len(self.boundary.queries),len(self.afc)));self.assertEqual(1,reader.acquisition['iosSnapshotCombinedWorkAcquisitionVersion'])
        self.assertGreaterEqual(value['clockBefore']['epochMs'],reader.acquisition['nativeRequestedEpochMs'])
    def test_foreign_candidate_or_actual_process_cannot_reuse_bound_original_reader(self):
        for update in (dict(pid=43),dict(foreground=False)):
            old=deepcopy(self.f.process);reader=self.reader();self.f.process.update(update)
            with self.subTest(update=update),self.assertRaises(NativeUIError):reader.read(RUN)
            self.f.process=old;self.assertEqual([],self.afc);self.assertEqual([],self.boundary.queries)
        reader=self.reader();self.f.artifact.write_bytes(b'foreign candidate bytes')
        with self.assertRaises(NativeUIError):reader.read(RUN)
        self.assertEqual([],self.afc);self.assertEqual([],self.boundary.queries)
    def test_wrong_pid_and_oversized_original_fail_without_resending_query(self):
        self.boundary.mutate=lambda value:value.update(processId=43)
        with self.assertRaises(NativeUIError):self.reader().read(RUN)
        self.assertEqual((1,1),(len(self.boundary.queries),len(self.afc)))
        self.boundary.mutate=lambda value:value['source']['workers'][0].update(unexpected='x'*(source.LIMIT+1))
        with self.assertRaises(NativeUIError):self.reader().read(RUN)
        self.assertEqual((2,2),(len(self.boundary.queries),len(self.afc)))


if __name__=='__main__':unittest.main()
