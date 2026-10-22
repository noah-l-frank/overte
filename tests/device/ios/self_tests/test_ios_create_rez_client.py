"""Actual DomainControlHandler + normal settings API over private loopback HTTP."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request,urlopen
import json
import threading
import unittest

from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.lock import ScriptSourceLock
from fixture.domain import DomainControlHandler
from fixture.create_rez_authority import CreateRezControl
from ios.adapters.create_rez_client import CreateRezClient
from ios.self_tests import test_ios_create_rez_authority as authority_tests
from ios.self_tests.test_ios_create_files import BINDING,RUN


class CreateRezClientTests(unittest.TestCase):
    def setUp(self):
        self.harness=authority_tests.RezAuthorityTests();self.harness.setUp();self.addCleanup(self.harness.doCleanups)
        self.path=self.harness.path;self.lock=ScriptSourceLock(self.path/'script-feature-sources.lock')
        self.control=CreateRezControl(self.harness.owner(),PrivateFeatureState(self.path/'control-owner.json'))
        self.commands=[];self.lose=False;self.alive=True
        def command(value):
            self.commands.append(deepcopy(value));result=self.control.handle(value)
            if self.lose: raise RuntimeError('Synthetic lost private control return')
            return result
        handler=type('BoundActualHandler',(DomainControlHandler,),dict(token='T'*48,create_rez=staticmethod(command),log_message=lambda *_args:None))
        self.server=ThreadingHTTPServer(('127.0.0.1',0),handler)
        self.thread=threading.Thread(target=self.server.serve_forever,kwargs={'poll_interval':.01},daemon=True);self.thread.start()
        self.addCleanup(self.server.server_close);self.addCleanup(self.thread.join,2);self.addCleanup(self.server.shutdown)
        self.config=dict(controlUrl='http://127.0.0.1:'+str(self.server.server_port)+'/v1/create-rez',token='T'*48,domainId=self.harness.binding['domainId'])
        self.store=PrivateFeatureState(self.path/'ios-create-rez-client.json')
    def owner(self):return CreateRezClient(self.store,self.lock,BINDING,RUN,self.config,lambda:self.alive)
    def wire(self,query,*,token=None):
        request=Request(self.config['controlUrl'],data=json.dumps(query).encode(),method='POST',headers={'X-Overte-E2E-Token':self.config['token'] if token is None else token,'Content-Type':'application/json'})
        return urlopen(request,timeout=2)

    def test_client_reads_actual_permission_rows_and_restores_exact_domain_original(self):
        with self.lock.held():
            owner=self.owner();initial=owner.request('observe');denied=owner.request('set',allowed=False)
            self.assertTrue(all(not row['id_can_rez'] and not row['id_can_rez_tmp'] for row in denied['standardPermissions']))
            restored=owner.request('restore');self.assertEqual(initial['standardPermissions'],restored['standardPermissions'])
            self.assertEqual(2,self.harness.posts);self.assertNotIn('canRez',restored)
            self.assertNotIn(self.config['token'],json.dumps(self.store.read()))

    def test_lost_input_uses_explicit_read_only_recovery_after_reconstruction(self):
        with self.lock.held():
            owner=self.owner();self.lose=True
            with self.assertRaises(HTTPError) as error:owner.request('set',allowed=False)
            error.exception.close()
            self.assertEqual(1,self.harness.posts);self.assertIsNone(self.owner().state['commands'][-1]['original'])
            self.lose=False;recovered=self.owner();result=recovered.recover()
            self.assertEqual(['set','recover'],[row['operation'] for row in self.commands]);self.assertEqual(1,self.harness.posts)
            self.assertEqual(self.commands[0]['commandId'],self.commands[1]['queryCommandId'])
            self.assertTrue(all(not row['id_can_rez'] for row in result['standardPermissions']))
            recovered.request('observe');self.assertEqual(1,self.harness.posts)

    def test_actual_handler_rejects_wrong_token_fields_nonce_reuse_and_source_rollover(self):
        query=dict(schemaVersion=1,commandId='b'*32,runId=RUN,operation='set',allowed=False)
        with self.assertRaises(HTTPError) as error:self.wire(query,token='wrong')
        self.assertEqual(404,error.exception.code);error.exception.close();self.assertEqual([],self.commands);self.assertEqual(0,self.harness.posts)
        for extra in ({'expected':{}},{'canRez':True},{'ids':[]},{'schemaVersion':True}):
            with self.subTest(extra=extra),self.assertRaises(HTTPError) as error:self.wire(query|extra)
            error.exception.close()
        self.assertEqual(0,self.harness.posts)
        with self.wire(query) as response:self.assertEqual(200,response.status)
        self.assertEqual(1,self.harness.posts)
        with self.assertRaises(HTTPError) as error:self.wire(query|dict(allowed=True))
        error.exception.close()
        self.harness.binding['processId']=43
        with self.assertRaises(HTTPError) as error:self.wire(dict(schemaVersion=1,commandId='c'*32,runId=RUN,operation='observe'))
        error.exception.close()
        self.assertEqual(1,self.harness.posts)

    def test_wrong_native_domain_or_candidate_binding_cannot_adopt_a_control_journal(self):
        with self.lock.held():
            owner=self.owner();owner.request('observe')
            with self.assertRaises(NativeUIError):CreateRezClient(self.store,self.lock,BINDING|dict(processIdentity='43'),RUN,self.config,lambda:True)
            with self.assertRaises(NativeUIError):CreateRezClient(self.store,self.lock,BINDING,RUN,self.config|dict(domainId='33333333-3333-4333-8333-333333333333'),lambda:True)
            self.alive=False
            with self.assertRaises(NativeUIError):owner.request('set',allowed=False)
            self.assertEqual(0,self.harness.posts)


if __name__=='__main__':unittest.main()
