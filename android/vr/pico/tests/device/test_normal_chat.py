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


from test_chat_erase_binding import PicoChatControlsTests

if __name__=='__main__':unittest.main()
