"""Normal Upload connected to actual OAuth/protocol and original response IO.

TLS, Qt and sockets remain explicit model boundaries. The existing actual
Handler.send serializes headers/body into real BytesIO streams; no listener,
certificate, service or device is created. Bearer is private to this producer.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from email.message import Message
from io import BytesIO
import json
import ssl
from types import SimpleNamespace
import uuid
from unittest.mock import Mock
from urllib.parse import urlencode,urlsplit
from adapters.native_feature_observation import need
from feature_journeys.account_provider import AccountProvider
from feature_journeys.avatar_social_http import AccountAuthenticator
from feature_journeys.server import Handler
from feature_journeys.snapshot_upload_http import handle
from feature_journeys.snapshot_upload_provider import SnapshotUploadProvider,UPLOAD,STORIES,BODY,encode
from ios.self_tests.snapshot_upload_domain import UploadDomain
from ios.self_tests.snapshot_upload_flow_domain import SnapshotUploadFlowDomain,RUN,REAL_TIME,REAL_MONOTONIC


class SnapshotBackendDomain:
    def __init__(self):
        self.accounts=AccountProvider(epoch_ms=lambda:int(REAL_TIME()*1000),monotonic=REAL_MONOTONIC)
        self.accounts.provision(RUN);self.accounts.activate(RUN,'f'*32);credentials=self.accounts.credentials(RUN,'owned')
        status,grant=self.accounts.grant(urlencode(dict(grant_type='password',scope='owner',**credentials)).encode());need(status==200)
        self._authorization='Bearer '+grant['access_token'];self.provider=SnapshotUploadProvider(AccountAuthenticator(self.accounts),epoch_ms=lambda:int(REAL_TIME()*1000),monotonic=REAL_MONOTONIC)
        self.provider.provision(RUN);self.provider.activate(RUN,'f'*32);self.sent=[]
    def call(self,method,path,raw=b'',content_type=''):
        handler=object.__new__(Handler);handler.command=method;handler.path=path;handler.request_version='HTTP/1.1';handler.requestline=method+' '+path+' HTTP/1.1'
        handler.rfile=BytesIO(raw);handler.wfile=BytesIO();handler.connection=Mock(spec=ssl.SSLSocket);handler.connection.version.return_value='TLSv1.3'
        handler.server=SimpleNamespace(snapshot_upload_provider=self.provider);handler.headers=Message();handler.headers['Host']='controlled.invalid';handler.headers['Authorization']=self._authorization
        if raw:handler.headers['Content-Length']=str(len(raw));handler.headers['Content-Type']=content_type
        need(handle(handler,urlsplit(path)));original=handler.wfile.getvalue();header,body=original.split(b'\r\n\r\n',1)
        status=int(header.split(b'\r\n',1)[0].split(b' ',2)[1]);self.sent.append(dict(method=method,path=path,raw=raw,status=status,response=body))
        return status,body
    def source(self):return self.provider.snapshot(RUN,uuid.uuid4().hex)
    def independent_body(self,identity):
        # A declared independent backend reader boundary, with no Bearer or
        # native response passed to the adapter. Production reader admission
        # and durable original acquisition remain separately required.
        with self.provider.lock:
            value=self.provider.runs[RUN]['uploads'][identity];need(value['retired'] is None)
            with BytesIO(value['body']) as stream:raw=stream.read()
            return deepcopy(value['file']),raw


class BackendUpload(UploadDomain):
    def __init__(self,case,backend,**kwargs):self.backend=backend;self.upload_reply=None;super().__init__(case,**kwargs)
    def perform_request(self,stage):
        if stage=='upload':
            super().perform_request(stage);boundary='actual-native-'+uuid.uuid4().hex
            raw=(b'--'+boundary.encode()+b'\r\nContent-Type: image/png\r\nContent-Disposition: form-data; name="image"; filename="'+self.path.name.encode()+b'"\r\n\r\n'+self.received.getvalue()+b'\r\n--'+boundary.encode()+b'--\r\n')
            status,body=self.backend.call('POST',UPLOAD,raw,'multipart/form-data; boundary="'+boundary+'"')
            need(status==200);self.upload_reply=json.loads(body)['data'];return status,0,body
        need(stage=='story' and self.upload_reply is not None);reply=self.upload_reply
        details=dict(image_url=reply['image_url'],snapshot_id=reply['id'],original_image_file_name=reply['original_image_file_name'])
        raw=encode(dict(user_story=dict(details=json.dumps(details,indent=4)+'\n',thumbnail_url=reply['thumbnail_url'],place_name='controlled.invalid',path='/snapshot-fixture',action='snapshot',audience='for_url')))
        status,body=self.backend.call('POST',STORIES,raw,'application/json');need(status==200 and json.loads(body)['user_story']['details']['image_url']);return status,0,body


class SnapshotUploadBackendFlow(SnapshotUploadFlowDomain):
    def __init__(self,case):self.backend=SnapshotBackendDomain();super().__init__(case)
    def new_upload(self):return BackendUpload(self.case,self.backend,path=self.f.f.h.path,version=2,now=self.epoch)
    def prepare(self):
        result=super().prepare();ticket=self.activations[-1]['ticket'];self.backend.accounts.activate(RUN,ticket);self.backend.provider.activate(RUN,ticket);return result
