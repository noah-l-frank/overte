"""Declared owned-process/settings and HTTP boundaries, without a listener."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from email.message import Message
from io import BytesIO
import json
import secrets
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import urlsplit
from adapters.native_feature_observation import need
from fixture import snapshot_domain_policy as policy
from fixture.domain import DomainControlHandler
from feature_journeys import snapshot_domain_client as client

RUN='a'*32
DOMAIN='11111111-2222-4333-8444-555555555555'


class Response(BytesIO):status=200


class PolicyFixture:
    def __init__(self,case):
        self.epoch=20000;self.mono=10.;self.binding=dict(processId=73,startIdentity='123456',domainId=DOMAIN);self.actual=deepcopy(self.binding);self.calls=[];self.control_calls=[]
        self.settings=dict(values=dict(security=dict(standard_permissions=[dict(permissions_id=name,id_can_connect=True) for name in ('anonymous','friends','localhost','logged-in')],private_admin_password='NEVER-RETAIN-PRIVATE-SETTINGS')))
        self.drift=None;self.reader=policy.SnapshotDomainPolicy('http://127.0.0.1:49111',lambda:deepcopy(self.actual),epoch_ms=lambda:self.epoch,monotonic=lambda:self.mono)
        self.config=dict(url='http://127.0.0.1:49112'+policy.PATH,token=secrets.token_urlsafe(32),binding=self.binding,instance=self.reader.instance)
        case.enterContext(patch.object(policy,'build_opener',return_value=SimpleNamespace(open=self.open_domain)))
        case.enterContext(patch.object(client,'build_opener',return_value=SimpleNamespace(open=self.open_control)))
    def open_domain(self,request,timeout):
        path=urlsplit(request.full_url).path;need(request.get_method()=='GET' and request.data is None and timeout==2);self.calls.append(path)
        raw=('{'+self.binding['domainId']+'}').encode() if path=='/id' else json.dumps(self.settings).encode()
        if self.drift==path:self.actual['startIdentity']='654321'
        return Response(raw)
    def open_control(self,request,timeout):
        need(request.get_method()=='GET' and request.data is None and timeout==5);self.control_calls.append(request.full_url)
        handler=object.__new__(DomainControlHandler);handler.command='GET';handler.path=urlsplit(request.full_url).path;handler.request_version='HTTP/1.1';handler.requestline='GET '+handler.path+' HTTP/1.1'
        handler.headers=Message()
        for name,value in request.header_items():handler.headers[name]=value
        handler.rfile=BytesIO();handler.wfile=BytesIO();handler.snapshot_domain_reader_token=self.config['token'];handler.snapshot_domain_policy=self.reader.read
        handler.log_message=lambda *_args:None;handler.do_GET();head,body=handler.wfile.getvalue().split(b'\r\n\r\n',1);status=int(head.split(b' ',2)[1])
        response=Response(body);response.status=status;return response
    def client(self):return client.SnapshotDomainClient(self.config,epoch_ms=lambda:self.epoch,monotonic=lambda:self.mono)
    def policy(self,anonymous,logged_in):
        for row in self.settings['values']['security']['standard_permissions']:
            if row['permissions_id']=='anonymous':row['id_can_connect']=anonymous
            elif row['permissions_id']=='logged-in':row['id_can_connect']=logged_in
