"""Continuous normal World Script→ray/IME→Send; native/Qt/V8/OS are seams.

Actual Python owners, normal token/Session delivery, loopback HTTP bytes and
original histories execute. No head-mounted image or whole feature is claimed.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
import secrets
import tempfile
import threading
import traceback
import unittest
from unittest.mock import patch

from adapters.normal_ui import NativeUIError
from adapters.normal_feature_state import PrivateFeatureState
from adapters.pico4.world_web_binding import PicoWorldWebBinding
from adapters.pico4.navigation import NavigationError
from adapters.pico4.browser_history import PicoBrowserHistory
from adapters.script_journey.history import unpack
from feature_journeys.browser_fixture import BrowserResources
from feature_journeys.phase_fixture import PhaseFixtureReader,PhasePending
from feature_journeys.scenarios import SCENARIOS,VERSION,expand
from feature_journeys.fixtures import context
from feature_journeys.engine import matches
from feature_journeys.witness import Client
from feature_journeys.server import make_server
from self_tests.pico_browser_fixture import Clock
from self_tests.pico_world_web_prefix_fixture import WorldTarget


class WorldWebPrefixTests(unittest.TestCase):
    def run(self,result=None):
        result=result or self.defaultTestResult();error=result.addError;failure=result.addFailure
        def retain(test,info,forward):
            if hasattr(self,'root'):
                rows=[];current=info[1]
                while current is not None and len(rows)<12:
                    text=''.join(traceback.format_exception(type(current),current,current.__traceback__,chain=False))
                    rows.append(dict(type=type(current).__name__,traceback=text));print(text,flush=True);current=current.__context__
                model=getattr(self,'target',None)
                PrivateFeatureState(self.root/'first-failure.json').write(dict(test=test.id(),errors=rows,
                    normalInputs=[] if model is None else deepcopy(model.normal_inputs),
                    envelopes=[] if model is None else deepcopy(model.transport.envelopes),
                    script=None if model is None else model.script,
                    current=None if model is None else deepcopy(model.current),
                    sourceSequence=0 if model is None else model.sequence),None)
            return forward(test,info)
        with patch.object(result,'addError',side_effect=lambda test,info:retain(test,info,error)), \
             patch.object(result,'addFailure',side_effect=lambda test,info:retain(test,info,failure)):
            return unittest.TestCase.run(self,result)

    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory();self.temporary._finalizer.detach()
        self.root=Path(self.temporary.name);self.root.chmod(0o700)
        print('Retained World Web original fixture:',self.root,flush=True)
        self.clock=Clock();reader,actor,adapter=[secrets.token_hex(32) for _ in range(3)]
        self.server=make_server(reader,actor,adapter_token=adapter);self.server.journal.clock=self.clock.epoch
        self.server.browser_resources=BrowserResources(clock_ms=self.clock.epoch)
        self.peer=make_server(reader,actor,browser_peer_of=self.server)
        for server in (self.server,self.peer):
            thread=threading.Thread(target=lambda current=server:current.serve_forever(poll_interval=.01),daemon=True);thread.start()
            self.addCleanup(self.stop,server,thread)
        self.url='http://127.0.0.1:'+str(self.server.server_port)+'/feature-fixture/v1'
        self.foreign='http://127.0.0.1:'+str(self.peer.server_port)+'/feature-fixture/v1'
        self.reader=Client(self.url,reader);self.run,self.fixture_url=self.reader.register('world-web')
        self.target=WorldTarget(self.clock,self.reader,self.foreign,self.root)
        self.environment=patch.dict('os.environ',dict(OVERTE_PICO_NORMAL_SCRIPTS='1',OVERTE_ANDROID_E2E_DEBUG='1',
            OVERTE_PICO_OPENXR_INPUT='1',OVERTE_E2E_SCENE_URL=self.target.scene_url))
        self.environment.start();self.addCleanup(self.environment.stop)
        self.facade=PicoWorldWebBinding(self.target)
        def flow(token,role):return self.facade.prefix(self.target.selector,PhaseFixtureReader(Client(self.url,token),self.run,'world-web',
            epoch_ms=self.clock.epoch,monotonic=self.clock.now),self.foreign,role=role)
        self.primary=flow(adapter,'primary');self.actor=flow(actor,'actor')
        self.activate('baseline',{})
    def stop(self,server,thread):
        server.shutdown();server.server_close();thread.join(2);self.assertFalse(thread.is_alive())
    def activate(self,verb,inputs):
        ticket=secrets.token_hex(16);self.reader.activate(ticket,verb,inputs)
        return dict(contractVersion=VERSION,runId=self.run,fixtureUrl=self.fixture_url,ticket=ticket,verb=verb,inputs=inputs)
    def call(self,index):
        row=SCENARIOS['world-web']['steps'][index];return self.activate(row['verb'],expand(row['inputs'],context(self.run)))
    def baseline(self):
        self.primary.prepare();first=self.primary.observe();second=self.actor.observe()
        self.assertEqual(first['state'],second['state']);self.assertFalse(first['state']['open'])
    def open(self):self.baseline();call=self.call(0);self.primary.act(call);return call

    def test_normal_script_open_unicode_ray_ime_send_and_independent_original_roles(self):
        self.baseline()
        for index in range(3):
            call=self.call(index);self.primary.act(call);actual=self.primary.observe();peer=self.actor.observe()
            self.assertEqual(actual['state'],peer['state'])
            self.assertTrue(matches(actual['state'],expand(SCENARIOS['world-web']['steps'][index]['state'],context(self.run))))
        self.assertFalse(self.target.qt.opened);self.assertEqual(1,len(self.target.documents))
        self.assertEqual(1,len(self.target.requests));self.assertEqual(1,len(self.target.replies))
        self.assertEqual(1,len([call for call in self.target.normal_inputs if call['controlId']=='scripts.url.submit']))
        self.assertEqual(['tablet.open','tablet.close','input.primary','input.primary'],
            [row['commands'][0]['operation'] for row in self.target.transport.envelopes])
        self.assertEqual('world',self.primary.vm.surface());self.assertEqual('world',self.actor.vm.surface())
        self.assertNotEqual(self.primary.vm.store.path,self.actor.vm.store.path)
        self.assertNotEqual(self.primary.history.last['native']['commandId'],self.actor.history.last['native']['commandId'])
        self.assertEqual([],actual['artifacts']);self.assertTrue(self.primary.store.path.is_file())
        self.assertFalse(any('picoTabletWebFeatureVersion' in path.read_text() for path in self.target.feature_root.glob('*.json')))

    def test_lost_applied_normal_script_submit_keeps_owner_and_cold_never_replays(self):
        self.baseline();call=self.call(0);self.target.fail_script_reply=True
        with self.assertRaises(NativeUIError):self.primary.act(call)
        inputs=deepcopy(self.target.normal_inputs);envelopes=deepcopy(self.target.transport.envelopes)
        self.assertIsNotNone(self.target.current);self.assertIsNotNone(self.target.script_bytes)
        cold=self.facade.prefix(self.target.selector,self.primary.source,self.foreign)
        with self.assertRaises(NativeUIError):cold.act(call)
        self.assertEqual(inputs,self.target.normal_inputs);self.assertEqual(envelopes,self.target.transport.envelopes)
        with self.assertRaises(PhasePending):cold.observe()
        self.assertEqual('acting',unpack(self.primary.store.read()['payload'])[0]['phase'])

    def test_ignored_actual_ray_cannot_gain_focus_or_deliver_ime_and_cold_never_replays(self):
        self.open();self.target.ignore_ray=True;call=self.call(1)
        with self.assertRaises(NativeUIError):self.primary.act(call)
        self.assertFalse(self.target.current['focused']);self.assertEqual('',self.target.current['text'])
        commands=deepcopy(self.target.transport.envelopes)
        self.assertEqual(3,len(commands));self.assertFalse(any(row['original'].get('operation')=='world-browser-ime' for row in self.primary.state['inputs']))
        cold=self.facade.prefix(self.target.selector,self.primary.source,self.foreign)
        with self.assertRaises(NativeUIError):cold.act(call)
        self.assertEqual(commands,self.target.transport.envelopes)

    def test_pending_cannot_publish_after_actual_outer_exit_native_clock_jump(self):
        self.baseline();call=self.call(0);self.target.fail_script_reply=True
        with self.assertRaises(NativeUIError):self.primary.act(call)
        inputs=deepcopy(self.target.normal_inputs);commands=deepcopy(self.target.transport.envelopes)
        cold=self.facade.prefix(self.target.selector,self.primary.source,self.foreign)
        original=self.target.lock.held;exits=[]
        @contextmanager
        def held():
            with original():yield
            self.assertIsNone(self.target.lock._owner);exits.append(True)
            self.clock.base+=2000  # Native/fixture clock; monotonic stays fixed.
        with patch.object(self.target.lock,'held',side_effect=held):
            with self.assertRaises(NativeUIError):cold.observe()
        self.assertEqual([True],exits);self.assertEqual(inputs,self.target.normal_inputs)
        self.assertEqual(commands,self.target.transport.envelopes)
        self.assertEqual('acting',unpack(self.primary.store.read()['payload'])[0]['phase'])

    def prepare_after_outer_change(self,owner,change):
        original=self.target.lock.held;exits=[]
        @contextmanager
        def held():
            with original():yield
            self.assertIsNone(self.target.lock._owner);exits.append(True);change()
        with patch.object(self.target.lock,'held',side_effect=held):
            with self.assertRaises(NativeUIError):owner.prepare()
        self.assertEqual([True],exits)
        self.assertEqual([],self.target.normal_inputs)
        self.assertEqual([],self.target.transport.envelopes)
        self.assertIsNone(self.target.script)
        self.assertTrue(self.primary.store.path.is_file())

    def test_new_prepare_cannot_publish_after_actual_outer_exit_native_clock_jump(self):
        self.prepare_after_outer_change(self.primary,lambda:setattr(self.clock,'base',self.clock.base+2000))

    def test_cold_ready_prepare_cannot_publish_after_actual_outer_exit_native_clock_jump(self):
        self.primary.prepare();raw=self.primary.store.path.read_bytes();sequence=self.target.sequence
        cold=self.facade.prefix(self.target.selector,self.primary.source,self.foreign)
        self.prepare_after_outer_change(cold,lambda:setattr(self.clock,'base',self.clock.base+2000))
        self.assertEqual(raw,self.primary.store.path.read_bytes())
        self.assertEqual(sequence,self.target.sequence)

    def test_new_prepare_cannot_publish_after_actual_outer_exit_phase_advance(self):
        self.prepare_after_outer_change(self.primary,lambda:self.call(0))

    def test_prepare_cannot_publish_after_actual_outer_exit_role_replacement(self):
        self.prepare_after_outer_change(self.primary,lambda:setattr(self.primary,'role','actor'))

    def test_normal_script_url_rejects_foreign_authority_run_ticket_before_writer_and_preserves_missing(self):
        normal,_observe,_binding=self.target._script_runtime(self.target.selector);navigation=normal.io.navigation
        url=self.fixture_url+'tickets/'+'a'*32+'/client.js'
        self.target.qt.opened=self.target.qt.dialog=self.target.qt.focused=True
        with self.assertRaises((NativeUIError,NavigationError)):navigation.input('scripts.url.field','replace',url)
        navigation.bind_feature_client_url(url)
        for foreign in (url.replace('127.0.0.1','localhost'),url.replace(self.run,'b'*32),
                        url.replace('a'*32,'c'*32),url.replace('/client.js','/client.js?foreign=1'),
                        url.replace('/client.js','/not-client.js')):
            with self.subTest(url=foreign),self.assertRaises((NativeUIError,NavigationError)):
                navigation.input('scripts.url.field','replace',foreign)
        self.assertEqual([],self.target.normal_inputs)
        with self.assertRaises((NativeUIError,NavigationError)):navigation.bind_feature_client_url(url.replace('a'*32,'c'*32))
        navigation.input('scripts.url.field','replace',url)
        self.assertEqual(url,self.target.qt.text);self.assertEqual(1,len(self.target.normal_inputs))
        # Existing exact missing.js admission is retained, not reclassified as
        # an admitted browser client. The manager still owns missing execution.
        missing=url.replace('/client.js','/missing.js')
        navigation.input('scripts.url.field','replace',missing)
        self.assertEqual(missing,self.target.qt.text)
        ordinary='http://controlled.test/script-management/'+'d'*32+'/client.js'
        navigation.input('scripts.url.field','replace',ordinary)
        self.assertEqual(ordinary,self.target.qt.text)


if __name__=='__main__':unittest.main()
