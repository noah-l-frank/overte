"""Canonical candidate/HTTP/AFC paths with independent native Assets models.

Candidate preflight, installed bundle bytes, Qt and AssetClient boundaries are
declared host models. No device, compiler or AssetServer is used.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import json
from adapters.script_feature.lock import ScriptSourceLock
from fixture.serve import FixtureState
from ios.adapters import feature_observation
from ios.adapters.assets_runtime import IOSAssetsRuntime
from ios.self_tests import assets_reply_fixture as replies
from ios.self_tests import test_ios_script_runtime as script
from unittest.mock import patch


class RuntimeBoundary:
    def __init__(self,test):
        self.test=test;self.now=0.;self.asset_requests=[];self.afc=[];self.errors=[];self.observe_error=None;self.after_lost_start=None
        self.fixture=script.IOSScriptRuntimeTests();self.fixture.setUp();test.addCleanup(self.fixture.doCleanups)
        self.f=self.fixture.f;self.root=self.f.root;self.client=self.fixture.client
        self.state=FixtureState();self.file_sequence=0;self.file_packet=None
        test.enterContext(patch.object(replies,'EPOCH',20000));self.replies=replies.Boundary()
        self.original_post=feature_observation.post_request.side_effect
        self.original_execute=self.client.execute;self.client.execute=self.execute
        self.f.clock.mutate=self.native_clock
        test.enterContext(patch.object(feature_observation,'post_request',side_effect=self.post))
        self.runtime=IOSAssetsRuntime(self.f.adapter,monotonic=lambda:self.now)
        self.lock=ScriptSourceLock(self.root/'script-feature-sources.lock')
        context=self.lock.held();context.__enter__();test.addCleanup(context.__exit__,None,None,None)

    def native_clock(self,value):
        # Produce a fresh independent clock packet at the current model time.
        # Existing packets are never edited or retimed.
        def clock_fields(node):
            if type(node) is dict:
                for key,child in node.items():
                    if key.endswith('EpochMs'):node[key]=self.replies.clock()
                    else:clock_fields(child)
            elif type(node) is list:
                for child in node:clock_fields(child)
        clock_fields(value);value['processId']=42

    def files(self,query):
        self.test.assertEqual('observe',query['operation']);self.file_sequence+=1
        before=self.replies.stamp();self.replies.tick();at=self.replies.clock()
        ui=dict(iosAssetUiInventoryVersion=1,available=True,complete=True,instance='11111111-1111-4111-8111-111111111111',
            sequence=self.file_sequence,capturedEpochMs=at,processId=42,roots=[])
        work=dict(iosAssetUploadWorkVersion=1,available=True,complete=True,instance='22222222-2222-4222-8222-222222222222',
            sequence=self.file_sequence,processId=42,clock=self.replies.stamp(),jobs=[])
        self.replies.tick();self.file_packet=dict(iosAssetsFilesVersion=1,requestId=query['commandId'],runId=query['runId'],
            instance='f'*32,sequence=self.file_sequence,processId=42,clockDomain='native-main-assets-files',
            clockBefore=before,clockAfter=self.replies.stamp(),source=dict(files=dict(exists=False,files=[]),ui=ui,work=work))

    def post(self,request,timeout):
        query=json.loads(request.data)
        if query['action'] not in ('feature-ios-assets-files','feature-ios-assets-replies'):
            return self.original_post(request,timeout)
        self.test.assertEqual(5,timeout);self.state.set_client_command(query);self.asset_requests.append(deepcopy(query))
        try:
            if query['action']=='feature-ios-assets-files':self.files(query)
            else:
                if query['operation']=='observe' and self.observe_error is not None:raise self.observe_error
                self.replies.send(query)
        except BaseException as error:
            self.errors.append(error)
            if query['operation']=='inventory' and self.after_lost_start:self.after_lost_start()
            raise
        raw=json.dumps(query).encode()
        class Response:
            status=200
            def __enter__(self):return self
            def __exit__(self,*args):return False
            def read(self,limit):return raw[:limit]
        return Response()

    def execute(self,session,operation,values):
        if operation=='mobile: pullFile':
            path=values['remotePath']
            if path.endswith('/feature-ios-assets-files.json'):
                self.afc.append(path);return base64.b64encode(json.dumps(self.file_packet).encode()).decode()
            if path.endswith('/feature-ios-assets-replies.json'):
                self.afc.append(path);return base64.b64encode(self.replies.original().encode()).decode()
        return self.original_execute(session,operation,values)

    def components(self):return self.runtime._assets_components('test-only',replies.RUN,'primary',replies.URL,self.lock)
    def readback(self):return self.runtime._assets_readback('test-only',replies.RUN,'primary',replies.URL,replies.TICKET,self.lock)
