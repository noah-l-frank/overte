"""Original closed handler and reader composition without a listener/process.

HTTP exchange, native producer and kernel PID boundary are explicit models;
normal handler parsing, collector journal and original file reads execute.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from email.message import Message
import io
import json
import os
import unittest
from unittest.mock import patch
from adapters import asset_backend_client as client
from adapters.normal_ui import NativeUIError
from fixture.asset_backend_control import AssetsBackendControl,command
from fixture import domain
from test_asset_backend_files import BackendFilesTests


class BackendControlTests(unittest.TestCase):
    def setUp(self):
        self.fixture=BackendFilesTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups);self.f=self.fixture
        # The collector begins with its own unopened run journal, while the
        # original source admission still comes from the declared producer.
        self.f.transport.detach();self.journal=self.f.b.root/'route-journal';self.journal.mkdir(mode=0o700)
        self.control=AssetsBackendControl(self.f.process,self.journal);self.addCleanup(lambda:self.control.collector and self.control.collector.detach())
        self.token='T'*48;self.calls=[];self.client_guard=True
        self.query=dict(schemaVersion=1,operation='observe',commandId='assets-'+'1'*32,runId=self.f.run,ticket='2'*32)
        self.config=dict(url='http://127.0.0.1:43210/v1/assets-backend',token=self.token,domainId=self.f.b.domain,processIdentity=self.f.process.process_identity,
            executableSha256=self.f.process.sha256,ownerSha256=self.f.process.owner_sha256,sourceRootIdentity={key:str(getattr(self.f.b.export.stat(),'st_'+field)) for key,field in (('device','dev'),('inode','ino'))})
    def handler(self,raw,headers=None,path='/v1/assets-backend'):
        handler=domain.DomainControlHandler.__new__(domain.DomainControlHandler);handler.path=path;handler.command='POST';handler.rfile=io.BytesIO(raw);handler.wfile=io.BytesIO();handler.headers=Message()
        values=[('Content-Type','application/json'),('Content-Length',str(len(raw))),('X-Overte-Assets-Reader',self.token)] if headers is None else headers
        for key,value in values:handler.headers[key]=value
        handler.assets_reader_token=self.token;handler.assets_backend=lambda value:self.control.handle(value);handler.token='broad-control-token'
        handler.status=None;handler.sent_headers=[];handler.send_response=lambda status:setattr(handler,'status',status);handler.send_error=lambda status,*_args:setattr(handler,'status',status)
        handler.send_header=lambda key,value:handler.sent_headers.append((key,value));handler.end_headers=lambda:None
        handler.do_POST();return handler
    def open(self,request,timeout):
        self.calls.append(request);headers=list(request.header_items())+[('Content-Length',str(len(request.data)))]
        handler=self.handler(request.data,headers=headers,path=request.selector)
        class Response:
            status=handler.status
            def __enter__(self):return self
            def __exit__(self,*_args):pass
            def read(self,limit):return handler.wfile.getvalue()[:limit]
        return Response()
    def reader(self):return client.AssetsBackendClient(self.config,lambda:self.client_guard)
    def publish(self):
        self.f.transport=self.control.collector;return self.f.publish()
    def test_closed_reader_to_handler_collector_and_exact_original_export(self):
        reader=self.reader();intents=[]
        def record(value):intents.append(deepcopy(value));return True
        with patch.object(client,'build_opener',return_value=self):
            result=reader.request(self.query,before_send=record);self.assertEqual('pending',result['status']);packet,_=self.publish()
            result=reader.request(dict(self.query,operation='poll'),before_send=record);self.assertEqual('original',result['status']);self.assertEqual(packet,reader.latest)
            snapshot=deepcopy(reader.latest);result=reader.request(dict(self.query,operation='original'),before_send=record);self.assertEqual(snapshot,reader.latest)
        self.assertEqual(3,len(intents));self.assertEqual([self.query['commandId']],self.f.published)
        self.assertEqual(packet,client.export(result['original'],self.query,self.config));self.assertEqual('no-store',dict(self.handler(json.dumps(dict(self.query,operation='original')).encode()).sent_headers)['Cache-Control'])
    def test_repeated_observe_after_lost_delivery_only_polls_the_same_native_nonce(self):
        first=self.control.handle(self.query);self.assertEqual('pending',first['status']);packet,_=self.publish();second=self.control.handle(self.query)
        self.assertEqual('original',second['status']);self.assertEqual(packet,client.export(second['original'],self.query,self.config));self.assertEqual(1,len(self.f.published))
        wrong=dict(self.query,ticket='f'*32)
        with self.assertRaises(NativeUIError):self.control.handle(wrong)
    def test_scope_credential_cannot_use_existing_mutating_domain_routes(self):
        for path in ('/v1/domain-state','/v1/create-rez','/v1/messages-mixer-state','/v1/collaboration-edit'):
            handler=self.handler(b'{"schemaVersion":1,"action":"offline"}',path=path)
            with self.subTest(path=path):self.assertEqual(404,handler.status)
        for headers in ([('X-Overte-E2E-Token','broad-control-token')],[('X-Overte-Assets-Reader',self.token),('X-Overte-Assets-Reader',self.token)],[('X-Overte-Assets-Reader','\u00e4'*48)]):
            with self.subTest(headersCount=len(headers)):self.assertEqual(404,self.handler(json.dumps(self.query).encode(),headers=headers).status)
        self.assertIsNone(self.control.collector)
    def test_duplicate_or_oversized_body_and_desired_state_are_rejected_before_native_delivery(self):
        raw=json.dumps(self.query).encode()
        cases=[(raw,[('X-Overte-Assets-Reader',self.token),('Content-Type','application/json'),('Content-Length','1025')]),
            (raw,[('X-Overte-Assets-Reader',self.token),('Content-Type','application/json'),('Content-Length',str(len(raw))),('Content-Length',str(len(raw)))]),
            (b'{"schemaVersion":1,"schemaVersion":1}',None),(json.dumps(self.query|dict(expectedMappings=[])).encode(),None)]
        for body,headers in cases:
            with self.subTest(size=len(body)):self.assertIn(self.handler(body,headers=headers).status,(400,503))
        self.assertIsNone(self.control.collector)
    def test_missing_source_is_unavailable_and_no_native_result_is_inferred(self):
        (self.f.b.export/'asset-backend-admission.json').unlink();handler=self.handler(json.dumps(self.query).encode());self.assertEqual(503,handler.status)
        self.assertIsNone(self.control.collector);self.assertFalse((self.f.b.export/'asset-backend-query.json').exists())
    def test_read_intent_failure_or_process_guard_failure_prevents_transport(self):
        reader=self.reader()
        with patch.object(client,'build_opener',return_value=self):
            with self.assertRaises(NativeUIError):reader.request(self.query,before_send=lambda _q:False)
            self.client_guard=False
            with self.assertRaises(NativeUIError):reader.request(self.query,before_send=lambda _q:True)
        self.assertEqual([],self.calls)
    def test_export_wrong_binding_original_bytes_and_saved_inode_are_rejected(self):
        self.control.handle(self.query);self.publish();result=self.control.handle(dict(self.query,operation='poll'));original=result['original']
        for mutate in (lambda value:value.update(executableSha256='0'*64),lambda value:value['original']['reference']['identity'].update(inode='999'),lambda value:value['original'].update(base64='e30='),lambda value:value.update(hostAfter=dict(hostEpochMs=1,hostMonotonicMs=1))):
            wrong=deepcopy(original);mutate(wrong)
            with self.assertRaises(NativeUIError):client.export(wrong,self.query,self.config)
    def test_domain_source_environment_is_default_off_and_asset_role_only(self):
        environment=dict(OVERTE_E2E_ASSETS_SOURCE_ROOT='/foreign',XDG_CONFIG_HOME='kept')
        for enabled in (False,True):
            for role in ('0','1','2','3','4','5','6'):
                result=domain.assets_assignment_environment(environment,role,self.f.b.export,enabled)
                with self.subTest(enabled=enabled,role=role):
                    self.assertEqual(str(self.f.b.export) if enabled and role=='3' else None,result.get('OVERTE_E2E_ASSETS_SOURCE_ROOT'));self.assertEqual('kept',result['XDG_CONFIG_HOME'])
        self.assertEqual('/foreign',environment['OVERTE_E2E_ASSETS_SOURCE_ROOT'])
        with patch('sys.argv',['domain.py','--check']):self.assertFalse(domain.parse_args().feature_assets_backend)
    def test_client_configuration_has_no_general_domain_authority_or_remote_origin(self):
        for changes in (dict(url='http://192.0.2.1:43210/v1/assets-backend'),dict(url='http://127.0.0.1:43210/v1/domain-state'),dict(controlToken='broad'),dict(token='short'),dict(sourceRootIdentity={'device':'1','inode':'0'})):
            with self.subTest(fields=list(changes)),self.assertRaises(NativeUIError):client.configuration(self.config|changes)
