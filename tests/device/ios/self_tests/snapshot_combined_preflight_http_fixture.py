"""Independent Combined HTTP producer; actual protected serializer bytes.

The Qt/V8/XHR boundary is declared, not native execution. This constructor
never creates or converts a Separate1 HTTP original. Backend/HTTP bytes and
repository UTF-16 module bytes retain their independent original domains.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
from unittest.mock import patch
from feature_journeys.server import Handler
from feature_journeys.snapshot_concurrency import SnapshotConcurrency
from ios.self_tests.snapshot_upload_backend_domain import SnapshotBackendDomain,RUN
from ios.self_tests.snapshot_preflight_http_fixture import SnapshotPreflightHttpBoundary,wire,EPOCH
from ios.self_tests.snapshot_combined_work_fixture import packet,caller
from self_tests.snapshot_domain_fixture import PolicyFixture
from self_tests.test_snapshot_concurrency import actual_query


class CombinedPreflightHttpBoundary(SnapshotPreflightHttpBoundary):
    def __init__(self,case,epoch=EPOCH,*,anonymous=True,logged_in=True):
        self.epoch,self.time,self.sequence=epoch,1000,0;self.queries=[];self.raw='';self.mutate=None
        self.backend=SnapshotBackendDomain();self.policy=PolicyFixture(case);self.policy.policy(anonymous,logged_in)
        self.backend.provider.concurrency=SnapshotConcurrency(self.backend.provider,self.policy.client())
        original_send=Handler.send;responses=[]
        def serialized(handler,*args,**kwargs):
            result=original_send(handler,*args,**kwargs);responses.append(handler.wfile.getvalue());return result
        with patch.object(Handler,'send',serialized):status,body=self.backend.call('GET','/api/v1/user_stories?'+actual_query())
        header,actual_body=responses[-1].split(b'\r\n\r\n',1);assert status==200 and body==actual_body
        identities=[row.split(b':',1)[1].strip().decode() for row in header.split(b'\r\n') if row.lower().startswith(b'x-overte-fixture-response:')]
        assert len(identities)==1
        model=packet(epoch)['source']['workers'][0]
        stack,modules=caller(('modules/request.js','system/snapshot.js','defaultScripts.js'),epoch)
        read_stack,read_modules=caller(('modules/request.js',),epoch)
        self.xhr,self.reply='7'*32,'8'*32
        self.value=dict(iosSnapshotCombinedPreflightHttpVersion=1,requestId='ios-'+'5'*32,runId=RUN,instance='6'*32,sequence=1,processId=42,
            clockDomain='native-process-snapshot-combined-preflight-http',clockBefore=dict(epochMs=epoch+1000,monotonicMs=1000),
            clockAfter=dict(epochMs=epoch+1001,monotonicMs=1001),events=[],callerStacks=[
                dict(id='a3'*16,callerStack=stack,callerModules=modules),dict(id='a4'*16,callerStack=read_stack,callerModules=read_modules)])
        created=dict(callerStackId='a3'*16,engine=deepcopy(model['manager']),submitted=deepcopy(model['code']),
            codeSources=deepcopy(model['codeSources']),requestUrl='https://controlled.invalid/api/v1/user_stories?'+actual_query(),
            method='GET',protocolSignature=base64.b64encode(b'p'*16).decode())
        self.add('created',created);self.add('callback-enter',dict(callback='readystatechange',readyState=1));self.add('callback-leave',dict(callback='readystatechange',readyState=1))
        self.add('sent',dict(replyId=self.reply,url=created['requestUrl'],method='GET',body=wire(b''),authorizationAttached=True,contentType=''))
        self.add('timer-state',dict(active=False));self.add('reply-finished',dict(replyId=self.reply,httpStatus=status,networkError=0,responseId=identities[0],body=wire(actual_body)))
        self.add('callback-enter',dict(callback='readystatechange',readyState=4))
        self.add('text-read',dict(replyId=self.reply,scriptSource='qrc:/scripts/modules/request.js',sha256=wire(actual_body)['sha256'],callerStackId='a4'*16))
        self.add('callback-leave',dict(callback='readystatechange',readyState=4))
