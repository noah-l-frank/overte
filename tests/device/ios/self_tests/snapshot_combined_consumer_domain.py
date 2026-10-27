"""Actual request.js response GET and protected bytes on normal Combined input.

The Qt/V8/native boundaries are models, built at their actual host Script/HTTP
events before persistence. The model weak objects are real Python lifetimes;
their destruction does not qualify Qt garbage collection or installed V8.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import hashlib
import json
from unittest.mock import patch
import uuid
import weakref
from adapters.native_feature_observation import need
from adapters.normal_ui import NativeUIError
from feature_journeys.server import Handler
from ios.adapters import snapshot_combined_preflight_http as http
from ios.adapters.snapshot_upload_backend_owner import backend_context
from ios.self_tests.snapshot_combined_backend_domain import CombinedBackendDomain
from ios.self_tests.snapshot_combined_work_fixture import caller,packet
from ios.self_tests.snapshot_preflight_http_fixture import wire
from ios.self_tests.snapshot_upload_script_domain import OriginalUploadScript
from ios.self_tests.snapshot_pending_domain import REAL_TIME,REAL_MONOTONIC
from ios.self_tests.snapshot_upload_flow_domain import RUN,BASE


class WeakObject:pass


class ConsumerBoundary:
    def __init__(self,domain):
        self.domain=domain;self.instance=uuid.uuid4().hex;self.xhr=uuid.uuid4().hex;self.reply=uuid.uuid4().hex
        self.sequence=0;self.events=[];self.callers=[];self.objects={};self.weak={};self.trace_events=[]
        self.stack,self.modules=caller(('modules/request.js','system/snapshot.js','defaultScripts.js'),BASE)
        self.read_stack,self.read_modules=caller(('modules/request.js',),BASE)
        self.body=None;self.hold=False;self.mutate=None;self.lost_read=False
    def clock(self):
        d=self.domain;d.advance()
        return dict(epochMs=d.epoch(),monotonicMs=d.epoch()-BASE+700000)
    def add(self,kind,details=None):
        self.events.append(dict(sequence=len(self.events)+1,eventId=uuid.uuid4().hex,xhrId=self.xhr,
            kind=kind,clock=self.clock(),details={} if details is None else details))
    def birth(self,name,kind,details=None):
        obj=WeakObject()
        def destroyed(_weak):self.add(kind,details)
        self.weak[name]=weakref.ref(obj,destroyed);self.objects[name]=obj
    def trace(self,event):
        self.trace_events.append(deepcopy(event));kind=event['kind'];details=event['details']
        if kind=='created':
            model=packet(BASE)['source']['workers'][0]
            self.callers.append(dict(id='a3'*16,callerStack=self.stack,callerModules=self.modules))
            self.birth('xhr','xhr-destroyed');self.birth('timer','timer-destroyed')
            self.add(kind,dict(callerStackId='a3'*16,engine=deepcopy(model['manager']),submitted=deepcopy(model['code']),
                codeSources=deepcopy(model['codeSources']),requestUrl=details['uri'],method=details['method'],
                protocolSignature=base64.b64encode(b'p'*16).decode()))
        elif kind=='sent':
            need(details['body'] is None);self.birth('reply','reply-destroyed',dict(replyId=self.reply))
            self.add(kind,dict(replyId=self.reply,url=details['uri'],method=details['method'],body=wire(b''),authorizationAttached=True,contentType=''))
            self.add('timer-state',dict(active=False))
        elif kind=='callback-enter':self.add(kind,dict(callback='readystatechange',readyState=details['readyState']))
        elif kind=='text-read':
            need(details['body'].encode('utf8')==self.body)
            self.callers.append(dict(id='a4'*16,callerStack=self.read_stack,callerModules=self.read_modules))
            self.add(kind,dict(replyId=self.reply,scriptSource='qrc:/scripts/modules/request.js',sha256=hashlib.sha256(self.body).hexdigest(),callerStackId='a4'*16))
        elif kind=='callback-leave':
            self.add(kind,dict(callback='readystatechange',readyState=details['readyState']))
            need(details['released']);self.add('callbacks-released')
        else:need(False)
    def exchange(self,path):
        original_send=Handler.send;serialized=[]
        def send(handler,*args,**kwargs):
            result=original_send(handler,*args,**kwargs);serialized.append(handler.wfile.getvalue());return result
        with patch.object(Handler,'send',send):status,body=self.domain.backend.call('GET',path)
        need(len(serialized)==1);header,actual=serialized[0].split(b'\r\n\r\n',1);need(body==actual)
        ids=[row.split(b':',1)[1].strip().decode() for row in header.split(b'\r\n') if row.lower().startswith(b'x-overte-fixture-response:')]
        need(len(ids)==1);self.body=actual
        self.add('reply-finished',dict(replyId=self.reply,httpStatus=status,networkError=0,responseId=ids[0],body=wire(actual)))
        return status,body
    def finish(self,result):
        need(result['xhrCallbackReleased'])
        if not self.hold:
            for key in ('reply','timer','xhr'):self.objects.pop(key)
            need(all(ref() is None for ref in self.weak.values()))
    def produce(self,query):
        self.sequence+=1;before=self.clock();after=self.clock()
        value=dict(iosSnapshotCombinedPreflightHttpVersion=1,requestId=query['commandId'],runId=RUN,
            instance=self.instance,sequence=self.sequence,processId=42,clockDomain='native-process-snapshot-combined-preflight-http',
            clockBefore=before,clockAfter=after,events=deepcopy(self.events),callerStacks=deepcopy(self.callers))
        if self.mutate:self.mutate(value)
        return value


class CombinedConsumerDomain(CombinedBackendDomain):
    def __init__(self,case):
        super().__init__(case);self.http=ConsumerBoundary(self);self.script=OriginalUploadScript(case,self.backend,self.http);self.lose_http=None
        previous=self.ctx.files.execute
        def original_file(session,operation,values):
            if values['remotePath'].endswith('/'+http.FILE) and http.FILE not in self.raws:
                raise NativeUIError('Declared Combined HTTP original not produced')
            return previous(session,operation,values)
        self.ctx.files.execute=original_file
    def post(self,request,timeout):
        query=json.loads(request.data)
        if query['action']!=http.ACTION:return super().post(request,timeout)
        self.commands.append(deepcopy(query));lost=self.lose_http;self.lose_http=None
        if lost=='before':raise OSError('Declared HTTP source send lost before producing original')
        self.raws[http.FILE]=json.dumps(self.http.produce(query),indent=1)+'\n'
        self.ctx.files.echo=json.dumps(query).encode()
        if lost=='after':raise OSError('Declared original HTTP source saved but dispatch return lost')
        return self.ctx.files
    def upload_owner(self,*,combined=True,frontend_http=True):
        return self.runtime.upload_owner('primary',RUN,self.client(),combined=combined,frontend_http=frontend_http,
            epoch_ms=lambda:int(REAL_TIME()*1000),monotonic=REAL_MONOTONIC,sleep=self.sleep)
    def backend_owner(self,*,combined=True,frontend_http=True):
        return backend_context(self.runtime,'primary',RUN,self.reader,self.ctx.binding,epoch_ms=lambda:int(REAL_TIME()*1000),
            monotonic=REAL_MONOTONIC,sleep=self.sleep,domain_policy=self.domain_policy,combined=combined,frontend_http=frontend_http)
