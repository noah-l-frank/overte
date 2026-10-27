"""Actual probe/fixture/HTTP/AFC codec routes with declared native producers.

No renderer, compiler, device, server or newly launched app is exercised.
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
from ios.adapters import assets_model_renderers as source,feature_observation
from ios.self_tests import test_ios_create_state as create,test_ios_keyboard_runtime as keyboard
from ios.self_tests.test_ios_assets_model_renderers import packet
from self_tests.test_native_feature_observation import probe_source


class Boundary:
    def __init__(self,epoch=20000):
        self.epoch,self.time,self.sequence=epoch,20,0;self.raw='';self.queries=[];self.mutate=None
        # Instantiate a new modeled inventory before acquisition, in this
        # producer's native clock domain. No retained packet is retimed.
        with patch.object(create,'EPOCH',epoch):self.template=packet()
    def stamp(self):self.time+=1;return dict(epochMs=self.epoch+self.time,monotonicMs=self.time)
    def send(self,query):
        self.queries.append(deepcopy(query));self.sequence+=1;value=deepcopy(self.template)
        value.update(requestId=query['commandId'],runId=query['runId'],sequence=self.sequence,clockBefore=self.stamp(),clockAfter=self.stamp())
        if self.mutate:self.mutate(value)
        self.raw=json.dumps(value)


class AssetsModelRenderersProbeTests(unittest.TestCase):
    def test_closed_actual_getter_nonce_and_missing_or_throwing_getter_never_invent_bounds(self):
        b=Boundary();query=dict(schemaVersion=1,commandId='ios-'+'a'*32,action=source.ACTION,runId=create.RUN);b.send(query)
        self.assertEqual(query,FixtureState().set_client_command(query))
        for key,value in (('entityId',create.ID),('bounds',{}),('url','wanted')):
            with self.subTest(key=key),self.assertRaises(ValueError):FixtureState().set_client_command(dict(query,**{key:value}))
        program='''const Uuid={generate:()=>"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"};
const objectKeysMatch=(v,k)=>JSON.stringify(Object.keys(v).sort())===JSON.stringify(k.sort());
const original=PACKET;let calls=0,files=[];
const Test={featureIOSAssetsModelRenderers:q=>{calls++;return {...original,requestId:q.commandId};},saveObject:(v,f)=>files.push({v,f})};
SOURCE
const q=QUERY;applyClientCommand(q);applyClientCommand(q);
if(calls!==1||files.length!==1||files[0].f!=="feature-ios-assets-model-renderers.json"||JSON.stringify(files[0].v.source)!==JSON.stringify(original.source))throw Error("changed/replayed mesh original");
applyClientCommand({...q,commandId:"ios-"+"c".repeat(32),entityId:"wanted"});if(calls!==1)throw Error("wanted subject accepted");
delete Test.featureIOSAssetsModelRenderers;applyClientCommand({...q,commandId:"ios-"+"d".repeat(32)});
if(files.at(-1).v.status!=="unavailable"||files.at(-1).v.source)throw Error("missing getter became empty mesh");
Test.featureIOSAssetsModelRenderers=()=>{calls++;throw Error("original getter failure")};
const failed={...q,commandId:"ios-"+"e".repeat(32)};applyClientCommand(failed);applyClientCommand(failed);
if(calls!==2||files.length!==3||files.at(-1).v.status!=="unavailable"||files.at(-1).v.source)throw Error("failed getter retried/invented");
'''.replace('PACKET',b.raw).replace('QUERY',json.dumps(query)).replace('SOURCE',probe_source())
        result=subprocess.run(['node','-'],input=program,capture_output=True,text=True,timeout=5)
        self.assertEqual(0,result.returncode,result.stderr)


class AssetsModelRenderersRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.k=keyboard.KeyboardRuntimeTests();self.k.setUp();self.addCleanup(self.k.doCleanups);self.f=self.k.f
        self.b=Boundary();self.afc=[]
        def native_clock(value):self.k.b.time=self.b.time;self.k.native_clock(value)
        self.f.clock.mutate=native_clock
        def post(request,timeout):
            query=json.loads(request.data)
            if query['action']!=source.ACTION:return self.k.post(request,timeout)
            FixtureState().set_client_command(query);self.b.send(query);raw=json.dumps(query).encode()
            class Response:
                status=200
                def __enter__(self):return self
                def __exit__(self,*args):return False
                def read(self,limit):return raw[:limit]
            return Response()
        self.enterContext(patch.object(feature_observation,'post_request',side_effect=post));execute=self.k.client.execute
        def read(session,operation,values):
            if operation=='mobile: pullFile' and values['remotePath'].endswith('/'+source.FILE):
                self.afc.append(values['remotePath']);return base64.b64encode(self.b.raw.encode()).decode()
            return execute(session,operation,values)
        self.k.client.execute=read;self.sources=self.k.fixture.runtime._sources('test-only')
    def reader(self):return self.sources['observer'].assets_model_renderers(clock_source=self.sources['clock_source'])
    def test_canonical_factory_reads_actual_inventory_on_original_clock_without_session_or_launch(self):
        before=self.f.sessions,self.f.launches;reader=self.reader();value=reader.read(create.RUN)
        self.assertEqual([7,19],source.model(value,create.ID)['renderItemIds']);self.assertEqual(1,len(self.afc));self.assertEqual(1,len(self.b.queries))
        self.assertEqual(before,(self.f.sessions,self.f.launches));self.assertLess(value['clockAfter']['epochMs'],100000)
        self.assertEqual(1,reader.acquisition['iosAssetsModelRenderersAcquisitionVersion']);self.assertFalse(value['source']['renderedPixelsAvailable'])
    def test_replaced_actual_candidate_refuses_before_source_dispatch_and_afc(self):
        reader=self.reader();self.f.artifact.write_bytes(b'replaced independently pinned candidate')
        with self.assertRaises(NativeUIError):reader.read(create.RUN)
        self.assertEqual([],self.b.queries);self.assertEqual([],self.afc)
    def test_process_replacement_or_foreground_loss_cannot_reuse_original_reader(self):
        for change in (dict(pid=43),dict(foreground=False)):
            old=deepcopy(self.f.process);reader=self.reader();self.f.process.update(change)
            with self.subTest(change=change),self.assertRaises(NativeUIError):reader.read(create.RUN)
            self.f.process=old;self.assertEqual([],self.b.queries);self.assertEqual([],self.afc)
    def test_wrong_pid_or_oversized_actual_afc_body_is_unavailable_without_second_dispatch(self):
        self.b.mutate=lambda value:value.update(processId=43)
        with self.assertRaises(NativeUIError):self.reader().read(create.RUN)
        self.assertEqual(1,len(self.b.queries));self.assertEqual(1,len(self.afc))
        self.b.mutate=lambda value:value['source']['models'][0].update(unexpected='x'*(source.LIMIT+1))
        with self.assertRaises(NativeUIError):self.reader().read(create.RUN)
        self.assertEqual(2,len(self.b.queries));self.assertEqual(2,len(self.afc))
