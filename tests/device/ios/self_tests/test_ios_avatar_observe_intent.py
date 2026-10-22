"""Real loopback HTTP proves passive observe nonce admission before the socket."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
import unittest

from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.operation_transport_guard import scope
from ios.self_tests.test_ios_normal_input import Boundary


class AvatarObserveIntentTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup);root=Path(temporary.name);root.chmod(0o700)
        self.store=PrivateFeatureState(root/'passive-observe.json');self.boundary=Boundary();self.received=[];self.drop=False;self.errors=[];fixture=self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*_args):pass
            def do_POST(self):
                try:
                    raw=self.rfile.read(int(self.headers['Content-Length']));query=json.loads(raw);fixture.received.append(deepcopy(query))
                    if query['operation']=='observe':fixture.assertEqual(query,fixture.store.read()['queries'][-1])
                    else:fixture.assertNotIn(query,fixture.store.read()['queries'])
                    response=fixture.boundary.post(SimpleNamespace(data=raw),5)
                    if fixture.drop:self.close_connection=True;return
                    self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(response.read(32768))
                except Exception as error:fixture.errors.append(error);self.close_connection=True
        self.server=ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=self.server.serve_forever,daemon=True);thread.start()
        def close():self.server.shutdown();self.server.server_close();thread.join(timeout=2)
        self.addCleanup(close);self.boundary.target['testBuild']['fixtureOrigin']='http://127.0.0.1:'+str(self.server.server_port)
        self.native=self.boundary.input();self.native.observe_intent=self.own

    def own(self,query):
        previous=self.store.read();rows=[] if previous is None else deepcopy(previous['queries']);rows.append(deepcopy(query))
        self.store.write(dict(queries=rows),previous)

    def test_actual_socket_loss_keeps_exact_observe_nonce_and_later_query_is_distinct(self):
        self.drop=True
        with self.assertRaises(Exception):self.native.capture()
        first=deepcopy(self.store.read()['queries'][0]);self.drop=False;self.native.capture()
        self.assertEqual([],self.errors);self.assertEqual(2,len(self.received));self.assertEqual(first,self.received[0])
        self.assertNotEqual(first['commandId'],self.received[1]['commandId']);self.assertEqual(1,self.received.count(first))

    def test_hook_is_passive_only_and_never_receives_input_or_entered_text(self):
        self.native.edit('replace','Ordinary address')
        rows=self.store.read()['queries'];self.assertEqual(1,len(rows));self.assertEqual('observe',rows[0]['operation'])
        self.assertEqual({'schemaVersion','commandId','action','operation'},set(rows[0]));self.assertEqual([],self.errors)
        self.assertEqual(['observe','edit'],[row['operation'] for row in self.received])

    def test_failed_journal_or_final_guard_never_sends_an_unowned_or_late_query(self):
        def refuse(_query):raise OSError('Synthetic failed private journal write')
        self.native.observe_intent=refuse
        with self.assertRaises(OSError):self.native.capture()
        self.assertEqual([],self.received)
        clock=[0]
        def slow(query):self.own(query);clock[0]+=26
        self.native.observe_intent=slow
        def deadline():
            if clock[0]>=25:raise NativeUIError('Original whole operation deadline expired')
        with self.assertRaises(NativeUIError):
            with scope(deadline):self.native.capture()
        self.assertEqual([],self.received);self.assertEqual(1,len(self.store.read()['queries']))


if __name__=='__main__':unittest.main()
