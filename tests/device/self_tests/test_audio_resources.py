"""Original loopback Audio HTTP input counterexamples; no product acceptance."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
from pathlib import Path
import secrets
import sys
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request,urlopen
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from feature_journeys.audio_resources import AudioResources,RESOURCE,pcm_input,validate_status
from feature_journeys.server import make_server
from feature_journeys.witness import Client

TICKET='b'*32


class AudioResourcesTests(unittest.TestCase):
    def setUp(self):
        self.reader,self.actor=secrets.token_hex(32),secrets.token_hex(32)
        self.server=make_server(self.reader,self.actor)
        self.url='http://127.0.0.1:'+str(self.server.server_port)+'/feature-fixture/v1'
        self.provider=AudioResources(self.url);self.server.audio_resources=self.provider
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start();self.addCleanup(self.stop)
        self.client=Client(self.url,self.reader);self.run,self.root=self.client.register('audio');self.client.activate(TICKET)

    def stop(self):
        self.server.shutdown();self.server.server_close();self.thread.join(2)
        self.assertFalse(self.thread.is_alive());self.assertEqual(0,self.server.internal_errors)

    def status(self,previous=None):
        request=secrets.token_hex(16);value=self.client.request('/runs/'+self.run+'/audio',audio_nonce=request)
        return validate_status(value,instance=self.provider.instance,run=self.run,url=self.url,request=request,previous=previous)

    def fetch(self,ticket=TICKET,host=None):
        request=Request(self.root+'tickets/'+ticket+'/'+RESOURCE,headers={} if host is None else {'Host':host})
        try:
            with urlopen(request,timeout=2) as response:return response.status,response.read(),response.headers
        except HTTPError as error:
            try:return error.code,error.read(),error.headers
            finally:error.close()

    def test_real_socket_originals_match_delivered_pcm_and_distinct_challenge_bytes(self):
        first=self.status();self.assertEqual([],first['responses'])
        status,body,headers=self.fetch();self.assertEqual(200,status);self.assertEqual(pcm_input(self.run,TICKET),body)
        observed=self.status(first);row=observed['responses'][0]
        self.assertEqual(headers['X-Overte-Fixture-Response'],row['responseId'])
        self.assertEqual(hashlib.sha256(body).hexdigest(),row['sha256']);self.assertEqual(144000,row['bytes'])
        self.assertEqual('no-store',headers['Cache-Control'])
        self.client.activate('c'*32,'open');self.assertEqual(404,self.fetch()[0])
        other=self.fetch('c'*32)[1];self.assertNotEqual(body,other);self.status(observed)

    def test_foreign_origin_unregistered_and_retired_tickets_cannot_deliver_input(self):
        self.assertEqual(400,self.fetch(host='foreign.invalid:80')[0]);self.assertEqual(404,self.fetch('d'*32)[0])
        self.client.close();self.assertEqual(400,self.fetch()[0]);self.assertFalse(self.status()['active'])

    def test_status_requires_a_new_nonce_and_preserves_original_retirement(self):
        with self.assertRaises(ValueError):self.client.request('/runs/'+self.run+'/audio')
        first=self.status();self.client.close();last=self.status(first)
        changed=deepcopy(last);changed['active']=True;changed['ticket']=TICKET
        with self.assertRaises(ValueError):validate_status(changed,instance=self.provider.instance,run=self.run,url=self.url,request=changed['requestId'],previous=last)

    def test_altered_or_truncated_original_http_history_is_rejected(self):
        self.fetch();first=self.status()
        for fault in ('sha256','bytes','authority','ticket','sequence','time','drop'):
            with self.subTest(fault=fault):
                value=self.status();row=value['responses'][0]
                if fault=='sha256':row['sha256']='0'*64
                elif fault=='bytes':row['bytes']-=2
                elif fault=='authority':row['requestAuthority']='foreign:80'
                elif fault=='ticket':row['ticket']='d'*32
                elif fault=='sequence':row['sequence']=True
                elif fault=='time':row['startedEpochMs']=0
                else:value['responses']=[]
                with self.assertRaises(ValueError):validate_status(value,instance=self.provider.instance,run=self.run,url=self.url,request=value['requestId'],previous=first)

    def test_unwritten_response_cannot_create_success_or_be_reused(self):
        with self.assertRaises(ValueError):
            with self.provider.response(self.run,TICKET,request_authority=self.url.split('/')[2],request_scheme='http') as response:
                self.assertEqual(200,response[0])
        self.assertEqual(1,self.provider.failed);self.assertEqual([],self.provider.runs[self.run]['responses'])
        self.assertFalse(self.provider.ready()['ready']);self.assertEqual(404,self.fetch()[0])


if __name__=='__main__':unittest.main()
