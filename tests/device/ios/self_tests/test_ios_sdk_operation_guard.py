"""Actual WebDriver HTTP call with default, nested and thread-local guards."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from http.server import BaseHTTPRequestHandler,HTTPServer
import json
import threading
import unittest
from unittest.mock import patch
from urllib.request import Request
from adapters.normal_ui import NativeUIError
from adapters.operation_transport_guard import scope
from ios.adapters.appium_adapter import WebDriver
from ios.adapters.feature_observation import post_request


class SDKOperationGuardTests(unittest.TestCase):
    def setUp(self):
        self.requests=[];current=self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*_args):pass
            def do_POST(self):
                raw=self.rfile.read(int(self.headers['Content-Length']));current.requests.append((self.path,raw))
                response=json.dumps(dict(value=dict(received=True))).encode()
                self.send_response(200);self.send_header('Content-Length',str(len(response)));self.end_headers();self.wfile.write(response)
        self.server=HTTPServer(('127.0.0.1',0),Handler)
        self.thread=threading.Thread(target=lambda:self.server.serve_forever(poll_interval=.01),daemon=True);self.thread.start()
        self.addCleanup(self.stop);self.driver=WebDriver('http://127.0.0.1:'+str(self.server.server_address[1]))
    def stop(self):
        self.server.shutdown();self.server.server_close();self.thread.join(timeout=2);self.assertFalse(self.thread.is_alive())
    def send(self):return self.driver.execute('existing','mobile: backgroundApp',dict(seconds=-1))

    def test_default_actual_http_request_and_response_remain_unchanged(self):
        self.assertEqual(dict(received=True),self.send());self.assertEqual(1,len(self.requests))
        path,raw=self.requests[0];self.assertEqual('/session/existing/execute/sync',path)
        self.assertEqual(dict(script='mobile: backgroundApp',args=[dict(seconds=-1)]),json.loads(raw))

    def test_nested_original_guard_remains_active_and_error_releases_only_its_own_context(self):
        enabled=[True];events=[]
        def outer():events.append('outer');return enabled[0]
        def inner():events.append('inner');return enabled[0]
        with scope(outer):
            with scope(inner):self.send()
            enabled[0]=False
            with self.assertRaises(NativeUIError):self.send()
            enabled[0]=True;self.send()
        self.send();self.assertEqual(3,len(self.requests));self.assertIn('inner',events)
        with self.assertRaises(NativeUIError),scope(lambda:False):self.send()
        self.send();self.assertEqual(4,len(self.requests))

    def test_thread_does_not_inherit_another_operations_guard(self):
        enabled=[True];errors=[]
        with scope(lambda:enabled[0]):
            enabled[0]=False
            def worker():
                try:self.send()
                except Exception as error:errors.append(error)
            thread=threading.Thread(target=worker);thread.start();thread.join(timeout=2)
            self.assertFalse(thread.is_alive());self.assertEqual([],errors)
            with self.assertRaises(NativeUIError):self.send()
            enabled[0]=True
        self.assertEqual(1,len(self.requests))

    def test_slow_actual_serialization_prevents_urlopen_after_preparation(self):
        clock=[0.];original=json.dumps
        def guard():
            if clock[0]>=25:raise NativeUIError('Modeled operation deadline expired')
        def slow(value,*args,**kwargs):clock[0]=26.;return original(value,*args,**kwargs)
        with self.assertRaises(NativeUIError),scope(guard):
            with patch('ios.adapters.appium_adapter.json.dumps',side_effect=slow),patch('ios.adapters.appium_adapter.urlopen') as sending:
                try:self.send()
                finally:self.assertEqual(0,sending.call_count)
        self.assertEqual([],self.requests)
        self.send();self.assertEqual(1,len(self.requests))

    def test_original_native_post_helper_checks_context_without_an_object_callback(self):
        request=Request(self.driver.server_url+'/e2e-client-command.json',data=b'{}',method='POST')
        enabled=[True]
        with scope(lambda:enabled[0]):
            enabled[0]=False
            with patch('ios.adapters.feature_observation.build_opener') as opener:
                with self.assertRaises(NativeUIError):post_request(request,timeout=2)
                self.assertEqual(1,opener.call_count);opener.return_value.open.assert_not_called()
            enabled[0]=True
            with post_request(request,timeout=2) as response:self.assertEqual(dict(value=dict(received=True)),json.load(response))
        self.assertEqual([('/e2e-client-command.json',b'{}')],self.requests)

    def test_slow_native_opener_preparation_cannot_send_after_deadline(self):
        from ios.adapters import feature_observation
        clock=[0.];build=feature_observation.build_opener;opened=[]
        def slow(*args,**kwargs):
            opener=build(*args,**kwargs);clock[0]=26.;opened.append(opener)
            opener.open=unittest.mock.Mock(side_effect=AssertionError('Expired transport sent a command'))
            return opener
        request=Request(self.driver.server_url+'/e2e-client-command.json',data=b'{}',method='POST')
        with self.assertRaises(NativeUIError),scope(lambda:clock[0]<25):
            with patch.object(feature_observation,'build_opener',side_effect=slow):post_request(request,2)
        self.assertEqual(1,len(opened));opened[0].open.assert_not_called();self.assertEqual([],self.requests)
        with post_request(request,2) as response:
            self.assertEqual(dict(value=dict(received=True)),json.loads(response.read()))
        self.assertEqual(1,len(self.requests))


if __name__=='__main__':unittest.main()
