"""Real ordinary feet/orientation URL input stays separate from resource bytes."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import hashlib
from pathlib import Path
import secrets
import sys
import threading
import unittest
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import urlopen
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from feature_journeys.graphics_resources import GraphicsResources,viewpoint_query
from feature_journeys.server import make_server
from feature_journeys.witness import Client


class ViewpointQueryTests(unittest.TestCase):
    def test_only_one_bounded_finite_normalized_viewpoint_is_admitted(self):
        for value in ('location=/0,0,0/0,0,0,1','location='+quote('/-1.25,2e2,.5/0,0,0,1',safe='')):
            self.assertTrue(viewpoint_query(value))
        for value in ('','location=','location=/0,0,0/0,0,0,0','location=/nan,0,0/0,0,0,1',
                      'location=/1e309,0,0/0,0,0,1','location=/1000001,0,0/0,0,0,1',
                      'location=/1_0,0,0/0,0,0,1','location=/0,0,0/0,0,0,1&expectedScale=.5',
                      'location=/0,0,0/0,0,0,1&location=/0,0,0/0,0,0,1','other=/0,0,0/0,0,0,1'):
            with self.subTest(value=value):self.assertFalse(viewpoint_query(value))

    def test_actual_http_query_preserves_original_scene_body_and_socket_receipts(self):
        server=make_server(secrets.token_hex(32),secrets.token_hex(32));origin='http://127.0.0.1:'+str(server.server_port)
        server.graphics_resources=GraphicsResources(origin+'/feature-fixture/v1')
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            client=Client(origin+'/feature-fixture/v1',server.reader_token);run,fixture=client.register('graphics');ticket=secrets.token_hex(16);client.activate(ticket)
            scene=fixture+'tickets/'+ticket+'/graphics-scene.v1.json'
            with urlopen(scene,timeout=3) as response:original=response.read()
            with urlopen(scene+'?location='+quote('/0,-.2,0/0,0,0,1',safe=''),timeout=3) as response:located=response.read()
            self.assertEqual(original,located);status=client.graphics_status();self.assertEqual(2,len(status['responses']))
            self.assertEqual({hashlib.sha256(original).hexdigest()},{row['sha256'] for row in status['responses']})
            for path in (scene+'?expectedScale=.5',scene+'?location=/0,0,0/0,0,0,1&extra=1',
                         fixture+'tickets/'+ticket+'/marker.png?location=/0,0,0/0,0,0,1'):
                try:urlopen(path,timeout=3)
                except HTTPError as error:
                    self.assertEqual(404,error.code);error.close()
                else:self.fail('Foreign query grammar reached a resource')
            self.assertEqual(2,len(client.graphics_status()['responses']));client.close()
        finally:server.shutdown();thread.join(3);server.server_close()


if __name__=='__main__':unittest.main()
