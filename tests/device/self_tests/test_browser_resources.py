"""Actual owned HTTP stimuli and original parity bytes, without a browser/device."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import hashlib
import json
from pathlib import Path
import secrets
import sys
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from feature_journeys.browser_fixture import BrowserResources,ROOT
from feature_journeys.fixtures import payload
from feature_journeys.server import make_server
from feature_journeys.witness import Client

TICKET='a'*32


class BrowserResourcesTests(unittest.TestCase):
    def setUp(self):
        self.reader,self.actor=secrets.token_hex(32),secrets.token_hex(32)
        self.primary=make_server(self.reader,self.actor)
        self.peer=make_server(self.reader,self.actor,browser_peer_of=self.primary)
        for server in (self.primary,self.peer):
            worker=threading.Thread(target=lambda s=server:s.serve_forever(poll_interval=.01),daemon=True)
            worker.start();self.addCleanup(self.stop,server,worker)
        self.base=f'http://127.0.0.1:{self.primary.server_port}/feature-fixture/v1'
        self.foreign=f'http://127.0.0.1:{self.peer.server_port}/feature-fixture/v1'
        self.client=Client(self.base,self.reader);self.run,_=self.client.register('world-web');self.client.activate(TICKET)
        self.path=f'/runs/{self.run}/tickets/{TICKET}/'

    def stop(self,server,worker):
        server.shutdown();server.server_close();worker.join(timeout=2);self.assertFalse(worker.is_alive())

    def fetch(self,path,*,foreign=False,token=None,value=None,headers=None):
        metadata={} if headers is None else dict(headers)
        if token is not None:metadata['Authorization']='Bearer '+token
        request=Request((self.foreign if foreign else self.base)+path,
            data=None if value is None else json.dumps(value).encode(),headers=metadata)
        try:
            response=urlopen(request,timeout=2)
        except HTTPError as error:
            response=error
        with response:return response.status,response.headers,response.read()

    def snapshot(self):
        status,_,raw=self.fetch('/runs/'+self.run+'/browser',token=self.reader)
        self.assertEqual(200,status);return json.loads(raw)

    def test_original_page_and_real_echo_scripts_replace_dom_copy_stubs(self):
        status,headers,body=self.fetch(self.path+'reference.html')
        self.assertEqual(200,status);self.assertIn(b'id="text"',body);self.assertIn(b'id="bridge"',body)
        self.assertIn(b'href="page-b.html"',body);self.assertIn(b'href="recovery.html"',body)
        self.assertNotIn(b'owned-text',body);self.assertNotIn(b'{text:v}',body)
        self.assertIn(headers['X-Overte-Fixture-Response'].encode(),body)
        for name in ('reference.js','client.js','injected.js'):
            status,_,raw=self.fetch(self.path+name)
            self.assertEqual(200,status);self.assertEqual((ROOT/name).read_bytes(),raw)
        status,_,marker=self.fetch(self.path+'feature-marker.js')
        self.assertEqual(200,status);self.assertIn(b'/current',marker);self.assertNotIn(b'EventBridge',marker)
        source=self.snapshot();self.assertEqual(5,source['sequence'])
        self.assertEqual(hashlib.sha256(body).hexdigest(),source['responses'][0]['sha256'])
        self.assertEqual(len(body),source['responses'][0]['bytes'])

    def test_unrestored_404_stays_404_on_real_reloads_with_distinct_response_ids(self):
        replies=[self.fetch(self.path+'recovery.html') for _ in range(3)]
        self.assertEqual([404]*3,[r[0] for r in replies])
        self.assertEqual(3,len({r[1]['X-Overte-Fixture-Response'] for r in replies}))
        self.assertTrue(all(b'recovery unavailable' in r[2] for r in replies))
        self.assertFalse(self.snapshot()['ready'])
        self.assertEqual([404]*3,[r['status'] for r in self.snapshot()['responses']])

    def test_actual_restore_does_not_change_previous_body_or_invent_a_loaded_document(self):
        _,_,before=self.fetch(self.path+'recovery.html');original=before[:];sequence=self.snapshot()['sequence']
        status,_,_=self.fetch('/runs/'+self.run+'/browser/control',token=self.reader,value={'operation':'restore-resource'})
        self.assertEqual(200,status);self.assertTrue(self.snapshot()['ready'])
        self.assertEqual(sequence,self.snapshot()['sequence']) # No request/navigation fabricated by control.
        self.assertEqual(original,before);self.assertIn(b'recovery unavailable',before)
        status,_,after=self.fetch(self.path+'recovery.html');self.assertEqual(200,status)
        self.assertIn(b'recovery available',after);self.assertNotEqual(before,after)
        self.assertEqual([404,200],[r['status'] for r in self.snapshot()['responses']])
        status,_,_=self.fetch('/runs/'+self.run+'/browser/control',token=self.reader,value={'operation':'restore-resource'})
        self.assertEqual(400,status) # An uncertain control input is not replayable.

    def test_actual_second_origin_serves_same_original_protocol_without_cooperative_filter(self):
        self.assertNotEqual(self.primary.server_port,self.peer.server_port)
        status,_,body=self.fetch(self.path+'reference.html',foreign=True)
        self.assertEqual(200,status);self.assertIn(b'id="bridge"',body)
        status,_,script=self.fetch(self.path+'client.js',foreign=True)
        self.assertEqual(200,status);self.assertEqual((ROOT/'client.js').read_bytes(),script)
        self.assertEqual(['foreign','foreign'],[r['origin'] for r in self.snapshot()['responses']])
        # A server response is not an observed normal click or native rejection.
        self.assertEqual([],self.client.observe()['entries'])

    def test_second_origin_is_resource_only_even_with_reader_or_publisher_tokens(self):
        for path,value in (('/runs',{'area':'chat'}),('/runs/'+self.run+'/browser/control',{'operation':'restore-resource'}),
                           ('/runs/'+self.run+'/samples',{}),('/runs/'+self.run+'/active',{}),('/account-provider',None),
                           ('/runs/'+self.run+'/browser',None)):
            for token in (self.reader,self.actor):
                with self.subTest(path=path):
                    self.assertEqual(404,self.fetch(path,foreign=True,token=token,value=value)[0])
        self.assertFalse(self.snapshot()['ready'])

    def test_wrong_role_expected_state_or_unknown_control_cannot_restore_resource(self):
        control='/runs/'+self.run+'/browser/control'
        for token,value,status in ((None,{'operation':'restore-resource'},403),
            (self.actor,{'operation':'restore-resource'},403),
            (self.reader,{'operation':'restore-resource','expected':200},400),
            (self.reader,{'operation':'set-status','status':200},400)):
            self.assertEqual(status,self.fetch(control,token=token,value=value)[0])
        self.assertFalse(self.snapshot()['ready']);self.assertEqual(404,self.fetch(self.path+'recovery.html')[0])

    def test_unknown_run_ticket_and_retired_owner_do_not_serve_browser_bytes(self):
        self.assertEqual(400,self.fetch('/runs/'+'f'*32+'/tickets/'+TICKET+'/reference.html')[0])
        self.assertEqual(404,self.fetch('/runs/'+self.run+'/tickets/'+'f'*32+'/reference.html')[0])
        self.client.close();self.assertFalse(self.primary.browser_resources.has_run(self.run))
        self.assertEqual(400,self.fetch(self.path+'reference.html')[0])
        self.assertEqual(404,self.fetch(self.path+'reference.html',foreign=True)[0])

    def test_http_inline_stub_is_absent_and_original_media_range_transport_is_reused(self):
        self.assertIsNone(payload('inline.html',self.run,TICKET))
        self.assertEqual(404,self.fetch(self.path+'inline.html')[0])
        status,headers,body=self.fetch(self.path+'reference.mp4',headers={'Range':'bytes=17-33'})
        self.assertEqual(206,status);self.assertEqual((ROOT/'reference.mp4').read_bytes()[17:34],body)
        self.assertTrue(headers['Content-Range'].startswith('bytes 17-33/'))

    def test_source_copy_clock_regression_and_inventory_limit_are_fail_closed(self):
        clock=[20000];source=BrowserResources(clock_ms=lambda:clock[0]);source.open(self.run)
        source.resource(self.run,TICKET,'reference.html',origin='primary')
        changed=source.snapshot(self.run);changed['responses'].clear()
        self.assertEqual(1,len(source.snapshot(self.run)['responses']))
        clock[0]=19999
        with self.assertRaises(ValueError):source.resource(self.run,TICKET,'reference.html',origin='primary')
        clock[0]=20000
        for _ in range(255):source.resource(self.run,TICKET,'reference.js',origin='primary')
        with self.assertRaises(ValueError):source.resource(self.run,TICKET,'reference.html',origin='primary')
        self.assertEqual(256,source.snapshot(self.run)['sequence'])

    def test_unreviewed_or_missing_original_source_does_not_publish_a_response_receipt(self):
        with patch('feature_journeys.browser_fixture.pinned_resource',side_effect=ValueError('source digest differs')):
            self.assertEqual(400,self.fetch(self.path+'reference.html')[0])
        self.assertEqual(0,self.snapshot()['sequence'])


if __name__=='__main__':unittest.main()
