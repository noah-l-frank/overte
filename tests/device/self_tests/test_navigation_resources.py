"""Actual local HTTP fixture and reader checks; no Overte client/device runs."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import secrets
import sys
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request,urlopen
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from feature_journeys.navigation_fixture import NavigationResources,configuration,validate_status,DIRECTORY,QUERY,DIRECTORY_MARKER
from feature_journeys.server import make_server
from feature_journeys.witness import Client
from feature_journeys.fixtures import context
from navigation_observation import viewpoint_urls

INPUTS=dict(protocolSignature='AAAAAAAAAAAAAAAAAAAAAA==',sourceRevision='a'*40,sceneUrl='http://controlled.invalid/scene.json')
TICKET='b'*32


class NavigationResourcesTests(unittest.TestCase):
    def setUp(self):
        self.reader,self.actor=secrets.token_hex(32),secrets.token_hex(32)
        self.provider=NavigationResources(INPUTS)
        self.server=make_server(self.reader,self.actor,navigation_resources=self.provider)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.origin=f'http://127.0.0.1:{self.server.server_port}'
        self.client=Client(self.origin+'/feature-fixture/v1',self.reader)
        self.addCleanup(self.stop)
    def stop(self):
        self.server.shutdown();self.server.server_close();self.thread.join(timeout=2)
        self.assertFalse(self.thread.is_alive());self.assertEqual(0,self.server.internal_errors)
    def open(self):
        run,_url=self.client.register('world-navigation');self.client.activate(TICKET)
        return run
    def fetch(self,path):
        try:
            with urlopen(self.origin+path,timeout=2) as response:return response.status,response.read(),response.headers.get('X-Overte-Fixture-Response')
        except HTTPError as error:
            try:return error.code,error.read(),error.headers.get('X-Overte-Fixture-Response')
            finally:error.close()

    def test_actual_directory_and_owned_named_404_have_original_byte_receipts_and_cleanup(self):
        run=self.open();status,raw,response=self.fetch(DIRECTORY+'?'+QUERY)
        self.assertEqual(200,status);record=json.loads(raw)['data']['places'][0]
        self.assertEqual(context(run)['name'],record['name']);self.assertEqual(context(run)['destination'],record['id'])
        self.assertEqual(INPUTS['protocolSignature'],record['domain']['protocol_version'])
        self.assertEqual(viewpoint_urls(INPUTS['sceneUrl'])['B'],record['address'])
        source=self.client.navigation_status();self.assertEqual(1,len(source['responses']))
        receipt=source['responses'][0]
        self.assertEqual(response,receipt['responseId']);self.assertEqual(len(raw),receipt['bytes'])
        self.assertEqual(hashlib.sha256(raw).hexdigest(),receipt['sha256']);self.assertEqual(TICKET,receipt['ticket'])
        self.client.activate('c'*32,'navigate-missing',{})
        status,raw,response=self.fetch(DIRECTORY+'/'+context(run)['hidden']);self.assertEqual(404,status)
        source=self.client.navigation_status();last=source['responses'][-1]
        self.assertEqual('missing-name',last['kind']);self.assertEqual('c'*32,last['ticket'])
        self.assertEqual(hashlib.sha256(raw).hexdigest(),last['sha256']);self.assertEqual(response,last['responseId'])
        self.client.close();self.client.close()
        self.assertFalse(self.client.navigation_status()['active']);self.assertNotIn(run,self.server.journal.runs)
        self.assertEqual(404,self.fetch(DIRECTORY+'?'+QUERY)[0])

    def test_absent_provider_refuses_registration_before_a_run_exists(self):
        self.server.navigation_resources=None
        with self.assertRaises(ValueError):self.client.register('world-navigation')
        self.assertEqual({},self.server.journal.runs)
        request=Request(self.origin+'/feature-fixture/v1/runs',data=b'{"area":"world-navigation"}',
            headers={'Authorization':'Bearer '+self.reader,'Content-Type':'application/json'})
        with self.assertRaises(HTTPError) as caught:urlopen(request,timeout=2)
        self.assertEqual(503,caught.exception.code);caught.exception.close();self.assertEqual({},self.server.journal.runs)

    def test_each_real_response_has_an_independent_materializable_marker_with_same_destination(self):
        self.open();originals=[]
        for _ in range(2):
            status,raw,response=self.fetch(DIRECTORY+'?'+QUERY);self.assertEqual(200,status)
            record=json.loads(raw)['data']['places'][0]
            self.assertEqual(DIRECTORY_MARKER+response,record['description']);originals.append((record,response,raw))
        first,second=originals
        for key in ('id','name','address'):self.assertEqual(first[0][key],second[0][key])
        self.assertNotEqual(first[0]['description'],second[0]['description'])
        self.assertNotEqual(first[1],second[1]);self.assertNotEqual(first[2],second[2])
        for receipt,(_,response,raw) in zip(self.client.navigation_status()['responses'],originals):
            self.assertEqual(response,receipt['responseId']);self.assertEqual(hashlib.sha256(raw).hexdigest(),receipt['sha256'])

    def test_original_service_error_prevents_navigation_readiness(self):
        self.server.internal_errors=1
        with self.assertRaises(ValueError):self.client.register('world-navigation')
        self.assertEqual({},self.server.journal.runs)
        self.server.internal_errors=0

    def test_foreign_queries_names_and_conflicting_run_do_not_receive_owned_directory(self):
        run=self.open()
        for path in (DIRECTORY,DIRECTORY+'?status=offline&per_page=1000',DIRECTORY+'/foreign',DIRECTORY+'/'+context(run)['hidden']+'?other=1'):
            self.assertEqual(404,self.fetch(path)[0])
        self.assertEqual([],self.client.navigation_status()['responses'])
        foreign=Client(self.origin+'/feature-fixture/v1',self.reader)
        with self.assertRaises(ValueError):foreign.register('world-navigation')
        self.assertEqual({run},set(self.server.journal.runs))
        request=Request(self.origin+'/feature-fixture/v1/runs',data=b'{"area":"world-navigation"}',
            headers={'Authorization':'Bearer '+self.actor,'Content-Type':'application/json'})
        with self.assertRaises(HTTPError) as caught:urlopen(request,timeout=2)
        code=caught.exception.code;caught.exception.close();self.assertEqual(404,code);self.client.close()

    def test_immutable_history_and_foreign_provider_cannot_be_adopted(self):
        run=self.open();self.fetch(DIRECTORY+'?'+QUERY);before=self.client.navigation_status();after=deepcopy(before)
        for mutate in (lambda v:v['responses'][0].update(sha256='f'*64),lambda v:v.update(responses=[]),
                       lambda v:v.update(capturedEpochMs=1),lambda v:v.update(instance='f'*32),
                       lambda v:v.update(failedResponses=1),lambda v:v.update(navigationProviderVersion=True)):
            after=deepcopy(before);mutate(after)
            with self.subTest(value=after),self.assertRaises(ValueError):
                validate_status(after,instance=before['instance'],run=run,inputs=INPUTS,previous=before)
        self.provider.instance='e'*32
        with self.assertRaises(ValueError):self.client.navigation_status()

    def test_failed_actual_write_and_unfinished_cleanup_cannot_be_success(self):
        run=self.open()
        with self.assertRaises(OSError):
            with self.provider.response(DIRECTORY,QUERY) as response:
                self.assertIsNotNone(response);raise OSError('Synthetic failed socket boundary')
        self.assertEqual([],self.provider.snapshot(run)['responses']);self.assertFalse(self.provider.ready()['ready'])
        with self.assertRaises(ValueError):self.client.navigation_status()
        other=NavigationResources(INPUTS);other.provision('d'*32);other.activate('d'*32,TICKET)
        with patch.object(self.provider,'retire',return_value=None):
            with self.assertRaises(ValueError):self.client.close()
        self.assertFalse(getattr(self.client,'closed',False));self.assertTrue(self.provider.snapshot(run)['active'])

    def test_cleanup_ack_without_retired_actual_ownership_is_rejected_independently(self):
        run=self.open();self.client.navigation_status()
        with patch.object(self.provider,'retire',return_value=None):
            with self.assertRaisesRegex(ValueError,'cleanup is incomplete'):self.client.close()
        self.assertFalse(self.client.closed);self.assertTrue(self.provider.snapshot(run)['active'])
        self.assertEqual(0,self.provider.failed)
        self.provider.retire(run)

    def test_configuration_is_original_bounded_input_and_clock_regression_poison_is_retained(self):
        for changes in ({'protocolSignature':'foreign'},{'protocolSignature':'A'*23+'='},{'sourceRevision':'main'},
                        {'sceneUrl':'http://controlled.invalid/scene.json?location=/2,0,4'},{'expected':'pass'}):
            with self.subTest(changes=changes),self.assertRaises(ValueError):configuration({**INPUTS,**changes})
        clock=[100];source=NavigationResources(INPUTS,clock_ms=lambda:clock[0]);source.provision('d'*32)
        clock[0]=99
        with self.assertRaises(ValueError):source.ready()
        clock[0]=101;self.assertFalse(source.ready()['ready'])
        with self.assertRaises(ValueError):source.provision('e'*32)


if __name__=='__main__':unittest.main()
