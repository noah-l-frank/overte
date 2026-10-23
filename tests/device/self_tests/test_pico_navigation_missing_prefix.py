"""Nine continuous ordinary actions and real TLS404; Qt/VM/OS remain models.

No baseline bookmark, fabricated transit, direct lookup handler or second input
stack replaces the actual preceding eight actions. Originals survive failures.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
import sys
from types import SimpleNamespace
import unittest
from urllib.error import HTTPError
import uuid

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from adapters.native_navigation_replies import NativeNavigationReplies
from adapters.navigation_missing import NavigationMissing
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.pico4.navigation_lookup import PicoNavigationLookup
from adapters.pico4.navigation_missing_join import NavigationMissingJoin
from adapters.pico4.tablet_home import PicoTabletHome
from adapters.script_journey.history import unpack
from adapters.token_script_ui import TokenScriptUI
from feature_journeys.fixtures import context
from feature_journeys.navigation_fixture import DIRECTORY
from feature_journeys.scenarios import SCENARIOS,expand,VERSION as CONTRACT_VERSION
from self_tests import test_navigation_lookup as lookup
from self_tests import test_native_navigation_modals as modals
from self_tests import test_pico_navigation_prefix as prefix
from self_tests import test_pico_navigation_transit_prefix as transit
from self_tests.test_pico_tablet_home import original as home_original


class Model(transit.Model):
    def __init__(self,root):
        super().__init__(root);self.lookup_mode=False;self.lookup=lookup.Source();self.lookup.text=''
        self.modal=modals.Boundary();self.modal.records=[];self.modal.replies.events=[]
        self.modal.now=lambda:self.clock;self.modal.ui_sequence=lambda:self.sequence
        self.modal.replies.epoch=self.epoch;self.lose_submit=False;self.bad_response=False;self.http_originals=[]
    def sync_lookup(self):
        value=self.lookup;value.clock=self.clock;value.pid=prefix.PID;value.bridge=self.bridge
        value.generation=self.generation;value.sequence=self.sequence;value.opened=self.shown
        value.extra_roots=[] if self.root_birth is None else [dict(rootId='e'*32,profile='pico-places-v1',sourceSha256='d'*64,
            firstObservedEpochMs=self.root_birth,alive=not self.root_dead,inCurrentTree=self.page,visible=self.page)]
    def raw(self):
        if not self.lookup_mode:value=super().raw()
        else:
            self.sync_lookup();value=self.lookup.snapshot()
            value.update(placesControlsVersion=1,navigationOriginControlsVersion=1,elapsedMs=100+round(self.clock*1000))
        value.update(navigationAddressVersion=1,navigationLookupControlsVersion=1)
        return value
    def private(self,request,kind):
        super().private(request,kind);original=self.native_packets[kind]
        if kind=='panels' and self.lookup_mode:
            self.sync_lookup();self.lookup.observe(request);value=deepcopy(self.lookup.native)
            value.update(instance=original['instance'],sequence=original['sequence']);value['ui']['elapsedMs']+=100
            self.native_packets[kind]=value
        elif kind=='modals':
            self.modal.send(request);value=deepcopy(self.modal.cached)
            value.update(instance=original['instance'],sequence=original['sequence'],processId=prefix.PID,
                uiBridgeId=self.bridge,uiGeneration=self.generation,tabletOpen=self.shown)
            for row in value['records']:
                if row['rootAlive']:row.update(visible=self.shown,inCurrentTree=self.shown)
            self.native_packets[kind]=value
    def replies_reader(self):
        source=self.modal.replies
        def raw():
            value=json.loads(source.original());value['processId']=prefix.PID;return json.dumps(value)
        return NativeNavigationReplies(source.send,raw,self.epoch,self.guard,prefix.PID,monotonic=lambda:self.clock,sleep=self.sleep)
    def consume_controller(self,envelope):
        if envelope['commands'][0]['operation']!='tablet.open':return super().consume_controller(envelope)
        child=self.owner_test.flow.missing_join.lookup
        pending=unpack(json.loads(child.store.path.read_text())['payload'])[0]['pending']
        assert pending is not None and pending['kind'] in ('open','reopen')
        self.controller_calls.append(deepcopy(envelope));self.lookup_mode=True;self.shown=True;self.generation=str(uuid.uuid4())
    def send(self,command):
        if not self.lookup_mode or not (command['controlId'].startswith('navigation.') or command['controlId'].startswith('tablet.page.')):
            return super().send(command)
        child=self.owner_test.flow.missing_join.lookup
        pending=unpack(json.loads(child.store.path.read_text())['payload'])[0]['pending']
        assert pending['kind']=='qt' and pending['input']['controlId']==command['controlId'] and pending['input']['action']==command['action']
        self.sync_lookup();self.lookup.intents.append(dict(control=command['controlId']))
        reply,_epoch=self.lookup.send(command);self.calls.append(deepcopy(command))
        self.sequence=self.lookup.sequence;self.shown=self.lookup.opened
        if command['controlId']=='navigation.address' and command['action']=='submit':
            self.generation=str(uuid.uuid4());self.fetch_missing()
            if self.lose_submit:raise NativeUIError('Synthetic normal Submit applied response lost')
        return reply,self.epoch()
    def fetch_missing(self):
        # Original normal address delivery reaches this explicit native-network
        # seam. The actual owned TLS response/header/body are acquired once.
        target=self.network+DIRECTORY+'/'+context(prefix.RUN)['hidden']
        try:
            with self.owner_test.opener.open(target,timeout=2) as response:status,body,header=response.status,response.read(),response.headers['X-Overte-Fixture-Response']
        except HTTPError as error:
            with error:status,body,header=error.code,error.read(),error.headers['X-Overte-Fixture-Response']
            assert error.closed
        raw=dict(url=target,status=status,body=body.decode('utf-8'),responseId=header,sha256=hashlib.sha256(body).hexdigest(),capturedEpochMs=self.epoch())
        self.http_originals.append(deepcopy(raw));store=PrivateFeatureState(self.root/'navigation-prefix-http-missing.json')
        store.write(dict(originals=deepcopy(self.http_originals)),store.read())
        source=self.modal.replies;source.generation+=1;source.error(header,origin=self.network)
        source.events[-1].update(httpStatus=status,networkError=203 if status==404 else 299,contentNotFound=status==404)
        if self.bad_response:source.events[-1]['responseId']='f'*32
        self.modal.event=deepcopy(source.events[-1]);self.modal.create()


@unittest.skipUnless(shutil.which('openssl'),'Existing ephemeral TLS fixture requires OpenSSL')
class NavigationMissingPrefixTests(unittest.TestCase):
    model_type=Model
    setUpClass=classmethod(prefix.NavigationPrefixTests.setUpClass.__func__)
    tearDownClass=classmethod(prefix.NavigationPrefixTests.tearDownClass.__func__)
    setUp=prefix.NavigationPrefixTests.setUp
    write=prefix.NavigationPrefixTests.write
    read=prefix.NavigationPrefixTests.read
    installed=prefix.NavigationPrefixTests.installed
    def activate(self,verb):
        if verb not in ('navigate-missing','dismiss-error'):return prefix.NavigationPrefixTests.activate(self,verb)
        self.ticket=uuid.uuid4().hex;self.server.journal.activate(prefix.RUN,self.ticket,verb,{})
        self.model.provider.activate(prefix.RUN,self.ticket)
        return dict(contractVersion=CONTRACT_VERSION,runId=prefix.RUN,fixtureUrl=self.url+'/feature-fixture/v1/runs/'+prefix.RUN+'/',ticket=self.ticket,verb=verb,inputs={})
    def make(self,role):
        parent=transit.NavigationTransitPrefixTests.make(self,role);m=self.model
        parent.source.readers['replies']=m.replies_reader();parent.source.version=2
        def factory(owner):
            def home():
                self.home_sequence+=1
                return home_original()|dict(commandId=uuid.uuid4().hex,processId=prefix.PID,sourceSequence=self.home_sequence,
                    elapsedMs=100+round(m.clock*1000),capturedEpochMs=m.epoch(),tabletShown=m.shown,
                    onHomeScreen=(m.lookup.page=='home' if m.lookup_mode else not m.page and not m.login))
            source=SimpleNamespace(pid=prefix.PID,capture=home,guard=m.guard,clock_ms=m.epoch,monotonic=lambda:m.clock,sleep=m.sleep)
            normal=TokenScriptUI(owner.source.normal.io.original,monotonic=lambda:m.clock,sleep=m.sleep)
            child=NavigationMissing(lambda intent:PicoNavigationLookup(normal,owner.source.readers['panels'],intent,prefix.RUN),
                owner.source.arrival,PicoTabletHome(source,lambda _pose:None),owner.source.readers['bookmarks'],owner.source.readers['replies'],
                owner.source.readers['modals'],owner.directory.status,self.root/'navigation-prefix-missing.json',prefix.RUN,self.binding,
                m.provider.instance,prefix.INPUTS,self.url,m.guard,monotonic=lambda:m.clock,sleep=m.sleep)
            return NavigationMissingJoin(owner,child,self.root/'navigation-prefix-missing-join.json')
        parent.missing_factory=factory;return parent
    def first_eight(self):
        self.flow.prepare()
        for verb in prefix.VERBS[:8]:self.flow.act(self.activate(verb))
    def test_continuous_nine_normal_steps_tls404_and_independent_visible_original_modal(self):
        self.flow.prepare();self.flow.observe();actor=self.make('actor');actor.observe()
        for index,verb in enumerate(prefix.VERBS[:9]):
            self.flow.act(self.activate(verb));actual=self.flow.observe();peer=actor.observe()
            expected=expand(SCENARIOS['world-navigation']['steps'][index]['state'],context(prefix.RUN))
            if index==8:self.assertIn(actual['state']['addressDialog'],expected.pop('addressDialog')['oneOf'])
            self.assertEqual(expected,{k:v for k,v in actual['state'].items() if k in expected});self.assertEqual(actual['state'],peer['state'])
        self.assertEqual('not-found',actual['state']['error']);self.assertEqual('B',actual['state']['location'])
        self.assertEqual(['hifi://hidden-'+prefix.RUN],self.model.lookup.entered);self.assertEqual(1,len(self.model.http_originals))
        raw=self.model.http_originals[0];self.assertEqual(404,raw['status'])
        child=self.flow.missing().lookup;self.assertEqual(raw['responseId'],child.state['joined']['event']['responseId'])
        self.assertEqual('visible',child.state['phase']);self.assertTrue(self.model.shown)
        self.assertEqual(['input.primary','input.primary','tablet.close','tablet.open','tablet.open'],
            [row['commands'][0]['operation'] for row in self.model.controller_calls])
        self.assertFalse(actual['fullNavigationRecipe']);self.assertTrue(actual['journalsRetained'])
    def test_lost_applied_normal_submit_recovers_original404_without_resend_or_another_fetch(self):
        self.first_eight();call=self.activate('navigate-missing');self.model.lose_submit=True
        with self.assertRaises(NativeUIError):self.flow.act(call)
        self.assertEqual(1,len(self.model.lookup.entered));self.assertEqual(1,len(self.model.http_originals));self.model.lose_submit=False
        self.flow=self.make('primary');self.flow.act(call);self.assertEqual(1,len(self.model.lookup.entered));self.assertEqual(1,len(self.model.http_originals))
        self.assertEqual('not-found',self.flow.observe()['state']['error'])
    def test_foreign_native_response_id_retains_original_submit_and_never_retries_input(self):
        self.first_eight();call=self.activate('navigate-missing');self.model.bad_response=True
        with self.assertRaises(NativeUIError):self.flow.act(call)
        self.assertEqual(1,len(self.model.http_originals));self.assertEqual(1,len(self.model.lookup.entered))
        self.model.bad_response=False;self.flow=self.make('primary')
        with self.assertRaises(NativeUIError):self.flow.act(call)
        self.assertEqual(1,len(self.model.http_originals));self.assertEqual(1,len(self.model.lookup.entered))
    def test_original_eight_action_version_three_envelope_cannot_acquire_a_ninth_input(self):
        self.first_eight();previous=self.flow.store.read();legacy=deepcopy(previous)
        legacy['navigationPrefixVersion']=3;legacy.pop('lookupReceipt')
        self.flow.store.write(legacy,previous);self.flow=self.make('primary');before=deepcopy(self.model.controller_calls)
        with self.assertRaises(NativeUIError):self.flow.act(self.activate('navigate-missing'))
        self.assertEqual(before,self.model.controller_calls);self.assertEqual([],self.model.http_originals)
        self.assertIsNone(self.flow.missing_join)

    def test_last_original_phase_fence_prevents_submit_writer_after_its_durable_intent(self):
        self.first_eight();call=self.activate('navigate-missing');guard=self.flow.source.guard;changed=[]
        def advance():
            rows=self.flow.state['deliveries']
            if rows and rows[-1]['controlId']=='navigation.address' and rows[-1]['action']=='submit' and not changed:
                changed.append(True);self.activate('dismiss-error')
            return guard()
        self.flow.source.guard=advance
        with self.assertRaises(NativeUIError):self.flow.act(call)
        self.assertTrue(changed);self.assertEqual([],self.model.lookup.entered);self.assertEqual([],self.model.http_originals)
        self.assertEqual('submit',self.flow.missing_join.lookup.state['pending']['input']['action'])


if __name__=='__main__':unittest.main()
