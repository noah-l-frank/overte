"""Normal original Python Go To/404 ownership; Qt/VR/native sources synthetic."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
import uuid
from unittest.mock import patch
from adapters.native_location_bookmarks import NativeLocationBookmarks
from adapters.native_navigation_modals import NativeNavigationModals,presented
from adapters.native_navigation_replies import NativeNavigationReplies
from adapters.navigation_missing import NavigationMissing
from adapters.normal_ui import NativeUIError
from adapters.pico4.navigation import PicoNavigation
from adapters.pico4.navigation_lookup import PicoNavigationLookup
from adapters.pico4.normal_scripts import PicoScriptIO
from adapters.pico4.tablet_home import PicoTabletHome
from adapters.token_script_ui import TokenScriptUI
from adapters.script_journey.history import pack,unpack
from feature_journeys.navigation_fixture import NavigationResources,DIRECTORY
from feature_journeys.fixtures import context
from navigation_observation import viewpoint_urls
from self_tests import test_navigation_lookup as lookup
from self_tests import test_native_navigation_modals as modals
from self_tests.test_navigation_arrival import Model as World,SCENE
from self_tests.test_token_places_ui import Widgets
from self_tests.test_pico_tablet_home import original as original_home

RUN=lookup.RUN;TICKET='b'*32;ORIGIN='http://controlled.invalid'


class Source(lookup.Source):
    @property
    def clock(self):return self.world.clock if hasattr(self,'world') else self.local_clock
    @clock.setter
    def clock(self,value):
        if hasattr(self,'world'):self.world.clock=value
        else:self.local_clock=value
    def __init__(self,world):
        super().__init__();self.world=world;self.opened=False;self.owner=None;self.path=None;self.lose=None;self.ignore=None
        self.controller_calls=[];self.hide_modal=True;self.skip_failure=False;self.bad_response=False;self.changed_world=False
        self.modal=modals.Boundary();self.modal.replies.events=[];self.modal.records=[];self.modal.now=lambda:self.clock
        self.modal.replies.epoch=lambda:self.epoch;self.modal.ui_sequence=lambda:self.sequence
        self.inputs_config=dict(protocolSignature='AAAAAAAAAAAAAAAAAAAAAA==',sourceRevision=world.binding['sourceRevision'],sceneUrl=SCENE)
        self.provider=NavigationResources(self.inputs_config,clock_ms=lambda:self.epoch);self.provider.provision(RUN);self.provider.activate(RUN,TICKET)
        self.book=Widgets(world.root);self.book.map[context(RUN)['renamed']]=viewpoint_urls(SCENE)['A'];self.book.persist()
        self.home_sequence=0;self.owned_origin=ORIGIN
    def fetch_missing(self):
        # Default host boundary completes a body without a socket. The joined
        # recovery suite replaces this boundary with the real loopback server.
        with self.provider.response(DIRECTORY+'/'+context(RUN)['hidden'],'') as response:return response
    def check(self,kind,control=None):
        assert self.owner is not None
        state=unpack(json.loads(self.path.read_text())['payload'])[0];p=state['pending'];assert p['kind']==kind
        if control:assert p['input']['controlId']==control
    def controller(self,operation):
        self.check('open' if not self.controller_calls else 'reopen');self.controller_calls.append(operation)
        if self.ignore==operation:return
        self.intents.append(dict(control=operation));super().controller(operation);self.generation=str(uuid.uuid4())
        if self.lose==operation:raise NativeUIError('Synthetic applied controller result lost')
    def send(self,command):
        control,action=command['controlId'],command['action'];self.check('qt',control);self.intents.append(dict(control=control))
        if self.ignore==control+':'+action:
            self.sequence+=1;self.inputs.append(deepcopy(command))
            return dict(schemaVersion=1,bridgeId=self.bridge,commandId=command['commandId'],sequence=self.sequence,performed=True,
                error='',processId=self.pid,updatedEpochMs=self.epoch),self.epoch
        reply,epoch=super().send(command)
        if control=='navigation.address' and action=='submit':
            self.generation=str(uuid.uuid4())
            if self.changed_world:self.world.position='A'
            if not self.skip_failure:
                status,body,nonce=self.fetch_missing()
                self.modal.replies.generation+=1;self.modal.replies.error(nonce,origin=self.owned_origin)
                if self.bad_response:self.modal.replies.events[-1]['responseId']='8'*32
                self.modal.event=deepcopy(self.modal.replies.events[-1]);self.modal.create()
                if not self.hide_modal:self.opened=True
        if self.lose==control+':'+action:raise NativeUIError('Synthetic applied Qt result lost')
        return reply,epoch
    def home(self):
        self.home_sequence+=1
        return original_home()|dict(commandId=uuid.uuid4().hex,processId=self.pid,sourceSequence=self.home_sequence,
            elapsedMs=round(self.clock*1000),capturedEpochMs=self.epoch,tabletShown=self.opened,onHomeScreen=self.page=='home')
    def bookmark_reader(self):
        def send(request):self.book.clock=self.clock;self.book.native_send(request);self.book.native_packet['processId']=31
        return NativeLocationBookmarks(send,lambda:json.dumps(self.book.native_packet),lambda:self.epoch,self.guard,31,
            monotonic=lambda:self.clock,sleep=self.sleep)
    def replies(self):
        def raw():
            value=json.loads(self.modal.replies.original());value['processId']=31;return json.dumps(value)
        return NativeNavigationReplies(self.modal.replies.send,raw,lambda:self.epoch,self.guard,31,monotonic=lambda:self.clock,sleep=self.sleep)
    def modals(self):
        def send(request):
            self.modal.send(request);self.modal.cached.update(processId=31,uiBridgeId=self.bridge,uiGeneration=self.generation,tabletOpen=self.opened)
        return NativeNavigationModals(send,self.modal.original,lambda:self.epoch,self.guard,31,monotonic=lambda:self.clock,sleep=self.sleep)


class NavigationMissingTests(unittest.TestCase):
    def setUp(self):
        self.world=World(run=RUN);self.addCleanup(self.world.close);self.world.position='B';self.native=Source(self.world)
        self.world.binding['sessionId']=self.native.bridge;self.path=self.world.root/'missing.json';self.native.path=self.path
        self.navigation=PicoNavigation(self.native,self.world.root/'ui.json',lookup.IDENTITY,'31:synthetic-start',SCENE,
            monotonic=lambda:self.world.clock,sleep=self.world.sleep)
        self.normal=TokenScriptUI(PicoScriptIO(self.navigation),monotonic=lambda:self.world.clock,sleep=self.world.sleep)
        source=SimpleNamespace(pid=31,capture=self.native.home,clock_ms=lambda:self.native.epoch,guard=self.native.guard,
            monotonic=lambda:self.world.clock,sleep=self.world.sleep)
        self.home=PicoTabletHome(source,lambda _:self.fail('No Home ray in lookup input'))
    def owner(self):
        owner=NavigationMissing(lambda intent:PicoNavigationLookup(self.normal,self.native.panels(),intent,RUN),self.world.arrival(),self.home,
            self.native.bookmark_reader(),self.native.replies(),self.native.modals(),lambda:self.native.provider.snapshot(RUN),self.path,
            RUN,self.world.binding,self.native.provider.instance,self.native.inputs_config,self.native.owned_origin,self.native.guard,
            monotonic=lambda:self.world.clock,sleep=self.world.sleep)
        self.native.owner=owner;return owner
    def act(self):return self.owner().act(TICKET)
    def test_normal_goto_uses_original_404_hidden_modal_and_one_reopen_with_unchanged_b_and_bookmarks(self):
        before=self.native.book.storage();self.assertEqual(dict(performed=True),self.act());state=self.owner().state
        self.assertEqual('visible',state['phase']);self.assertEqual('B',self.world.position);self.assertEqual(before,self.native.book.storage())
        self.assertEqual(['tablet.open','tablet.open'],self.native.controller_calls)
        self.assertEqual(['tablet.page.2','navigation.goto','navigation.address','navigation.address','navigation.address'],[r['controlId'] for r in self.native.inputs])
        self.assertEqual(lookup.MISSING,self.native.entered[0]);self.assertEqual(404,state['joined']['response']['status'])
        self.assertEqual(state['joined']['event'],presented(state['last']['modal'],state['joined']['event'])['event'])
        self.assertFalse(state['last']['ui']['native']['roots'][0]['alive']);count=len(self.native.inputs);self.act();self.assertEqual(count,len(self.native.inputs))
    def test_lost_open_page_goto_focus_replace_submit_and_reopen_results_never_reissue_their_input(self):
        for control in ('tablet.open','tablet.page.2:activate','navigation.goto:activate','navigation.address:activate','navigation.address:replace','navigation.address:submit'):
            self.setUp();self.native.lose=control
            with self.subTest(control=control),self.assertRaises(NativeUIError):self.act()
            count=len(self.native.inputs);controllers=len(self.native.controller_calls);self.assertIsNotNone(self.owner().state['pending'])
            self.native.lose=None;self.act();self.assertEqual('visible',self.owner().state['phase'])
            if control=='tablet.open':self.assertEqual(2,len(self.native.controller_calls))
            else:self.assertEqual(1,sum(r['controlId']+':'+r['action']==control for r in self.native.inputs))
        self.setUp();calls=[];controller=self.native.controller
        def lost_reopen(operation):
            controller(operation);calls.append(operation)
            if len(calls)==2:raise NativeUIError('Synthetic applied reopen result lost')
        self.native.controller=lost_reopen
        with self.assertRaises(NativeUIError):self.act()
        self.native.controller=controller;self.act();self.assertEqual(2,len(self.native.controller_calls))
    def test_ignored_input_missing_native_failure_or_foreign_response_cannot_pass_or_replay(self):
        for fault in ('tablet.open','tablet.page.2:activate','navigation.goto:activate','navigation.address:activate','navigation.address:replace',
                      'navigation.address:submit','failure','response','world'):
            self.setUp()
            if fault=='failure':self.native.skip_failure=True
            elif fault=='response':self.native.bad_response=True
            elif fault=='world':self.native.changed_world=True
            else:self.native.ignore=fault
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):self.act()
            count=len(self.native.inputs);controllers=len(self.native.controller_calls)
            with self.assertRaises(NativeUIError):self.act()
            self.assertEqual(count,len(self.native.inputs));self.assertEqual(controllers,len(self.native.controller_calls))
    def test_actual_visible_modal_needs_no_second_tablet_open_and_no_synthetic_error_replacement(self):
        self.native.hide_modal=False;self.act();self.assertEqual(['tablet.open'],self.native.controller_calls)
        self.assertEqual(1,len(self.native.modal.records));self.assertEqual(1,len(self.native.modal.replies.events))
    def test_foreign_initial_ui_or_bookmark_change_and_replacement_ticket_keep_ownership(self):
        self.native.opened=True
        with self.assertRaises(NativeUIError):self.act()
        self.assertFalse(self.native.inputs);self.assertFalse(self.native.controller_calls)
        self.setUp();self.native.lose='navigation.address:submit'
        with self.assertRaises(NativeUIError):self.act()
        with self.assertRaises(NativeUIError):self.owner().act('8'*32)
        self.native.book.map['Foreign']='hifi://foreign.invalid';self.native.book.persist();count=len(self.native.inputs)
        with self.assertRaises(NativeUIError):self.act()
        self.assertEqual(count,len(self.native.inputs))
    def test_changed_saved_native_scope_or_pending_url_refuses_recreation(self):
        for fault in ('url','pid','nonce'):
            self.setUp();self.native.lose='navigation.address:replace'
            with self.assertRaises(NativeUIError):self.act()
            disk=json.loads(self.path.read_text());state=unpack(disk['payload'])[0];p=state['pending']['input']
            if fault=='url':p['text']='hifi://foreign'
            elif fault=='pid':p['native']['processId']=32
            else:p['native']['commandId']='8'*32
            disk['payload']=pack([state]);self.path.write_text(json.dumps(disk));self.path.chmod(0o600)
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):self.owner()
    def test_completed_history_cannot_drop_or_reorder_inputs_or_change_the_submit_barrier(self):
        self.act();original=json.loads(self.path.read_text())
        for fault in ('drop','order','barrier','original-counter','last-counter'):
            disk=deepcopy(original);state=unpack(disk['payload'])[0]
            if fault=='drop':state['history'].pop(1)
            elif fault=='order':state['history'][1:3]=reversed(state['history'][1:3])
            elif fault=='barrier':state['submitEpochMs']+=1
            else:
                group=state['original'] if fault=='original-counter' else state['last']
                group['ui']['scope']['sequence']+=1
                group['ui']['native']['ui']['sequence']+=1;group['modal']['uiInputSequence']+=1
            disk['payload']=pack([state]);self.path.write_text(json.dumps(disk));self.path.chmod(0o600)
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):self.owner()
    def test_unrelated_qt_input_after_completion_does_not_borrow_the_original_lookup(self):
        self.act();count=len(self.native.inputs);self.native.sequence+=1
        with self.assertRaises(NativeUIError):self.act()
        self.assertEqual(count,len(self.native.inputs));self.assertEqual(2,len(self.native.controller_calls))
    def test_actual_private_factory_reuses_original_manager_and_requires_the_shared_source_lock(self):
        import sys
        sys.path.insert(0,str(Path(__file__).resolve().parents[3]/'android/vr/pico/tests/device'))
        import test_native_execution_binding as n
        fixture=n.NativeExecutionBindingTest();fixture.setUp();self.addCleanup(fixture.doCleanups);adapter=fixture.instance()
        adapter._scripts=lambda target:SimpleNamespace(ui=self.normal,binding=self.world.binding)
        adapter._native_feature_observer=lambda target:SimpleNamespace(guard=self.native.guard,monotonic=lambda:self.world.clock,sleep=self.world.sleep)
        adapter._navigation_arrival=lambda target,run,scene:self.world.arrival()
        adapter._navigation_panels=lambda target:self.native.panels()
        adapter._location_bookmarks=lambda target:self.native.bookmark_reader()
        adapter._navigation_replies=lambda target:self.native.replies()
        adapter._navigation_modals=lambda target:self.native.modals()
        def lock(_self,target,provided):
            self.assertEqual('owned',target);self.assertIs(self.world.lock,provided);return provided
        with patch('adapters.pico4.graphics_binding.PicoGraphicsBinding._lock',lock),patch('adapters.pico4.tablet_home.bind_home',return_value=self.home):
            owner=adapter._navigation_missing('owned',self.path,RUN,lambda:self.native.provider.snapshot(RUN),
                self.native.provider.instance,self.native.inputs_config,ORIGIN,source_lock=self.world.lock)
            self.native.owner=owner
            with self.assertRaises(NativeUIError):owner.act(TICKET)
            self.assertFalse(self.native.controller_calls);self.assertFalse(self.native.inputs)
            with self.world.lock.held():self.assertEqual(dict(performed=True),owner.act(TICKET))


if __name__=='__main__':unittest.main()
