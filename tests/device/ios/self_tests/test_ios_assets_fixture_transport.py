"""Real owned loopback HTTP fixture bounds, without an AssetServer or devices."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
from http.server import ThreadingHTTPServer
import json
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request,urlopen
from fixture.serve import FixtureHandler,FixtureState
from ios.self_tests.assets_reply_fixture import RUN,TICKET


class AssetsFixtureTransportTests(unittest.TestCase):
    def setUp(self):
        class Handler(FixtureHandler):
            def log_message(self,*args):pass
        self.server=ThreadingHTTPServer(('127.0.0.1',0),Handler);self.server.fixture_state=FixtureState()
        self.thread=threading.Thread(target=lambda:self.server.serve_forever(poll_interval=.01),daemon=True);self.thread.start()
        self.addCleanup(self.close);self.url='http://127.0.0.1:'+str(self.server.server_address[1])+'/e2e-client-command.json'
    def close(self):
        self.server.shutdown();self.server.server_close();self.thread.join(2);self.assertFalse(self.thread.is_alive())
    def post(self,command,*,padded=None):
        raw=json.dumps(command).encode()
        if padded is not None:
            self.assertGreaterEqual(padded,len(raw));raw+=b' '*(padded-len(raw))
        with urlopen(Request(self.url,data=raw,headers={'Content-Type':'application/json'}),timeout=5) as response:
            return json.loads(response.read(131073))
    def staged(self):
        # Independent bounded input bytes test the carrier gate only. They are
        # not claimed to parse as a model or to have been staged by a client.
        body=base64.b64encode(b'x'*10000).decode()
        return dict(schemaVersion=1,commandId='ios-'+'c'*32,action='feature-ios-assets-files',operation='stage',
            runId=RUN,ticket=TICKET,ownerToken='a'*64,resource='gltf-bundle/main.gltf',
            files={'main.gltf':body,'mesh/triangle.bin':body,'textures/checker.png':body})
    def reply(self):
        return dict(schemaVersion=1,commandId='ios-'+'d'*32,action='feature-ios-assets-replies',operation='inventory',
            runId=RUN,ticket=TICKET,ownerToken='b'*64,resource='gltf-bundle/main.gltf',namespace='original')

    def test_original_large_closed_assets_input_crosses_legacy_four_kib_gate_unchanged(self):
        query=self.staged();self.assertGreater(len(json.dumps(query).encode()),4096)
        self.assertEqual(query,self.post(query));self.assertEqual(query,self.server.fixture_state.snapshot_client_command())

    def test_reply_carrier_ceiling_is_eight_kib_and_refusal_preserves_last_command(self):
        query=self.reply();self.assertEqual(query,self.post(query,padded=8192));before=self.server.fixture_state.snapshot_client_command()
        with self.assertRaises(HTTPError) as caught:self.post(query,padded=8193)
        self.assertEqual(400,caught.exception.code);caught.exception.close();self.assertEqual(before,self.server.fixture_state.snapshot_client_command())

    def test_input_body_ceiling_and_unknown_fields_cannot_mutate_fixture_state(self):
        before=self.server.fixture_state.snapshot_client_command()
        for query,padded in ((self.staged(),131073),(dict(self.staged(),expectedUpload=True),None)):
            with self.subTest(padded=padded),self.assertRaises(HTTPError) as caught:self.post(query,padded=padded)
            self.assertEqual(400,caught.exception.code);caught.exception.close();self.assertEqual(before,self.server.fixture_state.snapshot_client_command())

    def test_legacy_four_kib_gate_is_not_expanded_for_foreign_actions_or_paths(self):
        before=self.server.fixture_state.snapshot_client_command();query=self.reply();query['action']='feature-unowned-assets'
        with self.assertRaises(HTTPError) as caught:self.post(query,padded=5000)
        self.assertEqual(400,caught.exception.code);caught.exception.close()
        query=self.staged();query['files']['../foreign']=query['files'].pop('main.gltf')
        with self.assertRaises(HTTPError) as caught:self.post(query)
        self.assertEqual(400,caught.exception.code);caught.exception.close();self.assertEqual(before,self.server.fixture_state.snapshot_client_command())


if __name__=='__main__':unittest.main()
