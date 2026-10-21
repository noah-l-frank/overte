"""Original input-phase metadata; synthetic clock and owned loopback only."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import sys
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from adapters.feature_fixture_access import AdapterFixtureClient
from feature_journeys.phase_fixture import PhaseFixtureReader, PhasePending, PhaseRetired, validate
from feature_journeys.scenarios import SCENARIOS, actions, expand
from feature_journeys.fixtures import context
from feature_journeys.server import make_server
from feature_journeys.witness import Client, Journal, projection

RUN='a'*32; TICKET='b'*32; SECOND='c'*32; REQUEST='d'*32
URL='http://controlled.test/feature-fixture/v1'


class PhaseFixtureTests(unittest.TestCase):
    def setUp(self):
        self.epoch=20000; self.clock=0.; self.journal=Journal(lambda:self.epoch)
        with patch('feature_journeys.witness.secrets.token_hex', return_value=RUN):
            self.run=self.journal.register('emotes')
        self.journal.activate(RUN,TICKET)
    def packet(self):return self.journal.phase(RUN,REQUEST)
    def valid(self, value, previous=None):
        return validate(value,run=RUN,area='emotes',request=value['requestId'],epoch=self.epoch,previous=previous)
    def source(self, transform=lambda value:value):
        self.client=Client(URL,'r'*64);self.calls=[]
        def request(path,**kwargs):
            self.calls.append((path,kwargs))
            return transform(self.journal.phase(RUN,kwargs['phase_nonce']))
        self.client.request=request
        return PhaseFixtureReader(self.client,RUN,'emotes',epoch_ms=lambda:self.epoch,monotonic=lambda:self.clock)

    def test_actual_activation_time_stays_original_when_later_reads_advance(self):
        source=self.source();first=source.read();self.assertEqual(20000,first['afterEpochMs'])
        self.epoch+=500;second=source.read(first['status'])
        self.assertEqual(20000,second['afterEpochMs']);self.assertEqual(20500,second['status']['capturedEpochMs'])
        self.assertGreater(second['status']['sequence'],first['status']['sequence'])
        self.assertNotEqual(second['status']['requestId'],first['status']['requestId'])
        self.assertEqual(['/runs/'+RUN+'/phase']*2,[call[0] for call in self.calls])
        self.assertTrue(all(set(call[1])=={'phase_nonce'} for call in self.calls))

    def test_new_ticket_retains_exact_original_closed_stimulus_and_time(self):
        source=self.source();first=source.read();self.epoch+=100
        data={'name':'Waving'};self.journal.activate(RUN,SECOND,'play',data);data['name']='foreign'
        second=source.read();self.assertEqual({'name':'Waving'},second['inputs'])
        self.assertEqual(20100,second['afterEpochMs'])
        self.assertEqual(first['status']['activations'],second['status']['activations'][:1])
        second['status']['activations'][0]['stimulus']['verb']='foreign'
        self.assertEqual('baseline',source.previous['activations'][0]['stimulus']['verb'])

    def test_all_fourteen_closed_action_inventories_have_original_input_metadata(self):
        for area in SCENARIOS:
            with self.subTest(area=area):
                journal=Journal(lambda:20000);run=journal.register(area)
                for index,(verb,choices) in enumerate(actions(area).items()):
                    journal.activate(run,format(index+1,'032x'),verb,expand(choices[0],context(run)))
                value=journal.phase(run,REQUEST)
                validate(value,run=run,area=area,request=REQUEST,epoch=20000)

    def test_no_peer_or_product_facts_are_exported_even_after_actual_publication(self):
        self.journal.publish(RUN,dict(ticket=TICKET,actor='owned-observer',actorSequence=1,capturedEpochMs=20000,
            facts=projection('emotes',SCENARIOS['emotes']['baseline'])))
        value=self.packet();self.assertNotIn('entries',value);self.assertNotIn('facts',value)
        self.assertNotIn('state',value);self.assertNotIn('resources',value)
        self.assertNotIn('peerMessages',str(value))

    def test_retired_status_preserves_original_history_and_never_queries_removed_active_endpoint(self):
        source=self.source();first=source.read();self.epoch+=100;self.journal.close(RUN)
        with self.assertRaises(PhaseRetired) as caught:source.read()
        status=caught.exception.status;self.assertFalse(status['active']);self.assertEqual(20100,status['retiredEpochMs'])
        self.assertEqual(first['status']['activations'],status['activations'])
        self.epoch+=100;self.journal.close(RUN);last=source.status()
        self.assertEqual(20100,last['retiredEpochMs']);self.assertEqual(status['activations'],last['activations'])
        self.assertTrue(all('/active' not in call[0] for call in self.calls))

    def test_unknown_or_evicted_run_is_unavailable_instead_of_empty_success(self):
        self.journal.close(RUN)
        for _ in range(64):
            run=self.journal.register('emotes');self.journal.close(run)
        self.assertEqual(64,len(self.journal.retired_phases))
        with self.assertRaises(KeyError):self.packet()
        with self.assertRaises(KeyError):self.journal.phase('e'*32,REQUEST)

    def test_known_retired_identity_and_ticket_cannot_be_reused(self):
        with self.assertRaises(ValueError):self.journal.activate(RUN,TICKET)
        self.journal.close(RUN)
        with patch('feature_journeys.witness.secrets.token_hex',return_value=RUN),self.assertRaises(ValueError):
            self.journal.register('emotes')
        with self.assertRaises(KeyError):self.journal.activate(RUN,SECOND)

    def test_pending_run_never_invents_a_baseline_ticket(self):
        run=self.journal.register('emotes');client=Client(URL,'r'*64)
        client.request=lambda path,**kwargs:self.journal.phase(run,kwargs['phase_nonce'])
        source=PhaseFixtureReader(client,run,'emotes',epoch_ms=lambda:self.epoch)
        with self.assertRaises(PhasePending):source.read()
        self.assertEqual([],source.previous['activations'])

    def test_stale_future_foreign_malformed_or_expectation_bearing_packets_are_rejected(self):
        original=self.packet()
        for edit in [dict(fixturePhaseVersion=True),dict(sequence=True),dict(runId='e'*32),dict(area='chat'),
            dict(instance='invalid'),dict(capturedEpochMs=18000),dict(capturedEpochMs=20300),
            dict(createdEpochMs=21000),dict(active=1),dict(retiredEpochMs=20000),dict(expectedState={}),dict(entries=[])]:
            with self.subTest(fields=list(edit)),self.assertRaises(ValueError):self.valid(original|edit)
        with self.assertRaises(ValueError):
            validate(original,run=RUN,area='emotes',request='e'*32,epoch=20000)

    def test_changed_or_truncated_original_activation_prefix_is_rejected(self):
        previous=self.packet();self.epoch+=100;self.journal.activate(RUN,SECOND,'play',{'name':'Waving'})
        original=self.journal.phase(RUN,'e'*32)
        for fault in ('old-time','changed-stimulus','sequence','reused-ticket','drop-prefix','extra-field','unknown-verb','wrong-input-type'):
            value=deepcopy(original);rows=value['activations']
            if fault=='old-time':rows[0]['activatedEpochMs']+=1
            elif fault=='changed-stimulus':rows[0]['stimulus']={'verb':'open','inputs':{}}
            elif fault=='sequence':rows[-1]['sequence']=True
            elif fault=='reused-ticket':rows[-1]['ticket']=TICKET
            elif fault=='drop-prefix':rows.pop(0);rows[0]['sequence']=1
            elif fault=='extra-field':rows[-1]['expected']=True
            elif fault=='unknown-verb':rows[-1]['stimulus']['verb']='setter'
            else:rows[-1]['stimulus']['inputs']={'name':True}
            with self.subTest(fault=fault),self.assertRaises(ValueError):self.valid(value,previous)

    def test_provider_cursor_nonce_birth_clock_or_retirement_cannot_regress(self):
        previous=self.packet();self.epoch+=100;current=self.journal.phase(RUN,'e'*32)
        for edit in [dict(sequence=previous['sequence']),dict(requestId=previous['requestId']),dict(instance='f'*32),
            dict(createdEpochMs=19999),dict(capturedEpochMs=19999)]:
            with self.subTest(fields=list(edit)),self.assertRaises(ValueError):self.valid(current|edit,previous)
        self.journal.close(RUN);retired=self.journal.phase(RUN,'f'*32);current=self.journal.phase(RUN,'1'*32)
        for edit in [dict(active=True,retiredEpochMs=None),dict(retiredEpochMs=20099),dict(activations=[])]:
            with self.subTest(retiredFields=list(edit)),self.assertRaises(ValueError):self.valid(current|edit,retired)

    def test_frozen_epoch_cannot_hide_slow_http_and_clock_regression_is_refused(self):
        def slow(value):self.clock+=2;return value
        with self.assertRaises(ValueError):self.source(slow).read()
        def backwards(value):self.clock-=1;return value
        with self.assertRaises(ValueError):self.source(backwards).read()

    def test_new_reader_must_honor_the_complete_external_original_floor(self):
        previous=self.source().status();self.epoch+=100
        source=self.source();value=source.status(previous);self.assertGreater(value['sequence'],previous['sequence'])
        self.journal.runs[RUN]['phaseActivations'][0]['activatedEpochMs']+=1
        with self.assertRaises(ValueError):self.source().status(previous)


class PhaseHttpTests(unittest.TestCase):
    def setUp(self):
        self.server=make_server('r'*64,'a'*64,adapter_token='d'*64)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.addCleanup(self.stop)
        self.url='http://127.0.0.1:'+str(self.server.server_address[1])+'/feature-fixture/v1'
        self.reader=Client(self.url,'r'*64);self.run,_=self.reader.register('emotes');self.reader.activate(TICKET)
    def stop(self):
        self.server.shutdown();self.server.server_close();self.thread.join(timeout=2)
        self.assertFalse(self.thread.is_alive())
    def test_actual_adapter_and_actor_read_separate_nonce_bound_originals_through_retirement(self):
        primary=PhaseFixtureReader(AdapterFixtureClient(self.url,'d'*64),self.run,'emotes')
        actor=PhaseFixtureReader(Client(self.url,'a'*64),self.run,'emotes')
        first=primary.read();other=actor.read()
        self.assertEqual(first['status']['activations'],other['status']['activations'])
        self.assertNotEqual(first['status']['requestId'],other['status']['requestId'])
        self.reader.activate(SECOND,'play',{'name':'Waving'});second=primary.read()
        self.assertEqual('play',second['verb']);self.assertGreater(second['afterEpochMs'],first['afterEpochMs'])
        self.reader.close()
        for source in (primary,actor):
            with self.assertRaises(PhaseRetired):source.read()
        self.assertEqual(0,self.server.internal_errors)
    def test_required_nonce_authorization_and_get_only_do_not_enable_mutation(self):
        path='/runs/'+self.run+'/phase'
        for token,method,nonce,expected in [('d'*64,'GET',None,400),('wrong'*8,'GET',REQUEST,403),
            ('d'*64,'POST',REQUEST,403),('a'*64,'DELETE',REQUEST,403)]:
            headers={'Authorization':'Bearer '+token}
            if nonce is not None:headers['X-Overte-Phase-Read']=nonce
            request=Request(self.url+path,method=method,headers=headers)
            with self.subTest(method=method,nonce=nonce),self.assertRaises(HTTPError) as caught:
                urlopen(request,timeout=2)
            self.assertEqual(expected,caught.exception.code);caught.exception.close()
        self.assertEqual(TICKET,self.server.journal.active(self.run)['ticket'])


if __name__=='__main__':unittest.main()
