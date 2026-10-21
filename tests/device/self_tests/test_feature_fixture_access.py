"""Actual owned loopback authorization and private config; no product/device IO."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from urllib.error import HTTPError
from urllib.request import Request,urlopen

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from adapters.feature_fixture_access import client,AdapterFixtureClient
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from feature_journeys.server import make_server
from feature_journeys.witness import Client

READER='r'*64;ACTOR='a'*64;ADAPTER='d'*64


class FixtureAccessTests(unittest.TestCase):
    def setUp(self):
        self.server=make_server(READER,ACTOR,adapter_token=ADAPTER)
        self.url='http://127.0.0.1:'+str(self.server.server_address[1])+'/feature-fixture/v1'
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.addCleanup(self.stop)
        self.reader=Client(self.url,READER);self.run,self.root=self.reader.register('emotes');self.ticket='b'*32;self.reader.activate(self.ticket)
        self.actor=Client(self.url,ACTOR);self.adapter=AdapterFixtureClient(self.url,ADAPTER)
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup);self.path=Path(temporary.name)/'fixture.json'
        self.value=dict(fixtureAdapterAccessVersion=1,fixtureUrl=self.url,adapterToken=ADAPTER)
        PrivateFeatureState(self.path).write(self.value,None)
    def stop(self):
        self.server.shutdown();self.server.server_close();self.thread.join(timeout=2);self.assertFalse(self.thread.is_alive())
    def request(self,path,*,token=ADAPTER,method='GET',value=None):
        raw=None if value is None else json.dumps(value).encode()
        request=Request(self.url+path,data=raw,method=method,headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
        with urlopen(request,timeout=2) as response:return json.loads(response.read(1024*1024))
    def test_private_adapter_reader_attaches_original_phase_and_provider_without_runner_secret(self):
        source=client(self.path,configured_url=self.url);source.run=self.run;source.area='emotes'
        original=source.request('/runs/'+self.run+'/active');self.assertEqual(self.ticket,original['ticket'])
        status=source.observe();self.assertEqual(self.ticket,status['ticket']);self.assertEqual([],status['entries'])
        self.assertTrue(source._adapter_admitted)
    def test_adapter_cannot_see_published_independent_peer_facts(self):
        payload=dict(ticket=self.ticket,actor='owned-observer',actorSequence=1,capturedEpochMs=time.time()*1000,
            facts=dict(animation='idle',sit='none',override=False,poseProgress=0,restoredBeforeNominalEnd=False))
        self.actor.request('/runs/'+self.run+'/samples',payload)
        full=self.reader.observe();original=self.adapter.request('/runs/'+self.run)
        self.assertEqual(1,len(full['entries']));self.assertEqual([],original['entries'])
        self.assertEqual(full['ticket'],original['ticket']);self.assertGreaterEqual(original['sampleEpochMs'],full['sampleEpochMs'])
    def test_readonly_token_cannot_register_activate_publish_delete_or_mutate_other_routes(self):
        operations=[('/runs','POST',dict(area='scripts')),('/runs/'+self.run+'/active','POST',dict(ticket='c'*32,verb='open',inputs={})),
            ('/runs/'+self.run+'/samples','POST',{}),('/runs/'+self.run,'DELETE',None),
            ('/runs/'+self.run+'/browser/control','POST',dict(operation='restore-resource')),
            ('/runs/'+self.run+'/account/control','POST',dict(operation='cleanup')),('/oauth/token','POST',dict(password='synthetic'))]
        for path,method,value in operations:
            with self.subTest(path=path),self.assertRaises(HTTPError) as caught:self.request(path,method=method,value=value)
            self.assertEqual(403,caught.exception.code);caught.exception.close()
        self.assertEqual(self.ticket,self.server.journal.active(self.run)['ticket']);self.assertEqual(1,len(self.server.journal.runs))
        self.assertEqual([],self.server.journal.snapshot(self.run)['entries'])
    def test_client_refuses_mutations_before_transport_even_before_role_admission(self):
        for operation in [('register',lambda:self.adapter.register('emotes')),('activate',lambda:self.adapter.request('/runs/'+self.run+'/active',{})),
            ('delete',lambda:self.adapter.request('/runs/'+self.run,method='DELETE'))]:
            with self.subTest(operation=operation[0]),self.assertRaises(NativeUIError):operation[1]()
        self.assertFalse(self.adapter._adapter_admitted)
    def test_reader_actor_or_wrong_credentials_cannot_impersonate_adapter_admission(self):
        for token in (READER,ACTOR,'wrong'*16):
            source=AdapterFixtureClient(self.url,token)
            with self.subTest(tokenKind='separate private role'),self.assertRaises(ValueError):source.request('/runs/'+self.run+'/active')
            self.assertFalse(source._adapter_admitted)
    def test_optional_new_role_does_not_enable_access_on_existing_two_token_servers(self):
        server=make_server(READER,ACTOR);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            url='http://127.0.0.1:'+str(server.server_address[1])+'/feature-fixture/v1'
            with self.assertRaises(ValueError):AdapterFixtureClient(url,ADAPTER).request('/adapter-reader')
        finally:server.shutdown();server.server_close();thread.join(timeout=2)
    def test_malformed_private_config_foreign_origin_and_boolean_version_are_refused(self):
        for edit in [dict(fixtureAdapterAccessVersion=True),dict(adapterToken=READER+'\n'),dict(adapterToken='short'),dict(expectedState={})]:
            value=self.value|edit;store=PrivateFeatureState(self.path);store.write(value,store.read())
            with self.subTest(editKind=list(edit)),self.assertRaises((NativeUIError,ValueError)):client(self.path,configured_url=self.url)
        PrivateFeatureState(self.path).write(self.value,PrivateFeatureState(self.path).read())
        with self.assertRaises(NativeUIError):client(self.path,configured_url=self.url+'/foreign')
    def test_private_config_symlink_hardlink_or_public_mode_cannot_expose_credentials(self):
        original=self.path.read_bytes();self.path.chmod(0o644)
        with self.assertRaises(NativeUIError):client(self.path)
        self.path.chmod(0o600);link=self.path.with_name('other.json');link.hardlink_to(self.path)
        with self.assertRaises(NativeUIError):client(self.path)
        link.unlink();link.symlink_to(self.path)
        with self.assertRaises(NativeUIError):client(link)
        self.assertEqual(original,self.path.read_bytes())
    def test_retired_run_cannot_be_reopened_by_adapter(self):
        source=client(self.path);source.run=self.run;source.area='emotes';source.observe()
        self.reader.close()
        with self.assertRaises(ValueError):source.observe()
        with self.assertRaises(HTTPError) as caught:self.request('/runs',method='POST',value=dict(area='emotes'))
        self.assertEqual(403,caught.exception.code);caught.exception.close()
        self.assertEqual({},self.server.journal.runs)
    def test_adapter_token_must_be_distinct_canonical_and_bounded_before_listener_creation(self):
        for token in (READER,ACTOR,True,'short','d'*257,'d'*32+'\n'):
            with self.subTest(tokenKind=type(token).__name__),self.assertRaises(ValueError):make_server(READER,ACTOR,adapter_token=token)

    def test_every_request_refuses_reassigned_role_even_after_successful_admission(self):
        self.adapter.request('/runs/'+self.run+'/active');self.assertTrue(self.adapter._adapter_admitted)
        self.server.reader_token=ADAPTER;self.server.adapter_token=None
        with self.assertRaises(ValueError):self.adapter.request('/runs/'+self.run)
        self.assertEqual([],self.server.journal.snapshot(self.run)['entries'])


if __name__=='__main__':unittest.main()
