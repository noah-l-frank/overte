"""Actual owned HTTP scene inputs; no client, avatar or renderer claims."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
import threading
import unittest
from urllib.request import urlopen,Request
from urllib.error import HTTPError
from feature_journeys.emote_resources import EmoteResources,RESOURCE,validate_status
from feature_journeys.navigation_scene import scene,marker_id
from feature_journeys.server import make_server
from feature_journeys.witness import Client
from adapters.feature_fixture_access import AdapterFixtureClient

READER='r'*64;ACTOR='a'*64;ADAPTER='d'*64


class EmoteResourcesTests(unittest.TestCase):
    def setUp(self):
        self.server=make_server(READER,ACTOR,adapter_token=ADAPTER)
        self.url='http://127.0.0.1:'+str(self.server.server_address[1])+'/feature-fixture/v1'
        self.resources=EmoteResources(self.url);self.server.emote_resources=self.resources
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.addCleanup(self.stop)
        self.reader=Client(self.url,READER);self.run,self.root=self.reader.register('emotes')
        self.ticket='b'*32;self.reader.activate(self.ticket)
    def stop(self):self.server.shutdown();self.server.server_close();self.thread.join(timeout=2)
    def fetch(self,url):
        with urlopen(url,timeout=2) as response:return response.status,response.read(),response.headers
    def status(self,nonce='e'*32,previous=None):
        value=self.reader.request('/runs/'+self.run+'/emotes',emote_nonce=nonce)
        validate_status(value,instance=self.resources.instance,run=self.run,url=self.url,request=nonce,previous=previous)
        return value
    def test_normal_scene_input_contains_actual_polled_marker_but_no_avatar_animation_setter(self):
        url=self.root+'tickets/'+self.ticket+'/'+RESOURCE+'?location=/0,0,4/0,0,0,1'
        status,raw,headers=self.fetch(url);self.assertEqual(200,status)
        self.assertEqual(scene(self.run,self.ticket,self.root),json.loads(raw))
        self.assertEqual(6,len(json.loads(raw)['Entities']))
        self.assertIn(marker_id(self.run),raw.decode());self.assertNotIn('overrideAnimation',raw.decode())
        value=self.status();receipt=value['responses'][-1]
        self.assertEqual(hashlib.sha256(raw).hexdigest(),receipt['sha256']);self.assertEqual(len(raw),receipt['bytes'])
        self.assertEqual(headers['X-Overte-Fixture-Response'],receipt['responseId'])
    def test_scene_bytes_stay_bound_to_first_ticket_while_real_marker_polls_current_phase(self):
        url=self.root+'tickets/'+self.ticket+'/'+RESOURCE
        _,first,_=self.fetch(url);before=self.status();self.reader.activate('c'*32,verb='open',inputs={})
        _,second,_=self.fetch(url);self.assertEqual(first,second)
        value=self.status('f'*32,before);self.assertEqual(self.ticket,value['sceneTicket']);self.assertEqual('c'*32,value['ticket'])
        with self.assertRaises(HTTPError) as error:self.fetch(self.root+'tickets/'+'c'*32+'/'+RESOURCE)
        self.assertEqual(404,error.exception.code);error.exception.close()
        _,current,_=self.fetch(self.root+'current');self.assertEqual('c'*32,json.loads(current)['ticket'])
    def test_adapter_reads_original_scene_status_but_cannot_publish_or_activate(self):
        source=AdapterFixtureClient(self.url,ADAPTER)
        value=source.request('/runs/'+self.run+'/emotes',emote_nonce='e'*32)
        self.assertEqual(self.ticket,value['sceneTicket']);self.assertNotIn('entries',value)
        with self.assertRaises(RuntimeError):source.request('/runs/'+self.run+'/active',dict(ticket='f'*32))
    def test_retirement_joins_actual_response_and_prevents_future_scene_delivery(self):
        url=self.root+'tickets/'+self.ticket+'/'+RESOURCE;self.fetch(url);before=self.status();self.reader.close()
        value=self.status('f'*32,before);self.assertFalse(value['active']);self.assertIsNone(value['ticket'])
        self.assertEqual(before['responses'],value['responses'])
        with self.assertRaises(HTTPError) as error:self.fetch(url)
        error.exception.close()
    def test_wrong_origin_unknown_nonce_or_unobserved_socket_write_is_not_success(self):
        run='1'*32;provider=EmoteResources(self.url);provider.provision(run);provider.activate(run,'2'*32)
        with self.assertRaises(ValueError):
            with provider.response(run,'2'*32,request_authority='foreign.test',request_scheme='http'):pass
        with self.assertRaises(ValueError):
            with provider.response(run,'2'*32,request_authority=self.url.split('/')[2],request_scheme='http'):pass
        self.assertEqual(1,provider.failed);self.assertFalse(provider.snapshot(run,'3'*32)['healthy'])

if __name__=='__main__':unittest.main()
