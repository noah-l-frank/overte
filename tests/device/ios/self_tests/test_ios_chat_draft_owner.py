"""Real draft WAL/locks/original files; explicit Qt/keyboard/settings models.

No product process, real keyboard, Chat delivery or installed binary executes.
Native clocks deliberately differ from host epoch; retained source clocks stay
native. Normal input effects and independent source reads use separate paths.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from copy import deepcopy
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
import uuid

from adapters.native_chat_view import NativeChatView
from adapters.native_feature_observation import NativeFeatureObservation,need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.lock import ScriptSourceLock
from adapters.script_feature.history import unpack
from feature_journeys.fixtures import context
from feature_journeys.phase_fixture import PhaseFixtureReader
from feature_journeys.witness import Client
from ios.adapters.chat_controls import IOSChatIO
from ios.adapters.chat_draft_owner import IOSChatDraftOwner
from ios.adapters.chat_draft_clock import Budget
from ios.adapters.normal_input import observation as ui_packet
from ios.self_tests.test_ios_create_files import BINDING
from self_tests.test_native_feature_observation import Boundary as NativeBoundary
from self_tests.test_token_chat_ui import Widgets

RUN='a'*32


class DraftModel:
    def __init__(self):
        self.widgets=Widgets();self.widgets.pid=42;self.widgets.instance=str(uuid.UUID('b'*32))
        self.widgets.generation=str(uuid.UUID('c'*32));capture=self.widgets.capture
        def original_controls():
            value=capture()
            for row in value['controls']:
                row['token']=str(uuid.UUID(row['token']))
                if row['id'].startswith('tablet.'):row.pop('inputReady',None)
            return value
        self.widgets.capture=original_controls
        self.native=NativeBoundary();self.owner=None;self.last_receipt=None;self.view_value=None;self.view_sequence=0
        self.keyboard=False;self.ghost_keyboard=False;self.keyboard_available=True;self.changed=False;self.hidden_draft=False
        self.storage=dict(kind='unset',count=0,unowned=0,events=[],configSha256='d'*64)
        self.phase_sequence=0;self.activations=[];self.add_phase('open',{},'1'*32)
        self.lose_after_replace=False;self.lose_after_focus=False;self.late_view=False;self.freeze_view=False

    def tick(self):self.widgets.clock+=.001;self.widgets.elapsed+=1
    def epoch(self):return 5000000+round(self.widgets.clock*1000)
    def native_epoch(self):return 100000+round(self.widgets.clock*1000)
    def sleep(self,seconds):self.widgets.sleep(seconds)
    def guard(self):return not self.changed
    def add_phase(self,verb,inputs,ticket):
        self.verb,self.inputs,self.ticket=verb,deepcopy(inputs),ticket
        self.activations.append(dict(sequence=len(self.activations)+1,ticket=ticket,activatedEpochMs=self.epoch(),stimulus=dict(verb=verb,inputs=deepcopy(inputs))))
    def query(self,command):self.owner.query_intent(command)
    def send_native(self,command):
        self.query(command);self.tick();self.native.send(command)
        value=self.native.sample;value.update(instance='e'*32,processId=42,capturedEpochMs=self.native_epoch(),requestedEpochMs=self.native_epoch(),animation={})
        value.pop('animationFence',None)
    def native_reader(self):
        return NativeFeatureObservation(self.send_native,lambda:json.dumps(self.native.sample),self.native_epoch,self.guard,42,
            ios=True,monotonic=lambda:self.widgets.clock,sleep=self.sleep)
    def capture(self):
        command=dict(schemaVersion=1,commandId='ios-'+uuid.uuid4().hex,action='normal-ui-input',operation='observe')
        self.query(command);self.tick();actual=self.widgets.capture()
        value=dict(schemaVersion=1,instance=actual['scope']['instance'],frameSpace='qt-window-logical',processId=42,
            sampleEpochMs=self.native_epoch(),elapsedMs=actual['scope']['elapsedMs'],lastSequence=actual['scope']['sequence'],
            tabletShown=actual['open'],ready=actual['ready'],chatControlsVersion=1,chatGeneration=actual['scope']['generation'],
            controls=[row|{'frame':dict(x=10,y=10,width=100,height=40)} for row in actual['controls']])
        ui_packet(value,42,self.native_epoch());self.last_receipt=dict(schemaVersion=1,commandId=command['commandId'],observation=deepcopy(value));return value
    def chat_input(self,identifier,action,*,reference,value=None):
        self.widgets.input(identifier,action,reference,value)
        self.keyboard=self.widgets.focus;self.tick()
        if self.lose_after_focus and identifier=='chat.input' and action=='activate':raise NativeUIError('Explicit lost focus return')
        if self.lose_after_replace and action=='replace':raise NativeUIError('Explicit lost replacement return')
    def send_view(self,command):
        self.query(command);self.tick()
        if self.late_view:self.sleep(2)
        if self.freeze_view:return
        self.view_sequence+=1;w=self.widgets
        ui=dict(present=False)
        if w.panel:
            ui=dict(present=True,generation=uuid.uuid5(uuid.NAMESPACE_URL,'draft-page-'+str(w.page_life)).hex,
                channel=w.channel,draft=w.draft,keyboardRequested=w.keyboard_request,
                localMessages=deepcopy(w.local),domainMessages=deepcopy(w.domain),visibleMessages=deepcopy(w.local if w.channel=='local' else w.domain),
                localRowCount=len(w.local),domainRowCount=len(w.domain),visibleRowCount=len(w.local if w.channel=='local' else w.domain))
        keyboard=dict(available=True,backend='native-touch-metrics',visible=self.keyboard or self.ghost_keyboard) if self.keyboard_available else dict(available=False)
        self.view_value=dict(chatViewVersion=1,commandId=command['commandId'],runId=RUN,instance='f'*32,sequence=self.view_sequence,
            processId=42,capturedEpochMs=self.native_epoch(),source=dict(tabletShown=True,editorFocused=w.focus,
                editorHasDraft=bool(w.draft) or self.hidden_draft,keyboard=keyboard,ui=ui,storage=deepcopy(self.storage)))
    def view_reader(self):
        return NativeChatView(self.send_view,lambda:json.dumps(self.view_value),self.native_epoch,self.guard,42,ios=True,
            monotonic=lambda:self.widgets.clock,sleep=self.sleep)
    def client(self):
        model=self
        class PhaseClient(Client):
            def request(self,path,value=None,method=None,*,phase_nonce=None,**_kwargs):
                need(path=='/runs/'+RUN+'/phase' and phase_nonce is not None);model.phase_sequence+=1
                return dict(fixturePhaseVersion=1,instance='2'*32,sequence=model.phase_sequence,requestId=phase_nonce,runId=RUN,area='chat',
                    capturedEpochMs=model.epoch(),active=True,createdEpochMs=4999999,retiredEpochMs=None,activations=deepcopy(model.activations))
        return PhaseClient('https://controlled.invalid/feature-fixture/v1','r'*64)


class ChatDraftOwnerTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name);self.root.chmod(0o700)
        self.store=PrivateFeatureState(self.root/'ios-chat-draft-owner.json');self.lock=ScriptSourceLock(self.root/'script-feature-sources.lock');self.model=DraftModel()
    @contextmanager
    def owner(self):
        model=self.model;failure=None
        with self.lock.held():
            try:
                owner=IOSChatDraftOwner(self.store,self.root,BINDING,RUN,self.lock,model.guard,native=model.native_reader(),
                    io=IOSChatIO(SimpleNamespace(capture=model.capture,native=model)),view=model.view_reader(),
                    phase=PhaseFixtureReader(model.client(),RUN,'chat',epoch_ms=model.epoch,monotonic=lambda:model.widgets.clock),
                    epoch_ms=model.epoch,monotonic=lambda:model.widgets.clock,sleep=model.sleep)
                model.owner=owner;yield owner
            except BaseException as original:failure=original
        if failure is not None:raise failure
    def act(self):
        with self.owner() as owner:return owner.act(self.model.ticket,self.model.verb,self.model.inputs)
    def phase(self,verb,inputs,ticket):self.model.add_phase(verb,inputs,ticket)
    def open(self):return self.act()
    def typed(self):
        self.open();self.phase('type',dict(text=context(RUN)['unicode']),'3'*32);return self.act()

    def test_normal_open_type_close_reopen_and_final_close_retain_actual_originals(self):
        self.typed();self.phase('close',{},'4'*32);closed=self.act();self.assertFalse(closed['local']['open'])
        self.phase('open',{},'5'*32);opened=self.act();self.assertEqual('',opened['local']['draft'])
        self.phase('close',{},'6'*32);self.act()
        inputs=deepcopy(self.model.widgets.calls);sequence=self.model.view_sequence
        with self.lock.held():
            original=IOSChatDraftOwner.archive(self.store,self.root,BINDING,RUN,self.lock,self.model.owner.fixture_url)
            self.assertEqual(5,len(original.state['operations']));self.assertEqual([],original.state['failures'])
            closed=original.state['operations'][-1];original.quiet(closed)
            self.assertEqual(3,len(closed['quiet']));self.assertFalse(original.local(original.original(closed['after']))['keyboard'])
            frame=original.original(original.state['records'][0]);self.assertLess(frame['clockJoin']['nativeAfter']['capturedEpochMs'],frame['clockJoin']['hostBeforeEpochMs'])
        self.assertEqual(inputs,self.model.widgets.calls);self.assertEqual(sequence,self.model.view_sequence);self.assertEqual([],self.model.widgets.sent)
        self.assertEqual('unset',self.model.storage['kind']);self.assertNotIn('performed',opened)

    def test_lost_replacement_return_resolves_new_actual_draft_without_duplicate_inputs(self):
        self.open();self.phase('type',dict(text=context(RUN)['unicode']),'3'*32);self.model.lose_after_replace=True
        with self.assertRaises(NativeUIError):self.act()
        calls=deepcopy(self.model.widgets.calls);self.model.lose_after_replace=False
        result=self.act();self.assertEqual(context(RUN)['unicode'],result['local']['draft']);self.assertEqual(calls,self.model.widgets.calls)

    def test_uncertain_intermediate_focus_is_not_replayed_and_explicit_cleanup_remains_failed(self):
        self.open();self.phase('type',dict(text=context(RUN)['unicode']),'3'*32);self.model.lose_after_focus=True
        with self.assertRaises(NativeUIError):self.act()
        calls=deepcopy(self.model.widgets.calls);self.model.lose_after_focus=False
        with self.assertRaises(NativeUIError):self.act()
        self.assertEqual(calls,self.model.widgets.calls)
        self.phase('cleanup',{},'4'*32)
        with self.owner() as owner:
            result=owner.cleanup(self.model.ticket);self.assertTrue(result['failed']);self.assertFalse(result['local']['open'])
            self.assertEqual(1,len(owner.state['failures']));self.assertEqual(1,len(owner.state['failures'][0]['intents']))

    def test_unowned_history_preexisting_draft_and_unavailable_keyboard_refuse_before_input(self):
        for fault in ('history','draft','keyboard'):
            self.setUp()
            if fault=='history':self.model.storage.update(kind='array',count=1,unowned=1)
            elif fault=='draft':self.model.widgets.panel=True;self.model.widgets.draft=context(RUN)['unicode']
            else:self.model.keyboard_available=False
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):self.act()
            self.assertEqual([],self.model.widgets.calls)

    def test_ghost_keyboard_hidden_draft_or_changed_settings_cannot_qualify_close(self):
        for fault in ('keyboard','hidden','settings'):
            self.setUp();self.typed();self.phase('close',{},'4'*32)
            if fault=='keyboard':self.model.ghost_keyboard=True
            elif fault=='hidden':self.model.hidden_draft=True
            else:self.model.storage['configSha256']='a'*64
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):self.act()
            self.assertIsNotNone(self.store.read())

    def test_missing_or_replaced_original_and_wrong_source_remain_unavailable(self):
        self.typed()
        with self.owner() as owner:
            path=owner.frames.path(owner.frames.expand(owner.state['records'][0]));replacement=path.with_suffix('.replacement')
            replacement.write_bytes(path.read_bytes());replacement.chmod(0o600);replacement.replace(path)
        with self.assertRaises(NativeUIError),self.owner():pass

    def test_late_or_ignored_native_view_and_ignored_input_do_not_supply_success(self):
        self.model.late_view=True
        with self.assertRaises(NativeUIError):self.act()
        self.assertEqual([],self.model.widgets.calls)
        self.setUp();self.model.widgets.ignore_effect=True
        with self.assertRaises(NativeUIError):self.act()
        self.assertEqual(1,len(self.model.widgets.calls));self.assertIsNotNone(self.model.owner.state['pending'])

    def test_failed_primitive_intent_write_blocks_the_actual_input(self):
        self.open();self.phase('type',dict(text=context(RUN)['unicode']),'3'*32)
        calls=deepcopy(self.model.widgets.calls)
        with self.owner() as owner:
            original=owner.store.write
            def write(value,previous):
                pending=unpack(value['payload'])[0]['pending']
                if pending is not None and pending['intents']:raise OSError('Controlled WAL failure before input')
                return original(value,previous)
            owner.store.write=write
            with self.assertRaises(OSError):owner.act(self.model.ticket,'type',self.model.inputs)
            owner.store.write=original
        self.assertEqual(calls,self.model.widgets.calls)
        with self.owner() as owner:self.assertEqual([],owner.state['pending']['intents'])

    def test_original_ui_and_view_nonces_cannot_be_replaced_by_expected_fields(self):
        self.open()
        with self.owner() as owner:
            frame=owner.original(owner.state['records'][-1])
            changed=deepcopy(frame);changed['queries']=[query for query in changed['queries'] if query['action']!='feature-chat-view-observe']
            with self.assertRaises(NativeUIError):owner.frame(changed)
            changed=deepcopy(frame);changed['queries']=[query for query in changed['queries'] if query.get('operation')!='observe']
            with self.assertRaises(NativeUIError):owner.frame(changed)


class ChatDraftBudgetTests(unittest.TestCase):
    def test_expiry_clock_regression_and_invalid_clock_are_sticky(self):
        for changed in (20.,-.1,float('nan'),True):
            now=[0.];budget=Budget(lambda:now[0]);now[0]=changed
            with self.subTest(changed=changed),self.assertRaises(NativeUIError):budget.check()
            now[0]=0.
            with self.assertRaises(NativeUIError):budget.check()


if __name__=='__main__':unittest.main()
