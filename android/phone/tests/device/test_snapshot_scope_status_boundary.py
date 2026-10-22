"""Fresh logical SDK status transport retains all three independent queries."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from collections import Counter
from copy import deepcopy
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
from pathlib import Path
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest

ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT/'tests/device'),str(ROOT/'tests/device/adapters/android-phone'),str(Path(__file__).parent)]
from adapters.normal_ui import NativeUIError
import snapshots_journey_producers as shared
import snapshot_documents_journey_boundary as documents
import test_snapshot_system_context as contexts


class SnapshotScopeStatusBoundaryTests(unittest.TestCase):
    def setUp(self):
        host=shared.HostOnlyBoundary();host.__enter__();self.addCleanup(host.close)
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.model=SimpleNamespace(lock=threading.RLock(),rpc_counts=Counter(),query_epoch=20000,
            model_binding=deepcopy(contexts.BINDING),component=contexts.COMPONENT,app_state=3,lifecycle={})
        self.calls=[];self.responses=[];self.fault=lambda count:None;owner=self
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                request=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                owner.calls.append(request['kind'])
                value=shared.SnapshotTarget.rpc(owner.model,request['kind'],request['value'])
                raw=json.dumps(value).encode();owner.responses.append(deepcopy(value))
                owner.fault(len(owner.calls))
                self.send_response(200);self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
            def log_message(self,*args):pass
        self.server=ThreadingHTTPServer(('127.0.0.1',0),documents.keepalive_handler(Handler))
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        def close():self.server.shutdown();self.server.server_close();self.thread.join(2)
        self.addCleanup(close)
        documents.install_keepalive_snapshot_rpc(shared.SnapshotProxy)
        self.proxy=shared.SnapshotProxy('http://127.0.0.1:'+str(self.server.server_port),Path(temp.name))
        self.addCleanup(documents.close_snapshot_rpc,self.proxy);self.calls.clear();self.responses.clear()
    def context(self):
        return self.proxy._snapshot_system_context(None,contexts.BINDING,contexts.Boundary().reader().read(),lambda:True)
    def test_status_component_status_are_three_actual_independent_queries_every_time(self):
        scope=self.context();self.assertTrue(scope.guard())
        self.assertEqual(['scope-status','snapshot-state','scope-status'],self.calls)
        self.assertEqual(2,self.model.rpc_counts['scope-status']);self.assertEqual(1,self.model.rpc_counts['snapshot-state'])
        first=deepcopy(self.responses);self.assertTrue(scope.guard())
        self.assertEqual(['scope-status','snapshot-state','scope-status']*2,self.calls)
        self.assertEqual(first,self.responses[-3:]);self.assertEqual(4,self.model.rpc_counts['scope-status'])
    def test_each_status_returns_actual_binding_and_state_without_alias_or_caller_authority(self):
        first=self.proxy.call('scope-status',None)
        self.assertEqual(3,first['appState']);self.assertFalse(first['foreground']);self.assertEqual(self.model.model_binding,first['binding'])
        first['binding']['sessionId']='caller';self.model.app_state=4
        second=self.proxy.call('scope-status',None);self.assertTrue(second['foreground']);self.assertEqual(4,second['appState'])
        self.assertEqual(contexts.BINDING,second['binding'])
        with self.assertRaises(ValueError):shared.SnapshotTarget.rpc(self.model,'scope-status',{'binding':contexts.BINDING})
    def test_pid_session_generation_target_and_state_changes_between_each_original_query_are_red(self):
        for after in (1,2):
            for field in ('processIdentity','sessionId','generation','targetFingerprint','appState'):
                self.calls.clear();self.responses.clear();self.model.model_binding=deepcopy(contexts.BINDING);self.model.app_state=3
                def changed(count):
                    if count!=after:return
                    if field=='appState':self.model.app_state=2
                    else:self.model.model_binding[field]=(2 if field=='generation' else 'f'*64 if field=='targetFingerprint' else '32:1234' if field=='processIdentity' else 'foreign-session')
                self.fault=changed
                with self.subTest(after=after,field=field),self.assertRaises(NativeUIError):self.context().guard()
                self.assertEqual(['scope-status','snapshot-state','scope-status'],self.calls)
    def test_component_change_after_first_status_is_seen_by_the_independent_middle_query(self):
        self.fault=lambda count:setattr(self.model,'component','foreign.app/foreign.app.Window') if count==1 else None
        with self.assertRaises(NativeUIError):self.context().guard()
        self.assertEqual(['scope-status','snapshot-state'],self.calls)
    def test_normal_component_foreground_transition_after_middle_query_is_not_hidden(self):
        def changed(count):
            if count==2:self.model.component=contexts.PRIMARY+'/'+contexts.PRIMARY+'.MainActivity';self.model.app_state=4
        self.fault=changed
        with self.assertRaises(NativeUIError):self.context().guard()
        self.assertEqual(['scope-status','snapshot-state','scope-status'],self.calls)
    def test_component_query_cannot_hide_a_late_return_with_changed_binding_or_process(self):
        for field,value in (('processIdentity','32:1234'),('sessionId','foreign-session')):
            self.calls.clear();self.model.model_binding=deepcopy(contexts.BINDING)
            def changed(count):
                if count==2:self.model.model_binding[field]=value
            self.fault=changed
            with self.subTest(field=field),self.assertRaises(NativeUIError):self.context().guard()
            self.assertEqual(['scope-status','snapshot-state','scope-status'],self.calls)
    def test_missing_owner_authority_sends_no_original_query(self):
        scope=self.proxy._snapshot_system_context(None,contexts.BINDING,contexts.Boundary().reader().read(),lambda:False)
        with self.assertRaises(NativeUIError):scope.guard()
        self.assertEqual([],self.calls)


if __name__=='__main__':unittest.main()
