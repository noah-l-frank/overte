"""Actual task-private loopback HTTP fixtures; no client/device qualification."""
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
from feature_journeys.graphics_resources import GraphicsResources,RESOURCE,fixture_url,validate_status
from feature_journeys.graphics_fixture import scene
from feature_journeys.server import Handler,make_server
from feature_journeys.witness import Client

TICKET='b'*32
NEXT='c'*32


class GraphicsResourcesTests(unittest.TestCase):
    def setUp(self):
        self.reader,self.actor=secrets.token_hex(32),secrets.token_hex(32)
        self.server=make_server(self.reader,self.actor)
        self.origin='http://127.0.0.1:'+str(self.server.server_port)
        self.url=self.origin+'/feature-fixture/v1'
        self.provider=GraphicsResources(self.url);self.server.graphics_resources=self.provider
        self.client=Client(self.url,self.reader)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.addCleanup(self.stop)

    def stop(self):
        self.server.shutdown();self.server.server_close();self.thread.join(timeout=2)
        self.assertFalse(self.thread.is_alive());self.assertEqual(0,self.server.internal_errors)

    def open(self):
        self.run,self.root=self.client.register('graphics');self.client.activate(TICKET)

    def fetch(self,path,*,token=None,value=None,method=None,host=None,nonce=None):
        headers={'Authorization':'Bearer '+token} if token else {}
        if host is not None:headers['Host']=host
        if nonce is not None:headers['X-Overte-Graphics-Read']=nonce
        request=Request(self.origin+path,data=json.dumps(value).encode() if value is not None else None,
            headers=headers,method=method)
        try:
            with urlopen(request,timeout=2) as response:
                return response.status,response.read(),response.headers
        except HTTPError as error:
            try:return error.code,error.read(),error.headers
            finally:error.close()

    def path(self,ticket=TICKET,run=None):
        return '/feature-fixture/v1/runs/'+(run or self.run)+'/tickets/'+ticket+'/'+RESOURCE

    def validate(self,value,previous=None):
        return validate_status(value,instance=self.provider.instance,run=self.run,url=self.url,
            request=value['requestId'],previous=previous)

    def test_original_socket_write_is_bound_to_actual_origin_stable_uuids_and_document_bytes(self):
        self.open();self.assertEqual([],self.client.graphics_status()['responses'])
        status,body,headers=self.fetch(self.path());self.assertEqual(200,status)
        self.assertEqual(scene(self.run,TICKET,self.root),json.loads(body))
        observed=self.client.graphics_status();row=observed['responses'][0]
        self.assertEqual(headers['X-Overte-Fixture-Response'],row['responseId'])
        self.assertEqual(hashlib.sha256(body).hexdigest(),row['sha256']);self.assertEqual(len(body),row['bytes'])
        self.assertEqual('no-store',headers['Cache-Control']);self.assertEqual(200,row['status'])
        self.assertNotIn('hazePass',body.decode());self.assertNotIn('expected',body.decode())

    def test_scene_ticket_remains_original_across_challenges_and_restart_reloads(self):
        self.open();first=self.fetch(self.path())[1];self.client.activate(NEXT,'open')
        second=self.fetch(self.path())[1];self.assertEqual(first,second)
        observed=self.client.graphics_status()
        self.assertEqual(TICKET,observed['sceneTicket']);self.assertEqual(NEXT,observed['ticket'])
        self.assertEqual([TICKET,NEXT],[r['activeTicket'] for r in observed['responses']])
        self.assertEqual(404,self.fetch(self.path(NEXT))[0])
        self.assertEqual(2,len(self.client.graphics_status()['responses']))

    def test_foreign_run_or_unregistered_ticket_cannot_allocate_a_scene(self):
        self.open()
        for path in (self.path(run='d'*32),self.path('e'*32)):
            with self.subTest(path=path):self.assertEqual(404,self.fetch(path)[0])
        self.assertEqual([],self.client.graphics_status()['responses'])

    def test_private_status_requires_read_authority_and_fresh_request_nonce(self):
        self.open();path='/feature-fixture/v1/runs/'+self.run+'/graphics'
        self.assertEqual(403,self.fetch(path,nonce='a'*32)[0])
        self.assertEqual(400,self.fetch(path,token=self.actor)[0])
        status,body,_=self.fetch(path,token=self.actor,nonce='a'*32)
        self.assertEqual(200,status);self.assertEqual('a'*32,json.loads(body)['requestId'])
        self.assertEqual(403,self.fetch('/feature-fixture/v1/runs/'+self.run+'/active',token=self.actor,
            value=dict(ticket=NEXT,verb='open',inputs={}))[0])
        self.assertEqual(403,self.fetch('/feature-fixture/v1/runs/'+self.run,token=self.actor,method='DELETE')[0])

    def test_foreign_or_credentialed_host_is_refused_without_recording_a_scene_write(self):
        self.open()
        for host in ('foreign.invalid','user:secret@127.0.0.1','127.0.0.1','127.0.0.1:0'):
            with self.subTest(host=host):self.assertEqual(400,self.fetch(self.path(),host=host)[0])
        self.assertEqual([],self.client.graphics_status()['responses'])

    def test_absent_provider_is_an_error_not_a_successful_scene_or_status(self):
        self.server.graphics_resources=None
        self.open()
        self.assertEqual(503,self.fetch(self.path())[0])
        with self.assertRaises(ValueError):self.client.graphics_status()

    def test_failed_provision_rolls_back_the_new_generic_journal(self):
        with patch.object(self.provider,'provision',side_effect=ValueError('Synthetic source unavailable')):
            with self.assertRaises(ValueError):self.client.register('graphics')
        self.assertEqual({},self.server.journal.runs);self.assertEqual({},self.provider.runs)

    def test_retirement_is_independently_read_and_prevents_later_scene_requests(self):
        self.open();self.fetch(self.path());before=self.client.graphics_status();self.client.close()
        after=self.client.graphics_status();self.assertFalse(after['active']);self.assertIsNone(after['ticket'])
        self.assertEqual(before['responses'],after['responses']);self.assertEqual(TICKET,after['sceneTicket'])
        self.assertEqual(404,self.fetch(self.path())[0]);self.assertEqual(0,self.provider.ready()['activeRuns'])

    def test_ignored_retirement_ack_cannot_make_client_cleanup_green(self):
        self.open();self.client.graphics_status()
        with patch.object(self.provider,'retire',return_value=None):
            with self.assertRaises(ValueError):self.client.close()
        self.assertFalse(self.client.closed);self.assertTrue(self.provider.runs[self.run]['active'])

    def test_observed_actual_http_status_is_preserved_instead_of_requested_200(self):
        self.open();send=Handler.send
        def altered(handler,status,value,*args,**kwargs):
            if kwargs.get('observe_write') is not None:status=503
            return send(handler,status,value,*args,**kwargs)
        with patch.object(Handler,'send',altered):self.assertEqual(503,self.fetch(self.path())[0])
        self.assertEqual(503,self.client.graphics_status()['responses'][0]['status'])

    def test_missing_actual_write_poison_blocks_further_success_and_publishes_no_receipt(self):
        self.open()
        with self.assertRaises(ValueError):
            with self.provider.response(self.run,TICKET,request_authority=url_host(self.url),request_scheme='http') as response:
                self.assertIsNotNone(response)
        self.assertEqual([],self.provider.runs[self.run]['responses']);self.assertFalse(self.provider.ready()['ready'])
        with self.assertRaises(ValueError):self.client.graphics_status()

    def test_incomplete_changed_or_duplicate_socket_write_does_not_become_a_receipt(self):
        self.open()
        for fault in ('bytes','digest','nonce','duplicate'):
            provider=GraphicsResources(self.url);provider.provision(self.run);provider.activate(self.run,TICKET)
            with self.subTest(fault=fault),self.assertRaises(ValueError):
                with provider.response(self.run,TICKET,request_authority=url_host(self.url),request_scheme='http') as response:
                    _,body,nonce,write=response
                    value=dict(responseId=nonce,status=200,bytes=len(body),sha256=hashlib.sha256(body).hexdigest())
                    if fault=='bytes':value['bytes']-=1
                    elif fault=='digest':value['sha256']='f'*64
                    elif fault=='nonce':value['responseId']='f'*32
                    write(value)
                    if fault=='duplicate':write(value)
            self.assertEqual([],provider.runs[self.run]['responses']);self.assertEqual(1,provider.failed)

    def test_status_nonce_birth_run_and_origin_are_pinned(self):
        self.open();value=self.client.graphics_status()
        for change in (dict(requestId='f'*32),dict(instance='f'*32),dict(runId='f'*32),dict(fixtureUrl=self.url+'/')):
            changed=deepcopy(value);changed.update(change)
            with self.subTest(change=change),self.assertRaises(ValueError):
                validate_status(changed,instance=self.provider.instance,run=self.run,url=self.url,request=value['requestId'])

    def test_closed_status_shapes_and_types_reject_expected_results_or_coercion(self):
        self.open();value=self.client.graphics_status()
        for change in (dict(graphicsProviderVersion=True),dict(healthy=1),dict(failedResponses=False),
                dict(active=1),dict(expectedHaze=True),dict(activations={})):
            changed=deepcopy(value);changed.update(change)
            with self.subTest(change=change),self.assertRaises(ValueError):self.validate(changed)

    def test_replayed_snapshot_nonce_cannot_be_retimed_as_a_new_original_read(self):
        self.open();previous=self.client.graphics_status();value=self.client.graphics_status()
        value['requestId']=previous['requestId']
        with self.assertRaises(ValueError):self.validate(value,previous)

    def test_scene_cannot_be_relabelled_as_current_ticket(self):
        self.open();self.client.activate(NEXT,'open');value=self.client.graphics_status();value['sceneTicket']=NEXT
        with self.assertRaises(ValueError):self.validate(value)

    def test_status_history_cannot_erase_rewrite_or_reorder_original_responses(self):
        self.open();self.fetch(self.path());previous=self.client.graphics_status();self.fetch(self.path())
        value=self.client.graphics_status()
        for fault in ('erase','rewrite','duplicate','clock','status'):
            changed=deepcopy(value)
            if fault=='erase':changed['responses']=[]
            elif fault=='rewrite':changed['responses'][0]['sha256']='f'*64
            elif fault=='duplicate':changed['responses'][1]['responseId']=changed['responses'][0]['responseId']
            elif fault=='clock':changed['responses'][0]['completedEpochMs']=changed['capturedEpochMs']+1
            else:changed['responses'][0]['status']=503
            with self.subTest(fault=fault),self.assertRaises(ValueError):self.validate(changed,previous)

    def test_retired_runs_never_reactivate_or_accept_reused_tickets(self):
        self.open()
        with self.assertRaises(ValueError):self.provider.activate(self.run,TICKET)
        before=self.client.graphics_status();self.provider.retire(self.run)
        with self.assertRaises(ValueError):self.provider.activate(self.run,NEXT)
        changed=deepcopy(before);changed['active']=False;changed['ticket']=None
        with self.assertRaises(ValueError):self.validate(before,changed)

    def test_clock_regression_is_retained_as_an_unhealthy_source(self):
        provider=GraphicsResources(self.url,clock_ms=lambda:20000);provider.provision('a'*32)
        provider.clock_ms=lambda:19999
        with self.assertRaises(ValueError):provider.snapshot('a'*32,'b'*32)
        provider.clock_ms=lambda:20000;self.assertFalse(provider.ready()['ready'])

    def test_allocation_and_response_histories_are_bounded_without_dropping_ownership(self):
        provider=GraphicsResources(self.url);provider.provision('a'*32)
        with self.assertRaises(ValueError):provider.provision('b'*32)
        for i in range(256):provider.activate('a'*32,format(i+1,'032x'))
        with self.assertRaises(ValueError):provider.activate('a'*32,'f'*32)
        provider.runs['a'*32]['responses']=[{}]*256
        with provider.response('a'*32,format(1,'032x'),request_authority=url_host(self.url),request_scheme='http') as reply:
            self.assertIsNone(reply)
        self.assertFalse(provider.ready()['ready']);self.assertEqual(256,len(provider.runs['a'*32]['responses']))

    def test_fixture_url_rejects_credentials_aliases_queries_and_noncanonical_origins(self):
        self.assertEqual(self.url,fixture_url(self.url))
        for url in (self.url+'/',self.url+'?desired=on',self.url+'#fragment',self.url.replace('http:','file:'),
                self.url.replace('127.0.0.1','user:secret@127.0.0.1'),self.url.replace('http:','HTTP:'),
                self.url.replace('127.0.0.1','127.0.0.1%2fexample.invalid'),self.url+'\n'):
            with self.subTest(url=url),self.assertRaises(ValueError):GraphicsResources(url)


def url_host(url):
    from urllib.parse import urlsplit
    return urlsplit(url).netloc


if __name__=='__main__':unittest.main()
