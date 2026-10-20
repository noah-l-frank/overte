"""Chat component over original HTTP/AFC input logic and synthetic Qt state."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from functools import partial
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import uuid
import test_ios_normal_scripts as sources
from self_tests.test_token_chat_ui import Widgets,RUN
from adapters.token_chat_ui import TokenChatUI
from adapters.ios import binding
from ios.adapters import adapter as component,normal_input
from feature_journeys.fixtures import context


class IOSChatControlsTests(unittest.TestCase):
    def setUp(self):
        self.fixture=sources.IOSNormalScriptsTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.adapter,self.native=self.fixture.adapter,self.fixture.native
        self.widget=Widgets();self.widget.panel=True;self.widget.pid=42;self.widget.instance=self.native.instance
        self.widget.generation='22222222-2222-4222-8222-222222222222'
        self.native.qt.opened=True;self.marker=1;self.fault=None;self.before_input=None;self.intents=[]
        capture_original=self.widget.capture
        def capture():
            value=capture_original()
            for row in value['controls']:
                row['token']=str(uuid.uuid5(uuid.NAMESPACE_URL,row['token']))
                if row['id'].startswith('tablet.'):row.pop('inputReady',None)
            return value
        self.widget.capture=capture
        observed_original=self.native.observed;post_original=self.native.post
        def observed():
            value=observed_original();actual=self.widget.capture()
            value.update(chatControlsVersion=self.marker,chatGeneration=actual['scope']['generation'],
                elapsedMs=actual['scope']['elapsedMs'],lastSequence=self.widget.sequence,
                controls=[r|{'frame':dict(x=10,y=20,width=200,height=48)} for r in actual['controls']])
            if self.fault=='missing':value.pop('chatControlsVersion');value.pop('chatGeneration')
            return value
        self.observed=observed
        def post(request,timeout):
            value=json.loads(request.data)
            if value['action']!='normal-ui-input' or value['operation']!='edit':return post_original(request,timeout)
            command=self.native.fixture.set_client_command(value);self.native.commands.append(command)
            self.native.echo=json.dumps(command).encode();native=command['input']
            if self.before_input:self.before_input()
            original=self.widget.capture();scope=original['scope']
            rows=[r for r in original['controls'] if r['token']==native['fieldToken']]
            valid=(native['instance']==scope['instance'] and native['sequence']==scope['sequence']+1 and len(rows)==1)
            if valid:self.widget.input(rows[0]['id'],native['operation'],original,native.get('text'))
            else:self.widget.sequence+=1
            self.native.sequence=self.widget.sequence
            self.native.receipt=dict(schemaVersion=1,commandId=command['commandId'],status=dict(schemaVersion=1,
                commandId=native['commandId'],instance=self.native.instance,sequence=self.widget.sequence,
                performed=bool(valid),processId=42,sampleEpochMs=self.native.epoch()))
            return self.native
        for boundary in (patch.object(self.native,'observed',side_effect=observed),
                         patch.object(self.native,'post',side_effect=post),
                         patch.object(normal_input,'urlopen',side_effect=post),
                         patch('adapters.token_chat_ui.TokenChatUI',partial(TokenChatUI,
                             monotonic=lambda:self.widget.clock,sleep=self.widget.sleep))):
            boundary.start();self.addCleanup(boundary.stop)
        self.flow=self.adapter._chat_controls('test-only-selector',self.intents.append,RUN)

    def test_component_uses_normal_unicode_send_return_and_consumed_input_counter(self):
        self.flow.select_channel('domain');self.flow.type(context(RUN)['unicode']);self.flow.send()
        self.flow.type(context(RUN)['retry']);self.flow.send(enter=True);self.flow.close()
        self.assertEqual([('domain',context(RUN)['unicode']),('domain',context(RUN)['retry'])],self.widget.sent)
        self.assertEqual([],self.widget.domain);self.assertFalse(self.widget.panel)
        edits=[c['input'] for c in self.native.commands if c.get('operation')=='edit']
        self.assertEqual(list(range(1,len(edits)+1)),[c['sequence'] for c in edits])
        self.assertIn('submit',[c['operation'] for c in edits]);self.assertNotIn(context(RUN)['unicode'],str(self.intents))
        self.assertFalse(any(c.startswith('feature.chat.') for c in self.adapter.advertised_capabilities(self.native.target)))

    def test_consumed_but_ignored_effect_is_not_success(self):
        self.widget.ignore_effect=True
        with self.assertRaises(RuntimeError):self.flow.type(context(RUN)['unicode'])
        self.assertEqual('',self.widget.draft);self.assertFalse(self.widget.focus)

    def test_changed_draft_or_late_geometry_replacement_cannot_retarget_send(self):
        self.flow.type(context(RUN)['unicode']);reference=self.flow.capture()
        before=len(self.native.commands);self.widget.draft=context(RUN)['retry']
        with self.assertRaises(RuntimeError):self.flow.io.activate('chat.send',reference=reference)
        self.assertFalse(any(c.get('operation')=='edit' for c in self.native.commands[before:]))
        self.before_input=lambda:setattr(self.widget,'geometry',(30,40,150,50))
        with self.assertRaises(RuntimeError):self.flow.send()
        self.assertEqual([],self.widget.sent)

    def test_missing_version_bad_types_frames_and_fictional_keyboard_facts_refuse_input(self):
        self.fault='missing'
        with self.assertRaises(RuntimeError):self.flow.select_channel('domain')
        self.fault=None;self.marker=True
        with self.assertRaises(RuntimeError):self.flow.select_channel('domain')
        self.marker=1;value=self.observed()
        for changes in ({'frame':None},{'expected':{}},{'keyboard':True},{'keyboardRequested':1},{'domainRowCount':True}):
            altered=deepcopy(value);altered['controls']=[r|changes if r['id']=='chat.page' else r for r in altered['controls']]
            with self.assertRaises(RuntimeError):normal_input.observation(altered,42,self.native.epoch())
        self.assertFalse(any(c.get('operation')=='edit' for c in self.native.commands))

    def test_failed_intent_incomplete_close_and_lost_process_keep_original_ownership(self):
        def failed(_):raise RuntimeError('private storage unavailable')
        self.flow.intent=failed
        with self.assertRaises(RuntimeError):self.flow.type(context(RUN)['unicode'])
        self.assertFalse(any(c.get('operation')=='edit' for c in self.native.commands))
        self.flow.intent=self.intents.append;self.widget.ignore_effect=True
        with self.assertRaises(RuntimeError):self.flow.close()
        self.assertTrue(self.widget.panel);self.assertTrue(self.intents)
        self.native.pid=43;before=len(self.native.commands)
        with self.assertRaises(RuntimeError):self.flow.select_channel('domain')
        self.assertEqual(before,len(self.native.commands))

    def test_canonical_installed_code_gate_rejects_chat_before_any_io(self):
        with patch.object(component.AppiumAdapter,'load_targets',return_value={}):
            adapter=binding.create_adapter(SimpleNamespace(platform='ios',action='cleanup'),component.AppiumAdapter)
        with self.assertRaisesRegex(ValueError,'OVT_IOS_INSTALLED_CODE_BINDING_UNAVAILABLE'):
            adapter._chat_controls('private-selector',lambda _:None,RUN)


if __name__=='__main__':unittest.main()
