"""Pico Create wrapper tests on synthetic Qt/OpenXR/ADB boundaries only."""
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
sys.path.insert(0,str(Path(__file__).resolve().parents[5]/'tests/device/self_tests'))
from test_normal_create_adapter import NativeCreate
from test_token_create_ui import Controls
from adapters.token_create_ui import TokenCreateUI
from adapters.pico4.navigation import validate_snapshot


class PicoCreateTests(unittest.TestCase):
    def setUp(self):
        self.fixture=sources.PicoNormalScriptsTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.instance,self.native=self.fixture.instance,self.fixture.native
        self.world=NativeCreate(self.fixture.fixture.state_root);self.world.tablet=True;self.world.page='create'
        self.widget=Controls(self.world);self.widget.pid=123;self.widget.instance=self.native.bridge_id;self.widget.generation=self.native.generation
        self.native.opened=True;self.marker=1;self.before_input=None;self.fault=None
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
            value.update(createControlsVersion=self.marker,controls=deepcopy(actual['controls']),
                elapsedMs=actual['scope']['elapsedMs'],lastCommandSequence=self.widget.sequence)
            if self.fault=='missing':value.pop('createControlsVersion')
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
            if valid:self.widget.input(command['controlId'],command['action'],original,command.get('text',command.get('index',command.get('direction'))))
            self.native.sequence=self.widget.sequence
            self.native.status=dict(schemaVersion=1,bridgeId=self.native.bridge_id,commandId=command['commandId'],
                sequence=command['sequence'],performed=valid,error='' if valid else 'control-unavailable',processId=123,
                updatedEpochMs=self.native.epoch_milliseconds(target))
        for boundary in (patch.object(self.native,'snapshot',side_effect=snapshot),
                         patch.object(self.native,'write_debug_app_file',side_effect=write),
                         patch('adapters.token_create_ui.TokenCreateUI',partial(TokenCreateUI,
                             monotonic=lambda:self.world.clock,sleep=self.world.sleep))):
            boundary.start();self.addCleanup(boundary.stop)
        self.flow=self.instance._create_controls(self.native.target,self.widget.intents.append)

    def test_actual_wrapper_uses_normal_choice_field_and_scroll_with_original_refs(self):
        self.flow.choose('create.host',1);self.widget.hidden='create.resource'
        self.flow.replace('create.resource','owned-resource')
        self.assertEqual(1,self.widget.indexes['create.host']);self.assertEqual('owned-resource',self.widget.texts['create.resource'])
        self.assertTrue(any(r['action']=='scroll' for r in self.native.inputs))
        self.assertTrue(self.widget.intents)
        self.assertFalse(any(cap.startswith('feature.create.') for cap in self.instance.capabilities(self.native.target)))

    def test_ignored_choice_and_text_do_not_prove_delivery_effect(self):
        self.widget.ignore={'create.host'}
        with self.assertRaises(RuntimeError):self.flow.choose('create.host',1)
        self.widget.ignore={'create.resource'}
        with self.assertRaises(RuntimeError):self.flow.replace('create.resource','owned-resource')
        self.assertEqual(0,self.widget.indexes['create.host']);self.assertNotIn('create.resource',self.widget.texts)

    def test_foreign_reference_and_late_native_selection_change_refuse_input(self):
        reference=self.flow.capture();self.widget.selected=['22222222-2222-2222-2222-222222222222']
        with self.assertRaises(RuntimeError):self.flow.io.activate('create.tab.0',reference=reference)
        self.assertEqual([],self.native.inputs)
        self.widget.selected=[];self.before_input=lambda:self.widget.selected.append('22222222-2222-2222-2222-222222222222')
        with self.assertRaises(RuntimeError):self.flow.tab(0)
        self.assertEqual(0,self.widget.sequence)

    def test_missing_version_false_type_and_candidate_changes_refuse_mutation(self):
        self.fault='missing'
        with self.assertRaises(RuntimeError):self.flow.tab(0)
        self.fault=None;self.marker=True
        with self.assertRaises(RuntimeError):self.flow.tab(0)
        self.marker=1;self.native.digest='f'*64
        with self.assertRaises((ValueError,RuntimeError)):self.flow.tab(0)
        self.assertEqual([],self.native.inputs)

    def test_unbound_input_missing_results_and_extra_metadata_are_rejected(self):
        navigation=self.flow.io.original.navigation
        with self.assertRaises(RuntimeError):navigation.input('create.tab.0')
        current=self.snapshot();row=next(r for r in current['controls'] if r['id']=='create.page')
        for changes in ({'statusError':1},{'selectedIds':None},{'expected':{}},{'profile':'foreign'}):
            altered=deepcopy(current);altered['controls']=[r|changes if r['id']=='create.page' else r for r in altered['controls']]
            with self.assertRaises(RuntimeError):validate_snapshot(altered,123,self.native.epoch_milliseconds(self.native.target))
        self.assertEqual([],self.native.inputs)

    def test_failed_intent_and_ignored_scroll_keep_original_state(self):
        def failed(_):raise RuntimeError('private journal unavailable')
        self.flow.intent=failed
        with self.assertRaises(RuntimeError):self.flow.tab(0)
        self.assertEqual([],self.native.inputs)
        self.flow.intent=self.widget.intents.append;self.widget.hidden='create.resource';self.widget.ignore_scroll=True
        with self.assertRaises(RuntimeError):self.flow.replace('create.resource','owned-resource')
        self.assertNotIn('create.resource',self.widget.texts)


if __name__=='__main__':unittest.main()
