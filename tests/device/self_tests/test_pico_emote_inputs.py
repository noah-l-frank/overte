"""Original Pico input/source owners; explicit synthetic Qt/OpenXR/Rig boundaries."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
import unittest
import uuid

from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.pico4.emote_inputs import PicoEmoteInputs
from adapters.pico4.emote_sources import PicoEmoteSources
from adapters.pico4.normal_emote import PicoEmoteIO, project
from adapters.pico4.normal_scripts import PicoScriptIO
from adapters.token_emote_ui import TokenEmoteUI, same_reference
from feature_journeys.scenarios import VERSION
from self_tests import test_pico_emote_sources as source_seams

RUN=source_seams.RUN


class InputsTests(unittest.TestCase):
    def setUp(self):
        self.s=source_seams.SourcesTests();self.s.setUp();self.addCleanup(self.s.doCleanups)
        self.store=PrivateFeatureState(self.s.root/'pico-emote-inputs.json')
        self.inputs=[];self.controllers=[];self.fault=None;self.ticket=0
        # Use the original PicoScriptIO tablet method and PicoEmoteIO projection.
        # Only the actual OpenXR/Qt delivery edges below are explicit seams.
        self.tablet=object.__new__(PicoScriptIO)
        self.tablet.navigation=SimpleNamespace(controller=self.controller)
        self.original=SimpleNamespace(capture=self.s.widgets,navigation=SimpleNamespace(input=self.input))

    def sleep(self,seconds):self.s.sleep(seconds);self.s.widget.clock=self.s.clock

    def input(self,identifier,action='activate',*,reference,direction=None):
        self.assertEqual('issuing',self.owner.state['current']['phase'])
        self.assertEqual(self.owner.previous,self.store.read())
        if self.fault=='changed-context':self.s.widget.generation=str(uuid.uuid4())
        same_reference(reference,project(self.s.widgets()),identifier)
        original=self.s.widget.capture();row=next(value for value in original['controls'] if value['id']==identifier)
        self.inputs.append(identifier if direction is None else direction)
        if action=='scroll':self.s.widget.scroll(identifier,direction,token=row['token'])
        else:self.s.widget.activate(identifier,token=row['token'])
        if self.fault=='lost-qt-reply':raise NativeUIError('Synthetic reply loss after original Qt input')

    def controller(self,operation):
        self.assertEqual('issuing',self.owner.state['current']['phase'])
        self.assertEqual(self.owner.previous,self.store.read());self.controllers.append(operation)
        if self.fault!='ignored-controller':
            self.s.widget.tablet=operation=='tablet.open';self.s.widget.generation=str(uuid.uuid4())
        if self.fault=='lost-controller-reply':raise NativeUIError('Synthetic reply loss after original OpenXR input')

    @contextmanager
    def session(self):
        self.s.lock.assert_held();self.assertTrue(self.s.okay);yield;self.assertTrue(self.s.okay)

    def controls(self,intent,receipt):
        return TokenEmoteUI(PicoEmoteIO(self.original),intent,receipt=receipt,
            monotonic=lambda:self.s.clock,sleep=self.sleep)

    def create(self):
        self.source=self.s.owner()
        self.owner=PicoEmoteInputs(self.source,self.store,self.controls,self.tablet,self.session)
        return self.owner

    def call(self,verb,inputs=None):
        self.ticket+=1;ticket=format(self.ticket,'032x');inputs=inputs or {}
        self.s.journal.activate(RUN,ticket,verb,inputs)
        return dict(contractVersion=VERSION,runId=RUN,fixtureUrl=self.s.phase.fixture_url,ticket=ticket,verb=verb,inputs=inputs)

    def test_normal_open_play_cancel_close_and_controller_generation_edges_are_durable(self):
        self.s.widget.tablet=False
        with self.s.lock.held():
            owner=self.create();owner.act(self.call('open'))
            self.assertEqual(['tablet.open'],self.controllers);self.assertEqual(['emote.entry'],self.inputs)
            owner.act(self.call('play',{'name':'Crying'}));self.assertEqual('Crying',self.s.widget.active)
            owner.act(self.call('cancel'));self.assertEqual('',self.s.widget.active)
            owner.act(self.call('close'));self.assertFalse(self.s.widget.tablet)
            self.assertEqual(['tablet.open','tablet.close'],self.controllers)
            self.assertEqual(3,len(owner.state['history']));self.assertEqual('acknowledged',owner.state['current']['phase'])
            header=self.store.read();calls=list(self.s.calls)
            _state,history=PicoEmoteInputs.archive(header,self.source.previous,phase=self.s.phase,
                artifact_root=self.s.root,binding=self.source.binding,guard=self.s.guard,monotonic=lambda:self.s.clock)
            self.assertEqual(3,history['count']);self.assertEqual(calls,self.s.calls)
            self.assertEqual(header,self.create().previous)

    def test_acknowledged_retry_is_input_idempotence_and_never_an_effect_verdict(self):
        with self.s.lock.held():
            owner=self.create();call=self.call('play',{'name':'Crying'})
            self.assertEqual({'performed':True},owner.act(call));commands=list(self.inputs)
            self.assertEqual({'performed':True},self.create().act(call));self.assertEqual(commands,self.inputs)
            # The synthetic Rig deliberately remains the older Waving override.
            # A consumed Crying button cannot turn that into observed playback.
            event=self.source.frames[-1]['group']['native']['animation']['history']['events'][0]
            self.assertTrue(event['request']['url'].endswith('/Waving.fbx'))
            self.assertNotIn('state',owner.act(call))

    def test_lost_qt_reply_retains_exact_intent_and_refuses_reconstruction_replay(self):
        with self.s.lock.held():
            owner=self.create();self.fault='lost-qt-reply';call=self.call('open')
            with self.assertRaises(NativeUIError):owner.act(call)
            self.assertEqual(['emote.entry'],self.inputs);self.assertTrue(self.s.widget.page)
            recovered=self.create();self.assertEqual('issuing',recovered.state['current']['phase'])
            self.assertIsNone(recovered.state['current']['intents'][-1]['after'])
            with self.assertRaises(NativeUIError):recovered.act(call)
            self.assertEqual(['emote.entry'],self.inputs)

    def test_ignored_qt_entry_and_changed_context_are_never_resent(self):
        for fault in ('ignored','changed-context'):
            with self.subTest(fault=fault):
                self.setUp()
                with self.s.lock.held():
                    owner=self.create();self.s.widget.fault='ignored' if fault=='ignored' else None
                    self.fault=None if fault=='ignored' else fault;call=self.call('open')
                    with self.assertRaises(NativeUIError):owner.act(call)
                    count=len(self.inputs)
                    with self.assertRaises(NativeUIError):self.create().act(call)
                    self.assertEqual(count,len(self.inputs));self.assertLessEqual(count,1)

    def test_lost_or_ignored_controller_response_never_reopens_after_reconstruction(self):
        for fault in ('lost-controller-reply','ignored-controller'):
            with self.subTest(fault=fault):
                self.setUp();self.s.widget.tablet=False;self.fault=fault
                with self.s.lock.held():
                    owner=self.create();call=self.call('open')
                    with self.assertRaises(NativeUIError):owner.act(call)
                    recovered=self.create();self.assertEqual('issuing',recovered.state['current']['phase'])
                    with self.assertRaises(NativeUIError):recovered.act(call)
                    self.assertEqual(['tablet.open'],self.controllers)

    def test_source_query_loss_after_consumed_controller_retains_both_owners(self):
        self.s.widget.tablet=False
        original=self.controller
        def lost(operation):original(operation);self.s.fault='script'
        self.tablet.navigation.controller=lost
        with self.s.lock.held():
            owner=self.create();call=self.call('open')
            with self.assertRaises(NativeUIError):owner.act(call)
            self.assertEqual('reading',self.source.state['phase']);self.assertEqual('issuing',owner.state['current']['phase'])
            self.s.fault=None;recovered=self.create()
            with self.assertRaises(NativeUIError):recovered.act(call)
            self.assertEqual(['tablet.open'],self.controllers)

    def test_exact_interrupted_input_archive_is_recovered_without_product_input(self):
        with self.s.lock.held():
            owner=self.create();owner.act(self.call('open'));original=owner.history_store.write
            def interrupted(index,value):original(index,value);raise NativeUIError('Synthetic original input archive interruption')
            owner.history_store.write=interrupted
            with self.assertRaises(NativeUIError):owner.archive_current()
            commands=list(self.inputs);calls=list(self.s.calls);recovered=self.create()
            self.assertIsNone(recovered.recover_archive());self.assertEqual(commands,self.inputs);self.assertEqual(calls,self.s.calls)
            self.assertEqual(1,len(recovered.state['history']));self.assertIsNone(recovered.state['current'])

    def test_fixture_ticket_candidate_and_original_reference_cannot_be_changed(self):
        with self.s.lock.held():
            owner=self.create();call=self.call('play',{'name':'Crying'});owner.act(call)
            with self.assertRaises((NativeUIError,ValueError)):owner.act(call|dict(inputs={'name':'Waving'}))
            owner.state['current']['before']['sha256']='f'*64
            with self.assertRaises(NativeUIError):owner.row(owner.state['current'])
            commands=list(self.inputs);self.s.okay=False
            with self.assertRaises(NativeUIError):owner.act(call)
            self.assertEqual(commands,self.inputs)

    def test_v1_source_archive_stays_strict_and_live_generation_reuse_is_rejected(self):
        with self.s.lock.held():
            self.s.widget.tablet=False;owner=self.create();owner.act(self.call('open'))
            legacy=deepcopy(self.source.previous);legacy['picoEmoteSourcesVersion']=1
            with self.assertRaises(NativeUIError):PicoEmoteSources.archive(legacy,phase=self.s.phase,
                artifact_root=self.s.root,binding=self.source.binding,guard=self.s.guard,monotonic=lambda:self.s.clock)
            self.s.widget.generation=str(uuid.uuid4())
            with self.assertRaises(NativeUIError):self.source.read()


if __name__=='__main__':unittest.main()
