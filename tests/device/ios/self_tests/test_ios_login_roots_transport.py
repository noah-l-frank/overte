"""Real loopback NormalInput POST and unchanged AFC raw Login-root originals."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
import threading
from urllib.request import Request
import unittest
from adapters.normal_ui import NativeUIError
from ios.adapters import normal_input
from ios.self_tests.test_ios_normal_input import Boundary
from ios.self_tests.test_ios_login_root_ownership import packet,EPOCH


class LoginRootsTransportTests(unittest.TestCase):
    transport=normal_input

    def boundary(self,*,legacy=False,fault=None):
        class Native(Boundary):
            def observed(self):
                value=super().observed();value['sampleEpochMs']=EPOCH+10
                if not legacy:
                    original=packet();original['controls']=[]
                    if fault=='pid':original['ownership']['processId']=43
                    elif fault=='clock':original['ownership']['capturedEpochMs']-=2000
                    elif fault=='secret':original['ownership']['roots'][0]['password']='must-not-be-accepted'
                    value['loginRootOwnership']=original
                return value
        native=Native();calls=[]
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*_args):pass
            def do_POST(self):
                raw=self.rfile.read(int(self.headers['Content-Length']));request=Request('http://127.0.0.1'+self.path,data=raw)
                native.post(request,1);calls.append(deepcopy(native.receipt));body=native.response
                self.send_response(200);self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        self.addCleanup(server.server_close);self.addCleanup(server.shutdown);self.addCleanup(thread.join,.01)
        native.target['testBuild']['fixtureOrigin']='http://127.0.0.1:'+str(server.server_port)
        reader=self.transport.NativeInput(native,'owned-session',native.target,native.process,monotonic=native.tick,
            sleep=lambda _:None,native_epoch_ms=lambda:EPOCH+10)
        return native,reader,calls
    def test_actual_post_afc_preserves_original_optional_component_and_literal_old_receipt(self):
        for legacy in (True,False):
            with self.subTest(legacy=legacy):
                native,reader,calls=self.boundary(legacy=legacy);value=reader.capture()
                self.assertEqual(value,native.receipt['observation']);self.assertEqual(calls[-1],reader.last_receipt)
                self.assertEqual(not legacy,'loginRootOwnership' in value)
                if not legacy:self.assertTrue(value['loginRootOwnership']['ownership']['roots'][0]['weakAlive'])
                self.assertEqual(['observe'],[row['operation'] for row in native.requests])
    def test_foreign_stale_or_secret_nested_original_never_qualifies_inside_fresh_parent(self):
        for fault in ('pid','clock','secret'):
            with self.subTest(fault=fault):
                native,reader,calls=self.boundary(fault=fault)
                with self.assertRaises(NativeUIError):reader.capture()
                self.assertTrue(calls);self.assertEqual(['observe'],[row['operation'] for row in native.requests])


if __name__=='__main__':unittest.main()
