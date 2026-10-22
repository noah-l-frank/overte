"""Pico Chat normal controls over synthetic bound Qt/OpenXR/ADB sources only."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from functools import partial
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import uuid
import test_normal_scripts as sources
from self_tests.test_token_chat_ui import Widgets,RUN
from adapters.token_chat_ui import TokenChatUI
from adapters.pico4.navigation import validate_snapshot
from feature_journeys.fixtures import context


class PicoChatTests(unittest.TestCase):
    def setUp(self):
        self.fixture=sources.PicoNormalScriptsTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.instance,self.native=self.fixture.instance,self.fixture.native
        self.widget=Widgets();self.widget.panel=True;self.widget.instance=self.native.bridge_id;self.widget.generation=self.native.generation
        self.native.opened=True;self.marker=1;self.before_input=None;self.fault=None;self.intents=[]
        original=self.widget.capture
        def capture():
            value=original()
            for row in value['controls']:
                row['token']=str(uuid.uuid5(uuid.NAMESPACE_URL,row['token']))
                if row['id'].startswith('tablet.'):row.pop('inputReady',None)
            return value
        self.widget.capture=capture
        snapshot_original=self.native.snapshot;write_original=self.native.write_debug_app_file
        def snapshot():
            value=snapshot_original();actual=self.widget.capture()
            value.update(chatControlsVersion=self.marker,controls=deepcopy(actual['controls']),
                elapsedMs=actual['scope']['elapsedMs'],lastCommandSequence=self.widget.sequence)
            if self.fault=='missing':value.pop('chatControlsVersion')
            return value
        self.snapshot=snapshot
        def write(target,package,path,raw):
            if path!='files/overte-e2e/navigation-ui-command.json':return write_original(target,package,path,raw)
            command=json.loads(raw)
            if self.before_input:self.before_input()
            original=self.widget.capture();row=next(r for r in original['controls'] if r['id']==command['controlId'])
            valid=(row['token']==command['controlToken'] and command['sequence']==self.widget.sequence+1
                   and command['bridgeId']==self.widget.instance and command['generation']==self.widget.generation)
            self.native.inputs.append(deepcopy(command))
            if valid:self.widget.input(command['controlId'],command['action'],original,command.get('text'))
            self.native.sequence=self.widget.sequence
            self.native.status=dict(schemaVersion=1,bridgeId=self.native.bridge_id,commandId=command['commandId'],
                sequence=command['sequence'],performed=valid,error='' if valid else 'control-unavailable',processId=123,
                updatedEpochMs=self.native.epoch_milliseconds(target))
        for boundary in (patch.object(self.native,'snapshot',side_effect=snapshot),
                         patch.object(self.native,'write_debug_app_file',side_effect=write),
                         patch('adapters.token_chat_ui.TokenChatUI',partial(TokenChatUI,
                             monotonic=lambda:self.widget.clock,sleep=self.widget.sleep))):
            boundary.start();self.addCleanup(boundary.stop)
        self.flow=self.instance._chat_controls(self.native.target,self.intents.append,RUN)

    def test_closed_tablet_uses_existing_original_openxr_controller_owner_before_chat_pointer_input(self):
        self.widget.panel=False;self.widget.tablet=False;self.native.opened=False
        def stage(identity,operation,values):
            self.assertEqual('123:synthetic-start',identity);self.assertEqual('tablet.open',operation)
            self.assertEqual({'holdMilliseconds':1000},values)
            original=json.loads(self.flow.io.original.navigation.path.read_text())
            self.assertTrue(original['tabletOwned']);self.assertEqual(self.widget.instance,original['bridgeId'])
            self.assertEqual('controller-open',self.intents[-1]['action'])
            self.native.controllers.append(operation);self.native.opened=True;self.widget.tablet=True
            return {'performed':True}
        boundary=patch.object(self.native,'stage',side_effect=stage);boundary.start();self.addCleanup(boundary.stop)
        self.flow.open()
        self.assertTrue(self.widget.panel);self.assertEqual(['tablet.open'],self.native.controllers)
        self.assertEqual('controller-open',self.intents[0]['action'])
        self.assertEqual([('chat.entry','activate',None)],self.widget.calls)
        self.assertEqual(1,len(self.native.inputs))

    def test_original_wrapper_uses_unicode_channel_send_and_return_with_consumed_counters(self):
        self.flow.select_channel('domain');self.flow.type(context(RUN)['unicode']);self.flow.send()
        self.flow.type(context(RUN)['retry']);self.flow.send(enter=True);self.flow.close()
        self.assertEqual([('domain',context(RUN)['unicode']),('domain',context(RUN)['retry'])],self.widget.sent)
        self.assertFalse(self.widget.panel);self.assertEqual([],self.widget.domain)
        self.assertEqual(list(range(1,len(self.native.inputs)+1)),[r['sequence'] for r in self.native.inputs])
        self.assertNotIn(context(RUN)['unicode'],str(self.intents))
        self.assertFalse(any(c.startswith('feature.chat.') for c in self.instance.capabilities(self.native.target)))

    def test_consumed_but_ignored_field_effect_does_not_pass(self):
        self.widget.ignore_effect=True
        with self.assertRaises(RuntimeError):self.flow.type(context(RUN)['unicode'])
        self.assertEqual('',self.widget.draft);self.assertFalse(self.widget.focus);self.assertEqual(1,len(self.native.inputs))

    def test_changed_draft_and_late_original_context_are_not_recaptured(self):
        self.flow.type(context(RUN)['unicode']);reference=self.flow.capture();before=len(self.native.inputs)
        self.widget.draft=context(RUN)['retry']
        with self.assertRaises(RuntimeError):self.flow.io.activate('chat.send',reference=reference)
        self.assertEqual(before,len(self.native.inputs));self.assertEqual([],self.widget.sent)
        self.before_input=lambda:setattr(self.widget,'generation',str(uuid.uuid4()))
        with self.assertRaises(RuntimeError):self.flow.send()
        self.assertEqual([],self.widget.sent)

    def test_missing_or_boolean_version_and_changed_candidate_prevent_input(self):
        self.fault='missing'
        with self.assertRaises(RuntimeError):self.flow.select_channel('domain')
        self.fault=None;self.marker=True
        with self.assertRaises(RuntimeError):self.flow.select_channel('domain')
        self.marker=1;self.native.digest='f'*64
        with self.assertRaises((ValueError,RuntimeError)):self.flow.select_channel('domain')
        self.assertEqual([],self.native.inputs)

    def test_unbound_input_private_text_and_fictional_keyboard_fact_are_rejected(self):
        with self.assertRaises(RuntimeError):self.flow.io.original.navigation.input('chat.send')
        original=self.snapshot()
        for change in ({'keyboard':True},{'keyboardRequested':1},{'domainRowCount':True},{'profile':'foreign'},{'expected':{}}):
            altered=deepcopy(original);altered['controls']=[r|change if r['id']=='chat.page' else r for r in altered['controls']]
            with self.assertRaises(RuntimeError):validate_snapshot(altered,123,self.native.epoch_milliseconds(self.native.target))
        self.widget.draft='private user content'
        with self.assertRaises(RuntimeError):self.flow.capture()
        self.assertEqual([],self.native.inputs)

    def test_failed_intent_and_incomplete_close_cannot_be_success(self):
        def failed(_):raise RuntimeError('private ownership storage unavailable')
        self.flow.intent=failed
        with self.assertRaises(RuntimeError):self.flow.type(context(RUN)['unicode'])
        self.assertEqual([],self.native.inputs)
        self.flow.intent=self.intents.append;self.widget.ignore_effect=True
        with self.assertRaises(RuntimeError):self.flow.close()
        self.assertTrue(self.widget.panel);self.assertTrue(self.intents)

    def phase_boundary(self):
        from self_tests import test_chat_phase_fence as phases
        original=phases.PhaseFenceTests();original.setUp();self.addCleanup(original.doCleanups)
        self.flow.io.bind_input_fence(original.fence)
        def intent(value):original.fence.mark();self.intents.append(deepcopy(value))
        self.flow.intent=intent
        return original

    def test_actual_qml_transport_refuses_changed_phase_after_original_intent_write(self):
        boundary=self.phase_boundary();intent=self.flow.intent
        def changed(value):
            intent(value);boundary.h.journal.activate(RUN,uuid.uuid4().hex,'open',{})
        self.flow.intent=changed
        with boundary.flow.session():
            with self.assertRaises((ValueError,RuntimeError)):self.flow.type(context(RUN)['unicode'])
        self.assertEqual([],self.native.inputs);self.assertEqual([],self.widget.calls)
        self.assertEqual('',self.widget.draft);self.assertTrue(boundary.fence.failed)

    def test_actual_controller_transport_refuses_phase_changed_by_final_navigation_cas(self):
        boundary=self.phase_boundary();self.widget.panel=False;self.widget.tablet=False;self.native.opened=False
        navigation=self.flow.io.original.navigation;mark=navigation._mark
        def changed(snapshot,owned):
            mark(snapshot,owned);boundary.h.journal.activate(RUN,uuid.uuid4().hex,'open',{})
        navigation._mark=changed
        with boundary.flow.session():
            with self.assertRaises((ValueError,RuntimeError)):self.flow.open()
        self.assertEqual([],self.native.controllers);self.assertEqual([],self.native.inputs)
        self.assertTrue(json.loads(navigation.path.read_text())['tabletOwned'])
        self.assertFalse(self.widget.tablet);self.assertTrue(boundary.fence.failed)

    def test_original_locked_controller_callback_persists_envelope_without_phase_or_sdk_reentry(self):
        from contextlib import contextmanager
        from self_tests import test_pico_openxr_adapter_session as sessions
        from adapters.normal_feature_state import PrivateFeatureState
        for late in (False,True):
            with self.subTest(late=late):
                self.setUp();boundary=self.phase_boundary();self.widget.panel=False;self.widget.tablet=False;self.native.opened=False
                directory=self.fixture.fixture.state_root/'chat-native-session';directory.mkdir(mode=0o700)
                transport=sessions.FakeTransport();session=sessions.PicoOpenXrAdapterSession(transport,'synthetic-chat-target',directory)
                session.begin('123:synthetic-start');original_lock=session._lock;inside=False
                @contextmanager
                def held():
                    nonlocal inside
                    with original_lock():
                        inside=True
                        try:yield
                        finally:inside=False
                session._lock=held;request=boundary.fence.source.client.request
                def outside(*args,**kwargs):
                    self.assertFalse(inside);return request(*args,**kwargs)
                boundary.fence.source.client.request=outside
                ledger=PrivateFeatureState(directory/'actual-envelope.json')
                def intent(envelope):
                    self.assertTrue(inside);ledger.write({'envelope':envelope},None)
                    if late:boundary.h.h.native.host+=2
                boundary.fence.stream_intent=intent;stage=transport.stage
                def publish(envelope,profile,*,before_publish):
                    before_publish(envelope)
                    self.assertEqual(envelope,ledger.read()['envelope']);self.assertTrue(inside)
                    self.native.opened=True;self.widget.tablet=True;return stage(envelope,profile)
                transport.stage=publish
                with patch.object(self.instance,'pico_input_session',return_value=session),boundary.flow.session():
                    if late:
                        with self.assertRaises((ValueError,RuntimeError)):self.flow.open()
                    else:self.flow.open()
                self.assertEqual(0 if late else 1,len(transport.envelopes));self.assertIsNotNone(ledger.read())
                if late:self.assertFalse(self.widget.tablet);self.assertTrue(boundary.fence.failed)
                else:self.assertTrue(self.widget.panel);self.assertEqual('tablet.open',transport.envelopes[0]['commands'][0]['operation'])


    def test_actual_original_sdk_and_command_writer_age_cannot_publish_chat_controller_grant(self):
        from self_tests import test_openxr_android_transport as sdk
        from tests.device.openxr_input.adapter_session import PicoOpenXrAdapterSession
        from adapters.normal_feature_state import PrivateFeatureState
        for delayed in ('SDK','command'):
            with self.subTest(delayed=delayed):
                self.setUp();boundary=self.phase_boundary();self.widget.panel=False;self.widget.tablet=False;self.native.opened=False
                directory=self.fixture.fixture.state_root/'chat-final-native-session';directory.mkdir(mode=0o700)
                fake_sdk=directory/'synthetic-adb';fake_sdk.write_text('explicit non-executable SDK seam')
                runner=sdk.FakeRunner('synthetic-final-chat-target')
                transport=sdk.AndroidOpenXrTransport(fake_sdk,'synthetic-final-chat-target',runner=runner)
                session=PicoOpenXrAdapterSession(transport,'synthetic-final-chat-target',directory)
                session.begin('123:synthetic-start');ledger=PrivateFeatureState(directory/'original-intent.json');intents=[]
                def intent(envelope):intents.append(envelope);ledger.write({'envelope':envelope},None)
                boundary.fence.stream_intent=intent
                guard=transport.require_exclusive_target;write=transport._atomic_write
                def guarded():
                    guard()
                    if delayed=='SDK':boundary.h.h.native.host+=2
                def written(name,payload):
                    write(name,payload)
                    if delayed=='command' and name=='commands.json':boundary.h.h.native.host+=2
                with patch.object(self.instance,'pico_input_session',return_value=session),\
                        patch.object(transport,'require_exclusive_target',side_effect=guarded),\
                        patch.object(transport,'_atomic_write',side_effect=written),\
                        patch.object(session,'_wait_for_ack',side_effect=AssertionError('unexpected controller publication')),boundary.flow.session():
                    with self.assertRaises((ValueError,RuntimeError)):self.flow.open()
                payloads=[payload for _,payload in runner.calls if payload]
                self.assertEqual(0 if delayed=='SDK' else 1,len(payloads))
                self.assertFalse(any(payload and 'grant.json' in command[-1] for command,payload in runner.calls))
                self.assertEqual(1,len(intents));self.assertEqual(intents[0],ledger.read()['envelope'])
                self.assertEqual(1,session._load()['nextSequence']);self.assertTrue(boundary.fence.failed)
                self.assertFalse(self.widget.tablet);self.assertEqual([],self.native.inputs)


from test_chat_erase_binding import PicoChatControlsTests

if __name__=='__main__':unittest.main()
