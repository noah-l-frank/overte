"""Actual loopback POST and factory/AFC pipeline; explicit native boundary."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
import threading
import unittest
from unittest.mock import patch
from ios.adapters import avatar_scripts,avatar_social_http
from ios.self_tests import avatar_callers2_fixture as current
from ios.self_tests.test_ios_avatar_transports import SourceBoundary
from ios.self_tests.test_ios_feature_observation import Native
from ios.self_tests.test_ios_avatar_scripts import packet as literal_scripts1,created as literal_created1
from ios.self_tests import test_ios_avatar_social_http as legacy_http
from self_tests.test_native_feature_observation import Boundary as NativeClockBoundary


class AvatarCallersTransportTests(unittest.TestCase):
    def transport(self,module,prototype,factory):
        native=Native();clock=NativeClockBoundary();source=SourceBoundary(prototype);requests=[]
        def stamp(value):
            source.native_clock();epoch=source.epoch()
            value.update(processId=42,capturedEpochMs=epoch,requestedEpochMs=epoch,animation={},animationFence={})
        clock.mutate=stamp
        class Handler(BaseHTTPRequestHandler):
            def do_POST(handler):
                if handler.path!='/e2e-client-command.json':handler.send_error(404);return
                raw=handler.rfile.read(int(handler.headers['Content-Length']));query=native.fixture.set_client_command(json.loads(raw))
                requests.append(raw);native.commands.append(deepcopy(query))
                (clock if query['action']=='feature-native-observe' else source).send(query)
                body=json.dumps(query).encode();handler.send_response(200);handler.send_header('Content-Type','application/json')
                handler.send_header('Content-Length',str(len(body)));handler.end_headers();handler.wfile.write(body)
            def log_message(*_args):pass
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        self.addCleanup(server.server_close)
        def close():server.shutdown();thread.join(timeout=2);self.assertFalse(thread.is_alive())
        self.addCleanup(close)
        native.target['testBuild']['fixtureOrigin']='http://127.0.0.1:'+str(server.server_port)
        observer=native.observer();observer.monotonic=lambda:source.clock;observer.sleep=source.sleep;observer.epoch_ms=lambda:9000
        def afc(session,operation,values):
            self.assertEqual(('native-session','mobile: pullFile'),(session,operation));path=values['remotePath']
            prefix='@org.example.client:documents/owned-results/'
            self.assertIn(path,(prefix+'feature-native-observation.json',prefix+module.FILE));native.reads.append(path)
            raw=clock.original() if path.endswith('/feature-native-observation.json') else source.original()
            return base64.b64encode(raw.encode()).decode()
        # post_request/opener/urlopen and the real FixtureState validator run
        # unchanged. Only the actual device/AFC boundary is explicitly modeled.
        with patch.object(native,'execute',side_effect=afc):
            reader=getattr(observer,factory)();result=reader.read('a'*32)
        self.assertEqual(source.last,result);self.assertEqual(3,len(requests));self.assertEqual(3,len(native.reads))
        self.assertEqual(['feature-native-observe',module.ACTION,'feature-native-observe'],[json.loads(raw)['action'] for raw in requests])
        self.assertEqual(3,len({json.loads(raw)['commandId'] for raw in requests}));self.assertNotEqual(9000,result['clockAfter']['epochMs'])
        self.assertLess(reader.acquisition['nativeRequestedEpochMs'],result['clockBefore']['epochMs'])
        self.assertGreater(reader.acquisition['nativeAfterEpochMs'],result['clockAfter']['epochMs']);return result

    def test_current_large_script2_original_tables_and_all_120_native_timer_ids_survive(self):
        original=current.timer_history2();value=self.transport(avatar_scripts,original,'avatar_scripts')
        self.assertEqual(2,value['iosAvatarScriptsVersion']);self.assertEqual(original['source'],value['source'])
        self.assertEqual(120,len(value['source']['workers'][0]['uiWork']['timers']))

    def test_current_social2_preserves_open_and_read_original_table_references(self):
        original=current.http2();value=self.transport(avatar_social_http,original,'avatar_social_http')
        self.assertEqual(2,value['iosAvatarSocialHttpVersion']);self.assertEqual(original['callerStacks'],value['callerStacks'])
        self.assertEqual(original['events'],value['events'])

    def test_public_component_readers_still_passively_read_unchanged_literal1(self):
        script=literal_scripts1();literal_created1(script);value=self.transport(avatar_scripts,script,'avatar_scripts')
        self.assertEqual(1,value['iosAvatarScriptsVersion']);self.assertEqual(script['source'],value['source'])
        logic=legacy_http.SocialHttpTests();logic.setUp();value=self.transport(avatar_social_http,logic.value,'avatar_social_http')
        self.assertEqual(1,value['iosAvatarSocialHttpVersion']);self.assertEqual(logic.value['events'],value['events'])
        self.assertNotIn('callerStacks',value)


if __name__=='__main__':unittest.main()
