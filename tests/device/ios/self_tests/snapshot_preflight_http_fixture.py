"""Explicit Qt/V8 producer; actual account/policy/HTTP serializer bytes.

No native runtime is executed. Compiled-frame identities are declared host
boundaries using independently read actual repository UTF-16 module bytes.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from unittest.mock import patch
from feature_journeys.server import Handler
from feature_journeys.snapshot_concurrency import SnapshotConcurrency
from ios.self_tests.snapshot_upload_backend_domain import SnapshotBackendDomain,RUN
from self_tests.snapshot_domain_fixture import PolicyFixture
from self_tests.test_snapshot_concurrency import actual_query

ROOT=Path(__file__).resolve().parents[4]
EPOCH=1700000000000


def wire(raw):return dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),contentBase64=base64.b64encode(raw).decode())


def callers(suffixes,epoch):
    frames=[];modules=[];code=[]
    for index,suffix in enumerate(suffixes):
        raw=(ROOT/'scripts'/suffix[1:]).read_text().encode('utf-16-le');url='qrc:/scripts'+suffix;url_sha=hashlib.sha256(url.encode()).hexdigest()
        code.append(dict(sequence=index+1,url=url,submittedEpochMs=epoch-100,encoding='utf-16le-code-units',codeUnits=len(raw)//2,sha256=hashlib.sha256(raw).hexdigest()))
        frames.append(dict(scriptId=1 if suffix=='/modules/request.js' else 2,line=78,column=1,sourceUrlSha256=url_sha,
            compiled=dict(urlSha256=url_sha,encoding=code[-1]['encoding'],codeUnits=code[-1]['codeUnits'],sha256=code[-1]['sha256'],firstObservedEpochMs=epoch-50),isEval=False,isConstructor=False))
        modules.append(dict(frame=index,url=url))
    return dict(emitStackVersion=1,instance='a'*32,complete=True,frames=frames),modules,code


class SnapshotPreflightHttpBoundary:
    def __init__(self,case,epoch=EPOCH,*,anonymous=True,logged_in=True):
        self.epoch,self.time,self.sequence=epoch,1000,0;self.queries=[];self.raw='';self.mutate=None
        self.backend=SnapshotBackendDomain();self.policy=PolicyFixture(case)
        self.policy.policy(anonymous,logged_in)
        self.backend.provider.concurrency=SnapshotConcurrency(self.backend.provider,self.policy.client())
        original_send=Handler.send;responses=[]
        def serialized(handler,*args,**kwargs):
            result=original_send(handler,*args,**kwargs);responses.append(handler.wfile.getvalue());return result
        with patch.object(Handler,'send',serialized):status,body=self.backend.call('GET','/api/v1/user_stories?'+actual_query())
        header,actual_body=responses[-1].split(b'\r\n\r\n',1);assert status==200 and body==actual_body
        identities=[row.split(b':',1)[1].strip().decode() for row in header.split(b'\r\n') if row.lower().startswith(b'x-overte-fixture-response:')];assert len(identities)==1
        stack,modules,code=callers(('/modules/request.js','/system/snapshot.js'),epoch)
        read_stack,read_modules,_read_code=callers(('/modules/request.js',),epoch)
        main=(ROOT/'scripts/system/snapshot.js').read_text().encode('utf-16-le')
        self.xhr,self.reply='7'*32,'8'*32
        self.value=dict(iosSnapshotPreflightHttpVersion=1,requestId='ios-'+'5'*32,runId=RUN,instance='6'*32,sequence=1,processId=42,
            clockDomain='native-process-snapshot-preflight-http',clockBefore=dict(epochMs=epoch+1000,monotonicMs=1000),clockAfter=dict(epochMs=epoch+1001,monotonicMs=1001),events=[],
            callerStacks=[dict(id='a3'*16,callerStack=stack,callerModules=modules),dict(id='a4'*16,callerStack=read_stack,callerModules=read_modules)])
        created=dict(callerStackId='a3'*16,engine=dict(instance='b'*32,assigned=True,url='qrc:/scripts/system/snapshot.js',loadGeneration=1,assignedEpochMs=epoch-120),
            submitted=dict(submitted=True,encoding='utf-16le-code-units',codeUnits=len(main)//2,sha256=hashlib.sha256(main).hexdigest(),submittedEpochMs=epoch-110),
            codeSources=dict(snapshotHttpSourcesVersion=1,complete=True,evaluations=code),requestUrl='https://controlled.invalid/api/v1/user_stories?'+actual_query(),method='GET',protocolSignature=base64.b64encode(b'p'*16).decode())
        self.add('created',created);self.add('callback-enter',dict(callback='readystatechange',readyState=1));self.add('callback-leave',dict(callback='readystatechange',readyState=1))
        self.add('sent',dict(replyId=self.reply,url=created['requestUrl'],method='GET',body=wire(b''),authorizationAttached=True,contentType=''))
        self.add('timer-state',dict(active=False));self.add('reply-finished',dict(replyId=self.reply,httpStatus=status,networkError=0,responseId=identities[0],body=wire(actual_body)))
        self.add('callback-enter',dict(callback='readystatechange',readyState=4));self.add('text-read',dict(replyId=self.reply,scriptSource='qrc:/scripts/modules/request.js',sha256=wire(actual_body)['sha256'],callerStackId='a4'*16))
        self.add('callback-leave',dict(callback='readystatechange',readyState=4))
    def add(self,kind,details=None):
        index=len(self.value['events'])+1
        self.value['events'].append(dict(sequence=index,eventId=f'{index:032x}',xhrId=self.xhr,kind=kind,clock=dict(epochMs=self.epoch+index,monotonicMs=index),details={} if details is None else details))
    def send(self,query):
        self.queries.append(deepcopy(query));self.sequence+=1;value=deepcopy(self.value);self.time+=1
        value.update(requestId=query['commandId'],runId=query['runId'],sequence=self.sequence,clockBefore=dict(epochMs=self.epoch+self.time,monotonicMs=self.time))
        self.time+=1;value['clockAfter']=dict(epochMs=self.epoch+self.time,monotonicMs=self.time)
        if self.mutate:self.mutate(value)
        self.raw=json.dumps(value)
