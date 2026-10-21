"""Original loopback HTTP evidence only; no native client, device or compiler."""
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
from urllib.request import Request, urlopen

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from feature_journeys.script_fixture import ScriptResources, validate_status, missing_receipt, BODY
from feature_journeys.server import make_server, Handler
from feature_journeys.witness import Client

TICKET = 'b' * 32


class ScriptResourcesTests(unittest.TestCase):
    def setUp(self):
        self.reader, self.actor = secrets.token_hex(32), secrets.token_hex(32)
        self.server = make_server(self.reader,self.actor)
        self.provider = self.server.script_resources
        self.thread = threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.origin = f'http://127.0.0.1:{self.server.server_port}'
        self.client = Client(self.origin+'/feature-fixture/v1',self.reader)
        self.addCleanup(self.stop)

    def stop(self):
        self.server.shutdown();self.server.server_close();self.thread.join(timeout=2)
        self.assertFalse(self.thread.is_alive());self.assertEqual(0,self.server.internal_errors)

    def open(self):
        self.run, self.url = self.client.register('scripts');self.client.activate(TICKET)
        return self.run

    def fetch(self, path, *, token=None, value=None, method=None, host=None):
        headers={'Authorization':'Bearer '+token} if token else {}
        if host is not None:headers['Host']=host
        if path.endswith('/scripts'):headers['X-Overte-Script-Read']=secrets.token_hex(16)
        request = Request(self.origin+path, data=json.dumps(value).encode() if value is not None else None,
            headers=headers,method=method)
        try:
            with urlopen(request,timeout=2) as response:
                return response.status,response.read(),response.headers.get('X-Overte-Fixture-Response')
        except HTTPError as error:
            try:return error.code,error.read(),error.headers.get('X-Overte-Fixture-Response')
            finally:error.close()

    def missing(self, ticket=TICKET, run=None):
        return f'/feature-fixture/v1/runs/{run or self.run}/tickets/{ticket}/missing.js'

    def test_actual_http_404_records_serialized_status_original_bytes_id_and_completion(self):
        self.open(); before = self.client.script_status()
        self.assertEqual([],before['responses']);self.assertEqual(TICKET,before['activations'][0]['ticket'])
        status, body, response_id = self.fetch(self.missing())
        self.assertEqual(404,status);self.assertEqual(BODY,body)
        source = self.client.script_status();row = source['responses'][0]
        self.assertEqual(response_id,row['responseId']);self.assertEqual(status,row['status'])
        self.assertEqual(len(body),row['bytes']);self.assertEqual(hashlib.sha256(body).hexdigest(),row['sha256'])
        self.assertLessEqual(source['activations'][0]['activatedEpochMs'],row['startedEpochMs'])
        self.assertLessEqual(row['startedEpochMs'],row['completedEpochMs'])
        self.assertLessEqual(row['completedEpochMs'],source['capturedEpochMs'])
        self.assertEqual(row,missing_receipt(source,run=self.run,ticket=TICKET,fixture_url=self.url,
            after_epoch=source['activations'][0]['activatedEpochMs']))

    def test_ack_or_snapshot_without_a_resource_request_never_creates_http_receipt(self):
        self.open();self.client.activate('c'*32,'load-url',{'resource':'missing.js'})
        for _ in range(3):self.assertEqual([],self.client.script_status()['responses'])

    def test_old_foreign_ticket_run_or_query_cannot_borrow_current_http_receipt(self):
        self.open();self.client.activate('c'*32,'load-url',{'resource':'missing.js'})
        for path in (self.missing(),self.missing('d'*32),self.missing('c'*32)+'?expected=404',self.missing('c'*32,'e'*32)):
            self.assertIn(self.fetch(path)[0],(400,404))
        self.assertEqual([],self.client.script_status()['responses'])
        self.assertEqual(404,self.fetch(self.missing('c'*32))[0])
        self.assertEqual('c'*32,self.client.script_status()['responses'][0]['ticket'])

    def test_status_is_private_actor_can_read_but_cannot_activate_or_retire(self):
        self.open();path=f'/feature-fixture/v1/runs/{self.run}/scripts'
        self.assertEqual(403,self.fetch(path)[0]);self.assertEqual(200,self.fetch(path,token=self.actor)[0])
        root=f'/feature-fixture/v1/runs/{self.run}'
        self.assertEqual(403,self.fetch(root+'/active',token=self.actor,value=dict(ticket='c'*32,verb='open',inputs={}))[0])
        self.assertEqual(403,self.fetch(root,token=self.actor,method='DELETE')[0])
        self.assertEqual(TICKET,self.client.script_status()['ticket'])

    def test_missing_provider_and_failed_readiness_refuse_registration_without_orphan_run(self):
        self.server.script_resources = None
        with self.assertRaises(ValueError):self.client.register('scripts')
        self.assertEqual({},self.server.journal.runs)
        self.server.script_resources = self.provider;self.provider.failed = 1
        with self.assertRaises(ValueError):self.client.register('scripts')
        self.assertEqual({},self.server.journal.runs)

    def test_provider_failure_after_registration_rolls_back_journal_without_relabeling_it(self):
        with patch.object(self.provider,'provision',side_effect=ValueError('synthetic unavailable ownership')):
            with self.assertRaises(ValueError):self.client.register('scripts')
        self.assertEqual({},self.server.journal.runs);self.assertEqual({},self.provider.runs)

    def test_failed_or_unobserved_actual_write_is_poison_not_completed_http_success(self):
        self.open()
        for source in (self.provider, ScriptResources()):
            if source is not self.provider:source.provision(self.run);source.activate(self.run,TICKET)
            with self.subTest(source=source.instance),self.assertRaises((OSError,ValueError)):
                with source.response(self.run,TICKET,request_authority='127.0.0.1',request_scheme='http') as response:
                    self.assertIsNotNone(response)
                    if source is self.provider:raise OSError('synthetic failed socket')
            self.assertEqual([],source.snapshot(self.run)['responses']);self.assertFalse(source.ready()['ready'])
        with self.assertRaises(ValueError):self.client.script_status()

    def test_actual_serialized_wrong_status_is_preserved_and_rejected_instead_of_expected_404(self):
        self.open();original=Handler.send_response
        def wrong(handler,code,message=None):
            return original(handler,200 if code==404 else code,message)
        with patch.object(Handler,'send_response',wrong):
            status,body,_response=self.fetch(self.missing())
        self.assertEqual(200,status);self.assertEqual(BODY,body)
        actual=self.provider.snapshot(self.run)
        self.assertEqual(200,actual['responses'][0]['status'])
        with self.assertRaises(ValueError):self.client.script_status()

    def test_actual_written_wrong_body_is_preserved_without_substituting_fixture_digest(self):
        self.open();original=Handler.send
        def wrong(handler,status,value,*args,**kwargs):
            if kwargs.get('observe_write') is not None:value=BODY.replace(b'not-found',b'forbidden')
            return original(handler,status,value,*args,**kwargs)
        with patch.object(Handler,'send',wrong):
            status,body,_response=self.fetch(self.missing())
        self.assertEqual(404,status);self.assertNotEqual(BODY,body)
        actual=self.provider.snapshot(self.run)['responses'][0]
        self.assertEqual(len(body),actual['bytes']);self.assertEqual(hashlib.sha256(body).hexdigest(),actual['sha256'])
        with self.assertRaises(ValueError):self.client.script_status()

    def test_original_history_cannot_be_rewritten_dropped_or_replaced(self):
        self.open();self.fetch(self.missing());before=self.client.script_status()
        for mutate in (lambda value:value['responses'][0].update(sha256='f'*64),
                       lambda value:value.update(responses=[]),lambda value:value.update(activations=[]),
                       lambda value:value.update(instance='f'*32),lambda value:value.update(scriptProviderVersion=True),
                       lambda value:value.update(capturedEpochMs=1),lambda value:value.update(ticket='c'*32),
                       lambda value:value.update(healthy=False),lambda value:value.update(failedResponses=1)):
            after=deepcopy(before);mutate(after)
            with self.subTest(after=after),self.assertRaises(ValueError):
                validate_status(after,instance=before['instance'],run=self.run,previous=before)

    def test_current_http_snapshot_nonce_rejects_freshly_replayed_or_foreign_packet(self):
        self.open();before=self.client.script_status()
        with patch.object(self.client,'request',return_value=deepcopy(before)):
            with self.assertRaisesRegex(ValueError,'another request'):self.client.script_status()
        request=Request(self.origin+f'/feature-fixture/v1/runs/{self.run}/scripts',headers={'Authorization':'Bearer '+self.actor})
        with self.assertRaises(HTTPError) as error:urlopen(request,timeout=2)
        self.assertEqual(400,error.exception.code);error.exception.close()

    def test_response_inventory_overflow_is_incomplete_not_an_ignored_extra_result(self):
        self.open();self.provider.runs[self.run]['responses']=[None]*256
        self.assertEqual(404,self.fetch(self.missing())[0])
        self.assertFalse(self.provider.snapshot(self.run)['healthy'])
        with self.assertRaises(ValueError):self.client.script_status()

    def test_original_foreign_http_host_is_preserved_but_cannot_prove_owned_origin(self):
        self.open();self.fetch(self.missing(),host='foreign.test:12345');source=self.client.script_status()
        self.assertEqual('foreign.test:12345',source['responses'][0]['requestAuthority'])
        with self.assertRaises(ValueError):missing_receipt(source,run=self.run,ticket=TICKET,fixture_url=self.url,after_epoch=1)

    def test_missing_duplicated_stale_or_foreign_failure_receipts_cannot_be_adopted(self):
        self.open();self.fetch(self.missing());source=self.client.script_status()
        for ticket,url,epoch in (('c'*32,self.url,1),(TICKET,self.url.replace('127.0.0.1','foreign.test'),1),
                                (TICKET,self.url,source['responses'][0]['completedEpochMs']+1)):
            with self.subTest(ticket=ticket,url=url,epoch=epoch),self.assertRaises(ValueError):
                missing_receipt(source,run=self.run,ticket=ticket,fixture_url=url,after_epoch=epoch)
        self.fetch(self.missing());source=self.client.script_status()
        with self.assertRaises(ValueError):missing_receipt(source,run=self.run,ticket=TICKET,fixture_url=self.url,after_epoch=1)

    def test_cleanup_retires_actual_owned_resource_and_is_idempotent_after_lost_reply(self):
        self.open();self.fetch(self.missing());self.client.script_status()
        original=self.client.request
        def lost(path,*args,**kwargs):
            result=original(path,*args,**kwargs)
            if kwargs.get('method')=='DELETE':raise ValueError('synthetic lost cleanup response')
            return result
        with patch.object(self.client,'request',side_effect=lost):
            with self.assertRaises(ValueError):self.client.close()
        self.assertFalse(self.client.closed);self.assertFalse(self.client.script_status()['active'])
        self.client.close();self.client.close()
        self.assertTrue(self.client.closed);self.assertNotIn(self.run,self.server.journal.runs)
        self.assertEqual(404,self.fetch(self.missing())[0])
        self.assertEqual(1,len(self.client.script_status()['responses']))

    def test_cleanup_ack_with_unretired_source_does_not_claim_absence(self):
        self.open();self.client.script_status()
        with patch.object(self.provider,'retire',return_value=None):
            with self.assertRaises(ValueError):self.client.close()
        self.assertFalse(self.client.closed);self.assertTrue(self.provider.snapshot(self.run)['active'])
        self.provider.retire(self.run);self.client.close()

    def test_original_activation_clock_never_resets_or_accepts_reused_challenge(self):
        self.open();before=self.client.script_status()
        with self.assertRaises(ValueError):self.client.activate(TICKET)
        self.assertEqual(before['activations'],self.client.script_status()['activations'])
        self.client.activate('c'*32,'open',{})
        source=self.client.script_status();self.assertEqual(2,len(source['activations']))
        self.assertLessEqual(source['activations'][0]['activatedEpochMs'],source['activations'][1]['activatedEpochMs'])

    def test_clock_regression_and_retired_resurrection_cannot_be_hidden(self):
        clock=[100];source=ScriptResources(clock_ms=lambda:clock[0]);run='e'*32
        source.provision(run);source.activate(run,TICKET);clock[0]=99
        with self.assertRaises(ValueError):source.snapshot(run)
        clock[0]=101;self.assertFalse(source.ready()['ready'])
        self.open();self.client.script_status();self.client.close();old=self.client.script_status()
        value=deepcopy(old);value.update(active=True,ticket=TICKET)
        with self.assertRaises(ValueError):validate_status(value,instance=old['instance'],run=self.run,previous=old)


if __name__=='__main__':unittest.main()
