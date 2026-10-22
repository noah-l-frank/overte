"""Create component over real HTTP/AFC logic with synthetic native Qt receipts."""
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
from self_tests.test_normal_create_adapter import NativeCreate
from self_tests.test_token_create_ui import Controls
from adapters.token_create_ui import TokenCreateUI
from adapters.ios import binding
from ios.adapters import adapter as component,normal_input
from ios.adapters.create_inputs import IOSCreateUI


class IOSCreateControlsTests(unittest.TestCase):
    def setUp(self):
        self.fixture=sources.IOSNormalScriptsTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.adapter,self.native=self.fixture.adapter,self.fixture.native
        self.world=NativeCreate(self.fixture.path.parent);self.world.tablet=True;self.world.page='create'
        self.widget=Controls(self.world);self.widget.pid=42;self.widget.instance=self.native.instance
        self.widget.generation='22222222-2222-4222-8222-222222222222'
        self.native.qt.opened=True;self.marker=1;self.fault=None;self.before_input=None
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
            value.update(createControlsVersion=self.marker,createGeneration=actual['scope']['generation'],
                elapsedMs=actual['scope']['elapsedMs'],lastSequence=self.widget.sequence,
                controls=[r|{'frame':dict(x=10,y=20,width=200,height=48)} for r in actual['controls']])
            if self.fault=='missing':value.pop('createControlsVersion');value.pop('createGeneration')
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
            if valid:self.widget.input(rows[0]['id'],native['operation'],original,native.get('text',native.get('index',native.get('direction'))))
            else:self.widget.sequence+=1
            self.native.sequence=self.widget.sequence
            self.native.receipt=dict(schemaVersion=1,commandId=command['commandId'],status=dict(schemaVersion=1,
                commandId=native['commandId'],instance=self.native.instance,sequence=self.widget.sequence,
                performed=bool(valid),processId=42,sampleEpochMs=self.native.epoch()))
            return self.native
        for boundary in (patch.object(self.native,'observed',side_effect=observed),
                         patch.object(self.native,'post',side_effect=post),
                         patch.object(normal_input,'urlopen',side_effect=post),
                         patch('ios.adapters.create_inputs.IOSCreateUI',partial(IOSCreateUI,
                             monotonic=lambda:self.world.clock,sleep=self.world.sleep))):
            boundary.start();self.addCleanup(boundary.stop)
        self.flow=self.adapter._create_controls('test-only-selector',self.widget.intents.append)

    def test_actual_component_sequences_pointer_field_choice_and_scroll(self):
        self.flow.choose('create.host',1);self.widget.hidden='create.resource'
        self.flow.replace('create.resource','owned-resource')
        self.assertEqual(1,self.widget.indexes['create.host']);self.assertEqual('owned-resource',self.widget.texts['create.resource'])
        edits=[c['input'] for c in self.native.commands if c.get('operation')=='edit']
        self.assertIn('activate',[c['operation'] for c in edits]);self.assertIn('scroll',[c['operation'] for c in edits])
        self.assertEqual(list(range(1,len(edits)+1)),[c['sequence'] for c in edits])
        self.assertFalse(any(c.startswith('feature.create.') for c in self.adapter.advertised_capabilities(self.native.target)))

    def test_ignored_text_and_choice_fail_on_independent_widget_readback(self):
        self.widget.ignore={'create.host'}
        with self.assertRaises(RuntimeError):self.flow.choose('create.host',1)
        self.widget.ignore={'create.resource'}
        with self.assertRaises(RuntimeError):self.flow.replace('create.resource','owned-resource')
        self.assertEqual(0,self.widget.indexes['create.host']);self.assertNotIn('create.resource',self.widget.texts)

    def test_foreign_selected_reference_and_late_replacement_cannot_mutate(self):
        reference=self.flow.capture();self.widget.selected=['22222222-2222-2222-2222-222222222222']
        with self.assertRaises(RuntimeError):self.flow.io.activate('create.tab.0',reference=reference)
        self.assertFalse(any(c.get('operation')=='edit' for c in self.native.commands))
        self.widget.selected=[];self.before_input=lambda:self.widget.selected.append('22222222-2222-2222-2222-222222222222')
        with self.assertRaises(RuntimeError):self.flow.tab(4)
        self.assertEqual(0,self.widget.tab)

    def test_missing_marker_false_types_and_native_frame_errors_refuse_input(self):
        self.fault='missing'
        with self.assertRaises(RuntimeError):self.flow.tab(0)
        self.fault=None;self.marker=True
        with self.assertRaises(RuntimeError):self.flow.tab(0)
        self.marker=1;value=self.observed()
        for changes in ({'frame':None},{'expected':{}},{'tab':True}):
            altered=deepcopy(value);altered['controls']=[r|changes if r['id']=='create.page' else r for r in altered['controls']]
            with self.assertRaises(RuntimeError):normal_input.observation(altered,42,self.native.epoch())
        self.assertFalse(any(c.get('operation')=='edit' for c in self.native.commands))

    def test_failed_intent_ignored_scroll_and_lost_session_refuse_success(self):
        def failed(_):raise RuntimeError('private journal unavailable')
        self.flow.intent=failed
        with self.assertRaises(RuntimeError):self.flow.tab(0)
        self.assertFalse(any(c.get('operation')=='edit' for c in self.native.commands))
        self.flow.intent=self.widget.intents.append;self.widget.hidden='create.resource';self.widget.ignore_scroll=True
        with self.assertRaises(RuntimeError):self.flow.replace('create.resource','owned-resource')
        self.native.pid=43;before=len(self.native.commands)
        with self.assertRaises(RuntimeError):self.flow.tab(0)
        self.assertEqual(before,len(self.native.commands))

    def test_canonical_installed_code_gate_rejects_create_before_io(self):
        with patch.object(component.AppiumAdapter,'load_targets',return_value={}):
            adapter=binding.create_adapter(SimpleNamespace(platform='ios',action='cleanup'),component.AppiumAdapter)
        with self.assertRaisesRegex(ValueError,'OVT_IOS_INSTALLED_CODE_BINDING_UNAVAILABLE'):
            adapter._create_controls('private-selector',lambda _:None)


if __name__=='__main__':unittest.main()
