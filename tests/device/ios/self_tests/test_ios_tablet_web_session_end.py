"""Actual loopback SDK DELETE/GET, modeled prior Tablet/OS authority only.

These tests qualify once-delivery and local CAS mechanics. The complete native
Tablet seal and independent OS histories are deliberately modeled here; they
do not establish a whole-feature or device result.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
from pathlib import Path
from threading import Thread
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from adapters.native_clock_join import digest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_feature.lock import ScriptSourceLock
from ios.adapters.tablet_web_process_end import TabletWebProcessEnd
from ios.adapters.tablet_web_session_end import TabletWebSessionEnd
from ios.self_tests import test_ios_installed_code as installed_fixture
from ios.self_tests import test_ios_retired_process as os_fixture


class SDKServer:
    def __init__(self):
        self.calls=[];self.present=True;self.lose=False;owner=self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*_args):pass
            def respond(self,status):
                raw=json.dumps(dict(value=None if status==200 else dict(error='invalid session id'))).encode()
                self.send_response(status);self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
            def do_GET(self):owner.calls.append(('GET',self.path));self.respond(200 if owner.present else 404)
            def do_DELETE(self):
                owner.calls.append(('DELETE',self.path));owner.present=False;self.respond(503 if owner.lose else 200)
        self.server=ThreadingHTTPServer(('127.0.0.1',0),Handler);self.thread=Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.url='http://127.0.0.1:'+str(self.server.server_port)
    def close(self):self.server.shutdown();self.server.server_close();self.thread.join()


class TabletSessionEndTests(unittest.TestCase):
    def setUp(self):
        self.fixture=installed_fixture.InstalledCodeTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.fixture.active();self.fixture.binding.begin_retirement();self.fixture.process=None;self.fixture.binding.finish_retirement()
        self.root=Path(self.fixture.temp.name);self.server=SDKServer();self.addCleanup(self.server.close)
        self.os=os_fixture.Boundary();self.lock=ScriptSourceLock(self.root/'script-feature-sources.lock')
        prior_reader=self.os.reader();prior_raw=prior_reader.read();self.prior=dict(original=prior_raw,acquisition=deepcopy(prior_reader.acquisition))
        self.sdk_store=PrivateFeatureState(self.root/'sdk.json');self.sdk=dict(sessionId=self.fixture.scope['sessionId'],generation=1,targetFingerprint=self.fixture.scope['targetFingerprint'])
        self.sdk_store.write(self.sdk,None);binding=dict(self.fixture.scope,processIdentity='42')
        base=SimpleNamespace(_candidate_guard=lambda **_args:None,read_session=lambda _s:self.sdk_store.read(),_binding_store=lambda _s:self.fixture.store,
            _retired_candidate_scope=lambda _s,scope:dict(serverUrl=self.server.url))
        runtime=SimpleNamespace(adapter=base,state_path=lambda _s:self.sdk_store.path,
            _existing=lambda _s:(None,binding['sessionId'],deepcopy(self.sdk_store.read()),dict(serverUrl=self.server.url),deepcopy(self.fixture.scope)))
        self.feature=SimpleNamespace(runtime=runtime,root=self.root,selector='existing-only',role='primary',clock=lambda:True,
            epoch_ms=self.os.epoch,monotonic=lambda:self.os.clock)
        self.process=object.__new__(TabletWebProcessEnd);self.process.feature=self.feature;self.process.lock=self.lock;self.process.binding=binding;self.process.run='a'*32
        self.process.state=dict(source=deepcopy(self.fixture.source),bundleId=os_fixture.BUNDLE,roles=dict(primary=dict(original={'testOnlyPriorOSOwner':True})))
        self.process.store=PrivateFeatureState(self.root/'modeled-prior-process.json');self.process.previous=dict(testOnlyPriorTabletAndOSAuthority=True)
        self.process.store.write(self.process.previous,None);self.process.verify=lambda:deepcopy(self.process.previous)
        self.process.originals_unchanged=lambda:None  # Prior full seal/lease is an explicit model in these transport tests.
        self.process.os_archive=lambda role,value:{'testOnlyPriorOSOwner':True}
        self.process.os_rows=lambda role,value:[dict(mode='observed',**deepcopy(self.prior))]
        transport=patch('ios.adapters.tablet_web_session_end.IOSGraphicsRuntime._retired_process_observer',
            side_effect=lambda *_args:self.os.reader())
        transport.start();self.addCleanup(transport.stop)
    def owner(self):
        owner=TabletWebSessionEnd(self.process)
        owner.prior_os=lambda:deepcopy(self.prior)
        return owner
    def test_actual_DELETE_is_once_then_actual_GET404_precedes_exact_local_CAS(self):
        with self.lock.held():
            owner=self.owner();value=owner.advance();self.assertEqual('complete',owner.state['phase'])
            self.assertIsNone(self.sdk_store.read());self.assertIsNone(self.fixture.store.read());self.assertEqual(value,owner.historical())
            self.assertEqual([('GET','/session/test-only'),('DELETE','/session/test-only'),('GET','/session/test-only')],self.server.calls)
            self.assertEqual(value,self.owner().advance());self.assertEqual(3,len(self.server.calls))
    def test_uncertain_DELETE_reconstruction_reads_only_and_never_repeats(self):
        self.server.lose=True
        with self.lock.held():
            owner=self.owner()
            with self.assertRaises((ValueError,RuntimeError)):owner.advance()
            self.assertEqual('delete-issued',owner.state['phase']);self.assertFalse(owner.state['deleteReturned'])
            reconstructed=self.owner();self.assertIsNotNone(reconstructed.advance())
            self.assertEqual(1,sum(method=='DELETE' for method,_path in self.server.calls));self.assertEqual('GET',self.server.calls[-1][0])
    def test_foreign_replacement_and_slow_issued_write_cannot_send_or_delete_foreign_metadata(self):
        with self.lock.held():
            owner=self.owner();owner.prepare();original=owner.store.write
            def slow(value,previous):
                original(value,previous)
                if value.get('payload') and owner.state['phase']=='delete-issued':self.os.clock+=2
            owner.store.write=slow
            with self.assertRaises((ValueError,RuntimeError)):owner.advance()
            self.assertEqual(0,sum(method=='DELETE' for method,_path in self.server.calls));self.assertIsNotNone(self.fixture.store.read())
            foreign=dict(self.sdk,sessionId='replacement');self.sdk_store.write(foreign,self.sdk_store.read());count=len(self.server.calls)
            with self.assertRaises((ValueError,RuntimeError)):self.owner().advance()
            self.assertEqual(count,len(self.server.calls));self.assertEqual(foreign,self.sdk_store.read())
    def test_rehashed_session_OS_history_cannot_reset_the_genuine_prior_anchor_or_counter(self):
        with self.lock.held():
            owner=self.owner();owner.prepare();original=deepcopy(owner.state)
            for fault in ('anchor','sequence','source'):
                value=deepcopy(original);raw=value['osHistory'][0]['original']
                if fault=='anchor':raw['anchor']['sequence']+=1
                elif fault=='sequence':raw['sequence']=self.prior['original']['sequence']
                else:raw['instance']='f'*32
                value['osHistory'][0]['acquisition']['originalSha256']=digest(raw)
                value['osOriginal']=deepcopy(raw);value['osAcquisition']=deepcopy(value['osHistory'][0]['acquisition'])
                with self.subTest(fault=fault),self.assertRaises((ValueError,RuntimeError)):owner.decode(owner.envelope(value))
            self.assertEqual([],self.server.calls)


if __name__=='__main__':unittest.main()
