"""Real SDK HTTP deletion/loss; whole scene qualifier and OS are explicit models."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from types import SimpleNamespace
import threading
import unittest
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.adapters.appium_adapter import WebDriver
from ios.adapters.world_web_session_end import WorldWebSessionEnd
from ios.self_tests.test_ios_world_web_runtime import WorldWebRuntimeTests
from ios.self_tests.test_ios_installed_code import InstalledCodeTests
from ios.self_tests.test_ios_retired_process import Boundary,SOURCE,BUNDLE


class WorldWebSessionEndTests(unittest.TestCase):
    def setUp(self):
        self.runtime_case=WorldWebRuntimeTests();self.runtime_case.setUp();self.addCleanup(self.runtime_case.doCleanups)
        self.flow=self.runtime_case.coordinator();self.flow.lock=self.flow.primary_lock=self.flow.lock
        self.os=Boundary();self.flow.epoch_ms=self.os.epoch;self.flow.monotonic=lambda:self.os.clock
        self.actual=InstalledCodeTests();self.actual.setUp();self.addCleanup(self.actual.doCleanups)
        self.actual.scope={key:value for key,value in self.flow.state['binding'].items() if key!='processIdentity'}
        self.actual.binding=self.actual.make();self.actual.active();self.actual.binding.begin_retirement();self.actual.process=None;self.actual.binding.finish_retirement()
        self.sdk=dict(sessionId=self.actual.scope['sessionId'],generation=self.actual.scope['generation'],targetFingerprint=self.actual.scope['targetFingerprint'])
        self.sdk_store=PrivateFeatureState(self.flow.runtime.state_path('actor'));self.sdk_store.write(self.sdk,None)
        self.requests=[];self.live=True;self.mode='normal';outer=self
        class Handler(BaseHTTPRequestHandler):
            def log_message(_self,*_args):pass
            def do_GET(_self):
                outer.requests.append(('GET',_self.path));_self.send_response(200 if outer.live else 404);_self.end_headers();_self.wfile.write(b'{"value":null}')
            def do_DELETE(_self):
                outer.requests.append(('DELETE',_self.path))
                if outer.mode not in ('lost-before','ignored'):outer.live=False
                if outer.mode.startswith('lost-'):_self.connection.close();return
                _self.send_response(200);_self.end_headers();_self.wfile.write(b'{"value":null}')
        self.server=ThreadingHTTPServer(('127.0.0.1',0),Handler);self.thread=threading.Thread(target=self.server.serve_forever,kwargs={'poll_interval':.01},daemon=True);self.thread.start()
        self.addCleanup(self.stop_server);self.target=dict(appId=BUNDLE,serverUrl='http://127.0.0.1:'+str(self.server.server_port))
        base=self.flow.runtime.adapter;base.target=lambda _selector:deepcopy(self.target);base.read_session=lambda _selector:self.sdk_store.read()
        base._binding_store=lambda _selector:self.actual.store;base._candidate_guard=lambda **kwargs:True
        def scope(_selector,expected):
            self.assertEqual(self.actual.scope,expected);return deepcopy(self.target)
        base._retired_candidate_scope=scope
        self.flow.runtime._existing=lambda _selector:(WebDriver(self.target['serverUrl']),self.sdk['sessionId'],deepcopy(self.sdk),deepcopy(self.target),deepcopy(self.actual.scope))
        self.flow.runtime._retired_process_observer=lambda *_args:self.os.reader()
        self.flow.finalize=lambda _status:dict(performed=True) # Whole qualification is outside this transport test.
        with self.flow.held():self.flow.load();self.flow.state['phase']='retired';self.flow.save()
        self.process=SimpleNamespace(previous=dict(modeledProcessArchiveVersion=1),state=dict(source=deepcopy(SOURCE)))
        self.archive=SimpleNamespace(previous=dict(modeledSceneArchiveVersion=1),verify=lambda:dict(phaseOriginal={}))
        self.qualified=patch.object(WorldWebSessionEnd,'final_originals',side_effect=lambda:(self.process,self.archive));self.qualified.start();self.addCleanup(self.qualified.stop)
    def stop_server(self):
        self.server.shutdown();self.server.server_close();self.thread.join(timeout=2);self.assertFalse(self.thread.is_alive())
    def owner(self):return WorldWebSessionEnd(self.flow)
    def count(self):return sum(method=='DELETE' for method,_path in self.requests)
    def test_actual_delete_and_positive_get404_are_required_and_repeat_uses_historical_owner(self):
        with self.flow.held():
            owner=self.owner();self.assertEqual(dict(cleaned=True),owner.finish());self.assertEqual(1,self.count());self.assertFalse(self.live)
            self.assertIsNone(self.sdk_store.read());self.assertIsNone(self.actual.store.read());self.assertTrue(owner.state['observed404'])
            requests=deepcopy(self.requests);self.assertEqual(dict(cleaned=True),self.owner().finish());self.assertEqual(requests,self.requests)
            self.assertTrue(self.os.queries);self.assertTrue(all(set(query)=={'bundleId','commandId'} for query in self.os.queries))
    def test_lost_committed_delete_resolves_only_by_actual_get404_without_another_delete(self):
        self.mode='lost-after'
        with self.flow.held():
            owner=self.owner()
            with self.assertRaises(RuntimeError):owner.finish()
            self.assertEqual('delete-issued',owner.state['phase']);self.assertEqual(1,self.count());self.assertIsNotNone(self.sdk_store.read())
            self.mode='normal';self.assertEqual(dict(cleaned=True),self.owner().finish());self.assertEqual(1,self.count())
    def test_lost_uncommitted_or_ignored_delete_remains_owned_and_is_never_replayed(self):
        self.mode='lost-before'
        with self.flow.held():
            with self.assertRaises(RuntimeError):self.owner().finish()
            self.assertEqual(1,self.count());self.mode='normal'
            for _attempt in range(2):
                with self.assertRaises(NativeUIError):self.owner().finish()
            self.assertEqual(1,self.count());self.assertTrue(self.live);self.assertIsNotNone(self.sdk_store.read());self.assertIsNotNone(self.actual.store.read())
    def test_late_durable_delete_intent_cannot_send_after_original_os_acquisition_expires(self):
        with self.flow.held():
            owner=self.owner();write=owner.store.write
            def slow(value,previous):
                write(value,previous)
                if value['state']['phase']=='delete-issued':self.os.clock+=2
            with patch.object(owner.store,'write',side_effect=slow),self.assertRaises(NativeUIError):owner.finish()
            self.assertEqual(0,self.count());self.assertTrue(self.live);self.assertEqual('delete-issued',owner.state['phase'])


if __name__=='__main__':unittest.main()
