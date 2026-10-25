"""Actual WDA HTTP/PNG files when the later native capture clock is lost.

Prior page/source admission is an explicit model here; no native page, capture
timing or whole-feature result is claimed. The actual unchanged WDA transport,
screen owner, raw fragments and interrupted ownership journals execute normally.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from io import BytesIO
import json
from pathlib import Path
from threading import Thread
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch
from PIL import Image
from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import unpack
from adapters.script_feature.lock import ScriptSourceLock
from ios.adapters.appium_adapter import WebDriver
from ios.adapters.tablet_web_samples import TabletWebSamples
from self_tests.test_completed_frame_lease import BINDING,RUN


class TabletWebSamplesInterruptedTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.root=Path(temp.name);self.root.chmod(0o700)
        self.artifacts=self.root/'artifacts';self.artifacts.mkdir(mode=0o700)
        self.lock=ScriptSourceLock(self.root/'script-feature-sources.lock');held=self.lock.held();held.__enter__();self.addCleanup(held.__exit__,None,None,None)
        self.clock=0.;self.native_calls=0;self.gets=[];self.delay=.05;self.owner=None
        image=Image.new('RGB',(320,200),(20,40,60));stream=BytesIO();image.save(stream,format='PNG');self.raw=stream.getvalue();outer=self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*_args):pass
            def do_GET(self):
                outer.gets.append(self.path);outer.clock+=outer.delay
                raw=json.dumps(dict(value=base64.b64encode(outer.raw).decode())).encode()
                self.send_response(200);self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=Thread(target=server.serve_forever,daemon=True);thread.start()
        self.addCleanup(thread.join);self.addCleanup(server.server_close);self.addCleanup(server.shutdown)
        def bound():self.lock.assert_held();return True
        source=SimpleNamespace(root=self.root,binding=BINDING,run=RUN,role='primary',lock=self.lock,bound=bound,guard=bound,
            epoch_ms=lambda:1700000000000+round(self.clock*1000),monotonic=lambda:self.clock)
        def native():
            self.native_calls+=1
            if self.native_calls==2:
                need(self.owner.state['pending']['archive']['complete'])
                need(self.owner.raw.read(self.owner.state['pending']['archive'])==self.raw)
                raise OSError('Modeled later native clock return lost after actual PNG bytes')
            return 1700086400000+round(self.clock*1000)
        self.runtime=SimpleNamespace(observer=SimpleNamespace(source=source),client=WebDriver('http://127.0.0.1:'+str(server.server_port)),
            native_clock=native,tail_source=lambda:dict(testOnlyPriorPageAuthority=True),validate_tail_source=lambda _value:dict(row={},frame={}))
        self.policy=dict(source='native-screen',marker=[0,0,128,32],subject=[0,40,160,90])
    def make(self):return TabletWebSamples(self.runtime,self.artifacts,self.policy)
    def test_actual_returned_PNG_is_immutable_before_lost_native_after_and_never_GET_replayed(self):
        self.owner=self.make()
        with patch('ios.adapters.tablet_web_samples.page_frame',return_value={'testOnlyPriorPageAuthority':True}):
            with self.assertRaises((OSError,NativeUIError)):self.owner.capture('b'*32)
        row=deepcopy(self.owner.state['pending']);self.assertEqual('failed',row['status']);self.assertIsNone(row['png'])
        self.assertEqual(self.raw,self.owner.raw.read(row['archive']));self.assertEqual(2,self.native_calls)
        rebuilt=self.make()
        with self.assertRaises(NativeUIError):rebuilt.capture('b'*32)
        self.assertEqual(['/session/'+BINDING['sessionId']+'/screenshot'],self.gets)
        self.assertTrue(rebuilt.cleanup_files());rebuilt.files_absent()
        self.assertEqual(self.raw,rebuilt.raw.read(row['archive']))
        original=PrivateFeatureState(self.root/('tabletweb-screen-owner-'+RUN+'-primary.json')).read()
        self.assertTrue(all(item['phase']=='removed' for item in unpack(original['transcript'])))
    def test_slow_actual_WDA_return_retains_bytes_without_another_native_or_HTTP_send(self):
        self.delay=2.;self.owner=self.make()
        with patch('ios.adapters.tablet_web_samples.page_frame',return_value={'testOnlyPriorPageAuthority':True}):
            with self.assertRaises(NativeUIError):self.owner.capture('b'*32)
        row=self.owner.state['pending'];self.assertEqual('failed',row['status']);self.assertEqual(1,self.native_calls)
        self.assertEqual(self.raw,self.owner.raw.read(row['archive']));self.assertEqual(1,len(self.gets))
        with self.assertRaises(NativeUIError):self.make().capture('b'*32)
        self.assertEqual(1,len(self.gets))


if __name__=='__main__':unittest.main()
