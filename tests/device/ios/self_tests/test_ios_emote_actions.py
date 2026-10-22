"""One-send ordinary inputs with synthetic native/SDK boundaries; no pose verdict."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUI,NativeUIError
from adapters.script_feature.lock import ScriptSourceLock
from ios.adapters.emote_actions import IOSEmoteActions
from ios.adapters.emote_sources import IOSEmoteSources
from ios.adapters.emote_controls import IOSEmoteIO
from ios.self_tests.test_ios_emote_controls import NativeBoundary
from ios.self_tests.test_ios_emote_sources import BINDING,RUN

URL='http://127.0.0.1:12345/feature-fixture/v1/runs/'+RUN+'/'


class Sources(IOSEmoteSources):
    def __init__(self,lock):
        self.lock=lock;self.run=RUN;self.binding=deepcopy(BINDING);self.role='primary';self.historical=False
        self.phase=SimpleNamespace(fixture_url=URL);self.frames=[];self.native=NativeBoundary();self.native.tablet=False
        self.readers=dict(ui=IOSEmoteIO(self.native));self.monotonic=lambda:self.native.clock;self.call=None;self.fault=None
    def bound(self):self.lock.assert_held()
    def read(self):
        self.bound()
        if self.fault=='read':raise NativeUIError('Synthetic lost original source return')
        call=self.call;value=dict(ui=self.readers['ui'].capture(),group=dict(native=dict(animation=dict(overrideActive=False))),
            phaseAfter=dict(active=True,activations=[dict(ticket=call['ticket'],stimulus=dict(verb=call['verb'],inputs=call['inputs']))]))
        self.frames.append(deepcopy(value));return value


class SDK(NativeUI):
    def __init__(self,source):self.source=source;self.sleep=source.native.sleep;self.calls=[];self.lost=False
    def click(self,locator):
        self.calls.append(locator.value);self.source.native.tablet=locator.value=='OverteTabletOpen'
        if self.lost:raise NativeUIError('Synthetic SDK return lost after input')


class IOSEmoteActionsTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.root.chmod(0o700)
        self.lock=ScriptSourceLock(self.root/'script-feature-sources.lock');self.held=self.lock.held();self.held.__enter__()
        self.source=Sources(self.lock);self.sdk=SDK(self.source);self.store=PrivateFeatureState(self.root/'ios-emote-inputs.json')
    def tearDown(self):self.held.__exit__(None,None,None);self.temp.cleanup()
    def actions(self):return IOSEmoteActions(self.store,self.source,self.sdk)
    def call(self,verb,ticket='1',**inputs):
        value=dict(contractVersion=16,runId=RUN,ticket=ticket*32,fixtureUrl=URL,verb=verb,inputs=inputs);self.source.call=value;return value
    def test_open_play_cancel_wait_close_use_ordinary_controls_without_pose_result(self):
        for index,(verb,inputs) in enumerate([('open',{}),('play',dict(name='Waving')),('cancel',{}),('wait-complete',{}),('close',{})]):
            result=self.actions().act(self.call(verb,str(index+1),**inputs));self.assertEqual({'performed':True},result)
        self.assertEqual(['OverteTabletOpen','OverteTabletClose'],self.sdk.calls)
        self.assertEqual(2,self.source.native.actions.count('emote.play.Waving'))
        self.assertFalse(self.source.native.tablet);self.assertFalse(self.source.native.page)
        self.assertFalse(self.source.frames[-1]['group']['native']['animation']['overrideActive'])
    def test_repeat_completed_call_returns_original_ack_without_any_input(self):
        call=self.call('open');self.actions().act(call);before=(len(self.sdk.calls),len(self.source.native.requests),len(self.source.frames))
        self.assertEqual({'performed':True},self.actions().act(call));self.assertEqual(before,(len(self.sdk.calls),len(self.source.native.requests),len(self.source.frames)))
    def test_uncertain_SDK_delivery_stays_owned_across_reconstruction(self):
        call=self.call('open');self.sdk.lost=True
        with self.assertRaises(NativeUIError):self.actions().act(call)
        self.sdk.lost=False
        with self.assertRaises(NativeUIError):self.actions().act(call)
        self.assertEqual(1,len(self.sdk.calls));self.assertEqual('issuing',self.actions().state['current']['phase'])
    def test_uncertain_Qt_delivery_stays_owned_without_resending_or_new_ticket(self):
        self.actions().act(self.call('open'));call=self.call('play','2',name='Waving');self.source.native.fault='lost'
        with self.assertRaises(NativeUIError):self.actions().act(call)
        count=len(self.source.native.requests);self.source.native.fault=None
        with self.assertRaises(NativeUIError):self.actions().act(call)
        with self.assertRaises(NativeUIError):self.actions().act(self.call('play','3',name='Waving'))
        self.assertEqual(count,len(self.source.native.requests))
    def test_wait_complete_sends_no_restore_or_other_product_input(self):
        self.actions().act(self.call('open'));before=(len(self.sdk.calls),len(self.source.native.requests))
        self.actions().act(self.call('wait-complete','2'))
        self.assertEqual(before,(len(self.sdk.calls),len(self.source.native.requests)))
    def test_preexisting_tablet_or_override_cannot_be_adopted(self):
        self.source.native.tablet=True
        with self.assertRaises(NativeUIError):self.actions().act(self.call('open'))
        self.assertEqual([],self.sdk.calls);self.assertEqual([],self.source.native.requests)
    def test_lost_source_after_intent_cannot_be_skipped_with_another_ticket(self):
        self.source.fault='read';call=self.call('open')
        with self.assertRaises(NativeUIError):self.actions().act(call)
        self.source.fault=None
        with self.assertRaises(NativeUIError):self.actions().act(self.call('open','2'))
        self.assertEqual([],self.sdk.calls);self.assertEqual([],self.source.native.requests)

if __name__=='__main__':unittest.main()
