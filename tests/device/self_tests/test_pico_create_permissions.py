"""Fixed Phone controller reuse with strict no-replay and real loopback joins."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from http.server import ThreadingHTTPServer
from pathlib import Path
import sys
import threading
import unittest
import uuid
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from self_tests import test_create_permissions as original
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.feature_fixture_access import AdapterFixtureClient
from fixture.pico_create_permissions import PicoCreatePermissions,FIELDS
from fixture.domain import DomainControlHandler
from feature_journeys.create_permissions import CreatePermissionProvider
from feature_journeys.server import make_server
from feature_journeys.witness import Client
from adapters.pico4.create_rez import validate_source


class PicoCreatePermissionTests(original.CreatePermissionTests):
    def setUp(self):
        super().setUp()
        for row in self.server.security['standard_permissions']:
            for key in FIELDS-{'permissions_id'}:row.setdefault(key,False)
        self.original=deepcopy(self.server.security)
    def build(self):
        return PicoCreatePermissions(self.process,lambda pid:self.owned and pid==self.process.pid,
            self.server.server_address[1],original.DOMAIN,self.store)
    def test_lost_response_recovers_actual_state_without_post_replay(self):
        # The stricter reader adds a pre-POST comparison. Lose the response
        # after the actual original POST, rather than counting source reads.
        self.call('observe');http=self.controller.http
        def lose(path,payload=None):
            result=http(path,payload)
            if payload is not None:raise OSError('declared read loss after actual original POST')
            return result
        self.controller.http=lose
        with self.assertRaises(OSError):self.call('set',allowed=False)
        self.controller=self.build();observed=self.call('observe')
        self.assertFalse(any(row['id_can_rez'] for row in observed['standard']));self.assertEqual(1,len(self.server.posts))
        self.call('restore');self.assertEqual(self.original,self.server.security)
    def test_uncertain_ignored_post_stays_pending_across_cold_observe_set_restore(self):
        self.call('observe');self.server.ignore=True
        with self.assertRaises(NativeUIError):self.call('set',allowed=False)
        pending=self.store.read();self.assertEqual(1,len(self.server.posts))
        for operation,args in [('observe',{}),('set',dict(allowed=False)),('restore',{})]:
            self.controller=self.build()
            with self.assertRaises(NativeUIError):self.call(operation,**args)
            self.assertEqual(pending,self.store.read());self.assertEqual(1,len(self.server.posts))
    def test_unknown_or_non_boolean_original_columns_never_reach_post(self):
        for key,value in [('foreign',True),('id_can_connect',1)]:
            self.server.security=deepcopy(self.original);self.server.security['standard_permissions'][0][key]=value
            with self.assertRaises(NativeUIError):self.call('set',allowed=False)
            self.assertEqual([],self.server.posts);self.assertIsNone(self.store.read())
    def test_frozen_epoch_cannot_hide_slow_original_acquisition(self):
        clock=[1.0];self.controller.monotonic=lambda:clock[0];self.controller.epoch_ms=lambda:20000
        http=self.controller.http
        def slow(path,payload=None):
            value=http(path,payload)
            if path=='/settings.json':clock[0]+=2
            return value
        self.controller.http=slow
        with self.assertRaises(NativeUIError):self.call('set',allowed=False)
        self.assertEqual([],self.server.posts);self.assertIsNone(self.store.read())
    def test_foreign_standard_row_during_durable_intent_never_reaches_original_post(self):
        self.call('observe');save=self.controller.save
        def foreign(**changes):
            save(**changes)
            if changes.get('phase')=='changing':self.server.security['standard_permissions'][0]['id_can_kick']=True
        self.controller.save=foreign
        with self.assertRaises(NativeUIError):self.call('set',allowed=False)
        self.assertEqual([],self.server.posts);self.assertIsNotNone(self.store.read()['pending'])
        self.assertTrue(self.server.security['standard_permissions'][0]['id_can_kick'])
    def test_frozen_epoch_final_guard_ages_actual_source_and_prevents_original_post(self):
        clock=[1.0];self.controller.monotonic=lambda:clock[0];self.controller.epoch_ms=lambda:20000
        self.call('observe');acquire=self.controller.original;guard=self.controller.guard;delay=[False]
        def original_read():
            value=acquire()
            if self.controller.state['pending'] is not None:delay[0]=True
            return value
        def last_guard():
            guard()
            if delay[0]:clock[0]+=2;delay[0]=False
        self.controller.original=original_read;self.controller.guard=last_guard
        with self.assertRaises(NativeUIError):self.call('set',allowed=False)
        self.assertEqual([],self.server.posts);self.assertIsNotNone(self.store.read()['pending'])
        self.assertEqual(self.original,self.server.security)
    def fixture(self):
        # Actual DomainControlHandler and Settings owner; only the domain
        # process/Settings endpoint is the explicitly synthetic original actor.
        handler=type('QuietOriginalDomainControl',(DomainControlHandler,),{'log_message':lambda *_:None})
        control=ThreadingHTTPServer(('127.0.0.1',0),handler)
        control_lock=threading.Lock()
        def request(command):
            with control_lock:return self.controller.request(command)
        DomainControlHandler.token='c'*64;DomainControlHandler.create_permissions=staticmethod(request)
        thread=threading.Thread(target=control.serve_forever,daemon=True);thread.start()
        self.addCleanup(lambda:(control.shutdown(),control.server_close(),thread.join(timeout=2)))
        provider=CreatePermissionProvider(dict(controlUrl='http://127.0.0.1:'+str(control.server_address[1])+'/v1/create-permissions',
            controlToken='c'*64,domainId=original.DOMAIN),PrivateFeatureState(self.root/'provider.json'))
        fixture=make_server('r'*64,'p'*64,adapter_token='a'*64,create_permissions=provider)
        worker=threading.Thread(target=fixture.serve_forever,daemon=True);worker.start()
        self.addCleanup(lambda:(fixture.shutdown(),fixture.server_close(),worker.join(timeout=2)))
        url='http://127.0.0.1:'+str(fixture.server_address[1])+'/feature-fixture/v1'
        return provider,fixture,Client(url,'r'*64),AdapterFixtureClient(url,'a'*64)
    def test_original_runner_phase_changes_settings_adapter_only_reads_and_cleanup_restores(self):
        provider,server,reader,adapter=self.fixture();run,_url=reader.register('create');adapter.run=run
        def read():return adapter.request('/runs/'+run+'/create-permissions',phase_nonce=uuid.uuid4().hex)
        first=read();validate_source(first,run,original.DOMAIN);self.assertEqual([],self.server.posts)
        ticket=uuid.uuid4().hex;reader.activate(ticket,'set-rez-permission',dict(allowed=False))
        denied=read();validate_source(denied,run,original.DOMAIN,first)
        self.assertEqual(ticket,denied['events'][-1]['ticket']);self.assertFalse(any(row['id_can_rez'] for row in denied['current']['standard']))
        self.assertEqual(1,len(self.server.posts))
        for operation in [('activate',lambda:adapter.activate(uuid.uuid4().hex,'set-rez-permission',dict(allowed=True))),
                          ('control',lambda:adapter.request('/runs/'+run+'/create-permissions',{'allowed':True},method='POST'))]:
            with self.subTest(operation=operation[0]),self.assertRaises(NativeUIError):operation[1]()
        self.assertEqual(1,len(self.server.posts));self.assertNotIn('ownerToken',str(denied));self.assertNotIn('controlToken',str(denied))
        reader.activate(uuid.uuid4().hex,'cleanup',{});restored=read();validate_source(restored,run,original.DOMAIN,denied)
        self.assertTrue(restored['current']['restored']);self.assertEqual(self.original,self.server.security)
        self.assertEqual(2,len(self.server.posts));reader.close();self.assertTrue(provider.state()['retired']);self.assertIsNone(self.store.read())
    def test_lost_initial_snapshot_retains_unknown_reservation_without_baseline_or_settings_write(self):
        provider,server,reader,adapter=self.fixture();initial=provider.request_initial
        def lose(value):initial(value);raise OSError('declared lost initial original read')
        provider.request_initial=lose
        with self.assertRaises(ValueError):reader.register('create')
        reservation=provider.store.read();self.assertEqual([],reservation['original']);self.assertIsNone(reservation['last'])
        with self.assertRaises(NativeUIError):provider.state()
        with self.assertRaises(ValueError):reader.register('create')
        self.assertEqual(reservation,provider.store.read());self.assertEqual([],self.server.posts)
        self.assertEqual(0,server.internal_errors)

    def test_lost_runner_post_response_recovers_only_actual_target_without_new_settings_write(self):
        provider,server,reader,adapter=self.fixture();run,_=reader.register('create');before=provider.state()
        call=provider.request
        def lose(operation,allowed=None):
            result=call(operation,allowed)
            if operation=='set':raise OSError('declared lost response after original actual POST')
            return result
        provider.request=lose
        with self.assertRaises(ValueError):reader.activate(uuid.uuid4().hex,'set-rez-permission',dict(allowed=False))
        self.assertIsNotNone(provider.state()['pending']);self.assertEqual(1,len(self.server.posts))
        provider.request=call
        actual=adapter.request('/runs/'+run+'/create-permissions',phase_nonce=uuid.uuid4().hex)
        self.assertIsNone(provider.state()['pending']);self.assertEqual(1,len(self.server.posts));self.assertEqual(1,len(actual['events']))
        reader.activate(uuid.uuid4().hex,'cleanup',{});reader.close()


if __name__=='__main__':unittest.main()
