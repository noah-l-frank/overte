"""Pico original coordinator at synthetic target seams and actual loopback HTTP."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import secrets
import tempfile
import threading
import unittest
from unittest.mock import patch
from adapters.script_journey.history import unpack

from adapters.pico4.tablet_web_feature import PicoTabletWebFeature
from adapters.pico4.browser_measurements import measurement
from feature_journeys.browser_fixture import BrowserResources
from feature_journeys.phase_fixture import PhaseFixtureReader
from feature_journeys.server import make_server
from feature_journeys.scenarios import VERSION,SCENARIOS,expand
from feature_journeys.fixtures import context
from feature_journeys.engine import matches
from feature_journeys.witness import Client
from self_tests.pico_browser_fixture import Clock,PicoTarget


class PicoTabletWebFlowTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name);self.path.chmod(0o700);self.artifacts=self.path/'artifacts';self.artifacts.mkdir(mode=0o700)
        self.clock=Clock();self.reader,self.actor_token,self.adapter_token=[secrets.token_hex(32) for _ in range(3)]
        self.server=make_server(self.reader,self.actor_token,adapter_token=self.adapter_token);self.server.journal.clock=self.clock.epoch
        self.server.browser_resources=BrowserResources(clock_ms=self.clock.epoch)
        self.peer=make_server(self.reader,self.actor_token,browser_peer_of=self.server)
        for server in (self.server,self.peer):
            thread=threading.Thread(target=lambda s=server:s.serve_forever(poll_interval=.01),daemon=True);thread.start()
            self.addCleanup(self.stop,server,thread)
        self.url=f'http://127.0.0.1:{self.server.server_port}/feature-fixture/v1'
        self.foreign=f'http://127.0.0.1:{self.peer.server_port}/feature-fixture/v1'
        self.client=Client(self.url,self.reader);self.run,self.fixture_url=self.client.register('tablet-web')
        self.target=PicoTarget(self.clock,self.client,self.foreign,self.path)
        self.primary=self.flow(Client(self.url,self.adapter_token),'primary')
        self.actor=self.flow(Client(self.url,self.actor_token),'actor')
    def stop(self,server,thread):server.shutdown();server.server_close();thread.join(timeout=2);self.assertFalse(thread.is_alive())
    def flow(self,client,role):
        return PicoTabletWebFeature(self.target,'target',PhaseFixtureReader(client,self.run,'tablet-web',epoch_ms=self.clock.epoch,
            monotonic=self.clock.now),self.artifacts,self.foreign,role=role,monotonic=self.clock.now,sleep=self.clock.sleep)
    def activate(self,verb='baseline',inputs=None):
        ticket=secrets.token_hex(16);self.client.activate(ticket,verb,inputs);return ticket
    def act(self,verb,inputs=None):
        ticket=self.activate(verb,inputs)
        self.primary.act(dict(contractVersion=VERSION,runId=self.run,fixtureUrl=self.fixture_url,ticket=ticket,verb=verb,inputs=inputs or {}))
        return ticket
    def measured(self):
        with self.target.lock.held():
            owner=self.primary.owner();native=self.primary.sample_native(owner)
            runtime=self.target._web_runtime_observer('target').read(self.run,self.fixture_url)
            status=self.client.request('/runs/'+self.run+'/browser');_ui,observe,*_=self.target.normal_feature_runtime('target')
            rows,_epoch=observe(0)
            return measurement(self.run,self.fixture_url,self.primary.foreign_url,native,status,runtime,rows['scripts'],owner['scriptUrl'],area='tablet-web')
    def test_original_http_app_normal_open_wheel_and_unicode_effect_are_independently_measured(self):
        self.activate();self.primary.prepare();self.act('open')
        state,_resources=self.measured();self.assertTrue(state['open']);self.assertEqual('',state['text'])
        self.act('focus-type',dict(text='Overte ä Ω 東京 '+self.run))
        state,_resources=self.measured();self.assertEqual('Overte ä Ω 東京 '+self.run,state['text'])
        self.assertTrue(any(row['command']['control']=='scroll-down' for row in self.target.inputs))

    def test_all_shared_input_state_stages_keep_original_http_dom_foreign_inline_and_lifecycle_sources(self):
        # This state/input lane deliberately makes no Journey image/actor or
        # whole-feature claim. The production image gate remains enabled.
        self.activate();self.primary.prepare();completed=[]
        for ordinal,step in enumerate(SCENARIOS['tablet-web']['steps'],1):
            self.act(step['verb'],expand(step['inputs'],context(self.run)))
            state,_resources=self.measured()
            self.assertTrue(matches(state,expand(step['state'],context(self.run))),f'stage {ordinal}: {step["verb"]}')
            completed.append(ordinal)
        self.assertEqual(list(range(1,27)),completed);self.assertEqual(1,self.target.backgrounds)
        self.assertEqual(1,len(self.target.deferred['deliveries']));self.assertFalse(self.target.deferred['deliveries'][0]['accepted'])
        self.assertTrue(any(row['status']==404 for row in self.client.request('/runs/'+self.run+'/browser')['responses']))
        self.activate('cleanup');self.primary.cleanup(dict(contractVersion=VERSION,runId=self.run))
        self.assertTrue(self.target.retired)
        with self.target.lock.held():
            owner=self.primary.owner();self.assertEqual('cleaned',owner['phase']);self.assertTrue(self.primary.cleanup_window(owner).value['complete'])
            vm=self.target._tablet_web_vm('target',self.primary);self.assertEqual(1,len(vm.windows))
        self.primary.cleanup(dict(contractVersion=VERSION,runId=self.run))
        self.assertEqual(1,sum(row['operation']=='retire' for row in self.target.command_log))
        self.assertTrue(self.primary.store.path.exists())
        with self.assertRaises((ValueError,RuntimeError)):self.primary.finalize()

    def test_ignored_input_and_lost_original_delivery_never_become_effects_or_resends(self):
        self.activate();self.primary.prepare();self.act('open');self.target.fail='ignored-input'
        self.act('focus-type',dict(text='Overte ä Ω 東京 '+self.run));state,_resources=self.measured();self.assertEqual('',state['text'])
        self.target.fail='lost-input';ticket=self.activate('submit');before=self.target.input_count
        call=dict(contractVersion=VERSION,runId=self.run,fixtureUrl=self.fixture_url,ticket=ticket,verb='submit',inputs={})
        for _attempt in range(2):
            with self.assertRaises((ValueError,RuntimeError)):self.primary.act(call)
        self.assertEqual(before+1,self.target.input_count)
        cold=self.flow(Client(self.url,self.adapter_token),'primary')
        with self.assertRaises((ValueError,RuntimeError)):cold.act(call)
        self.assertEqual(before+1,self.target.input_count)

    def test_last_quiet_parent_cas_cannot_renew_old_sources_before_original_retire(self):
        self.activate();self.primary.prepare();self.act('open');self.act('close');self.activate('cleanup')
        write=self.primary.store.write
        def late(value,previous):
            write(value,previous)
            if value['kind']=='owner' and unpack(value['payload'])[0]['cleanupProof'] is not None:self.clock.sleep(2)
        with patch.object(self.primary.store,'write',side_effect=late),self.assertRaises((ValueError,RuntimeError)):
            self.primary.cleanup(dict(contractVersion=VERSION,runId=self.run))
        self.assertFalse(self.target.retired);self.assertEqual(0,sum(row['operation']=='retire' for row in self.target.command_log))
        self.assertTrue(self.primary.store.path.exists())


if __name__=='__main__':unittest.main()
