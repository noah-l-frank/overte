"""Actual Pico file control transport with substituted Qt/lifetime effects."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import uuid

import test_normal_scripts as sources
from adapters.normal_ui import NativeUIError
from adapters.pico4.create_file_ui import CreateFileUI, inventory, metadata, same_reference, project
from adapters.pico4.navigation import validate_snapshot

RUN='a'*32;TICKET='b'*32
DIRECTORY='file:///actual/private/feature-create-'+RUN+'-'+TICKET
PATH=DIRECTORY.removeprefix('file://')
COMPONENT='file:///actual/application/dialogs/NativeFileBrowser.qml'


class FileEffects:
    def __init__(self,native):
        self.native=native;self.role='import';self.root=None;self.focus=None;self.text=''
        self.clock=0.;self.source_sequence=0;self.command_sequence=0;self.retired=[]
        self.input=[];self.intents=[];self.selected=[];self.cancels=0
        self.ignore=set();self.retain=False;self.closing=False;self.frozen=False;self.covered=False
        self.before_input=None;self.no_counter=False;self.native_elapsed=None
    def open(self):self.root='c'*32
    def sleep(self,seconds):self.clock+=seconds
    def capture(self):
        if not self.frozen:self.source_sequence+=1
        rows=[];roots=[dict(id='f'*32,profile='create-editor-v1',visible=True,inCurrentTree=True,
            componentSource='file:///actual/application/system/create/qml/NativeCreate.qml')]
        if self.root:
            roots.append(dict(id=self.root,profile='create-'+self.role+'-json-v1',visible=True,inCurrentTree=True,
                componentSource=COMPONENT,closing=self.closing,requestId=''))
            for name in ('page','folder','name','accept','cancel'):
                identifier='create-file.'+name
                row=dict(id=identifier,rootId=self.root,role=self.role,enabled=True,focused=self.focus==identifier,
                    inputReady=name!='page' and not self.closing and not self.covered)
                if name=='page':row.update(caption='Select .json to Import' if self.role=='import' else 'Select Where to Save',
                    filter='*.json',directory=DIRECTORY,closing=self.closing,requestId='',errorText='',componentSource=COMPONENT)
                elif name in ('name','folder'):row['text']=self.text if name=='name' else PATH
                row['token']=str(uuid.uuid5(uuid.NAMESPACE_URL,json.dumps(row,sort_keys=True)))
                rows.append(row)
        return dict(createFileControlsVersion=1,open=True,ready=True,
            scope=dict(instance=self.native.bridge_id,generation=self.native.generation,processId=123,
                elapsedMs=round(self.clock*1000) if self.native_elapsed is None else self.native_elapsed,
                sequence=self.command_sequence),controls=rows,
            inventory=dict(inventoryVersion=1,instance='d'*32,sequence=self.source_sequence,complete=True,
                roots=sorted(roots,key=lambda row:row['id']),retiredRoots=sorted(self.retired)))
    def apply(self,command):
        if self.before_input:self.before_input()
        before=self.capture();row=next(r for r in before['controls'] if r['id']==command['controlId'])
        valid=(command['controlToken']==row['token'] and command['bridgeId']==before['scope']['instance']
            and command['generation']==before['scope']['generation'] and command['sequence']==self.command_sequence+1
            and row['inputReady'])
        self.input.append(deepcopy(command))
        if valid:
            intent=self.intents[-1]
            if intent['scope']!=before['scope'] or intent['controlToken']!=row['token']:raise AssertionError('missing original durable intent')
            if not self.no_counter:self.command_sequence+=1
            identifier=command['controlId'];action=command['action']
            if identifier not in self.ignore:
                if action=='replace':self.text=command['text']
                elif identifier=='create-file.cancel' or identifier=='create-file.accept':
                    if identifier.endswith('accept'):self.selected.append(self.text)
                    else:self.cancels+=1
                    if self.retain:self.closing=True
                    else:self.retired.append(self.root);self.root=None
                elif action=='activate':self.focus=identifier
        return valid


class CreateFileUITests(unittest.TestCase):
    def setUp(self):
        fixture=sources.PicoNormalScriptsTests();fixture.setUp();self.addCleanup(fixture.doCleanups)
        self.instance,self.native=fixture.instance,fixture.native
        self.native.opened=True;self.boundary=FileEffects(self.native)
        original_snapshot=self.native.snapshot;original_write=self.native.write_debug_app_file
        def capture():
            value=original_snapshot();original=self.boundary.capture();scope=original['scope']
            value.update(createFileControlsVersion=1,createUiInventory=original['inventory'],controls=original['controls'],
                elapsedMs=scope['elapsedMs'],lastCommandSequence=scope['sequence'],open=True,ready=True)
            return value
        def write(target,package,path,raw):
            if path!='files/overte-e2e/navigation-ui-command.json':return original_write(target,package,path,raw)
            command=json.loads(raw);valid=self.boundary.apply(command)
            self.native.sequence=self.boundary.command_sequence
            self.native.status=dict(schemaVersion=1,bridgeId=self.native.bridge_id,commandId=command['commandId'],
                sequence=command['sequence'],performed=valid,error='' if valid else 'control-unavailable',processId=123,
                updatedEpochMs=self.native.epoch_milliseconds(target))
        self.capture=capture
        for boundary in (patch.object(self.native,'snapshot',side_effect=capture),
            patch.object(self.native,'write_debug_app_file',side_effect=write)):
            boundary.start();self.addCleanup(boundary.stop)
        self.before=deepcopy(capture()['createUiInventory']);self.boundary.open()
        self.flow=self.instance._create_file_controls(self.native.target,self.boundary.intents.append,DIRECTORY,
            RUN,TICKET,'import',self.before)
        self.flow.monotonic=lambda:self.boundary.clock;self.flow.sleep=self.boundary.sleep

    def test_real_pico_route_accepts_original_import_path_and_proves_root_retirement(self):
        before=self.boundary.clock;self.flow.accept()
        self.assertEqual([PATH+'/entity-import.json'],self.boundary.selected)
        self.assertGreaterEqual(self.boundary.clock-before,3)
        self.assertIn('c'*32,self.boundary.retired)
        self.assertTrue(self.boundary.intents)
        self.assertFalse(any(cap.startswith('feature.create.') for cap in self.instance.capabilities(self.native.target)))

    def test_real_save_route_uses_distinct_export_role_and_original_destination(self):
        self.boundary.root=None;self.boundary.role='export'
        before=deepcopy(self.capture()['createUiInventory']);self.boundary.root='e'*32
        flow=self.instance._create_file_controls(self.native.target,self.boundary.intents.append,DIRECTORY,RUN,TICKET,'export',before)
        flow.monotonic=lambda:self.boundary.clock;flow.sleep=self.boundary.sleep;flow.accept()
        self.assertEqual([PATH+'/export.json'],self.boundary.selected)

    def test_ignored_cancel_or_retained_closing_callback_cannot_retire(self):
        self.boundary.ignore={'create-file.cancel'}
        with self.assertRaises(NativeUIError):self.flow.cancel()
        self.assertEqual('c'*32,self.boundary.root);self.assertEqual([],self.boundary.retired)
        self.assertEqual(1,sum(c['controlId']=='create-file.cancel' for c in self.boundary.input))
        self.boundary.ignore=set();self.boundary.retain=True
        with self.assertRaises(NativeUIError):self.flow.cancel()
        self.assertTrue(self.boundary.closing);self.assertEqual([],self.boundary.retired)

    def test_ignored_typed_path_or_ack_without_counter_cannot_establish_acceptance(self):
        self.boundary.ignore={'create-file.name'}
        with self.assertRaises(NativeUIError):self.flow.accept()
        self.assertEqual([],self.boundary.selected)
        self.boundary.ignore=set();self.boundary.no_counter=True
        with self.assertRaises(NativeUIError):self.flow.input('create-file.name')
        before=len(self.boundary.input)
        with self.assertRaises(NativeUIError):self.flow.input('create-file.name')
        self.assertEqual(before,len(self.boundary.input))

    def test_foreign_reused_replaced_or_incomplete_original_roots_refuse_input(self):
        current=self.flow.capture();self.flow.page(current)
        self.boundary.before_input=lambda:setattr(self.boundary,'root','e'*32)
        with self.assertRaises(RuntimeError):self.flow.input('create-file.name')
        self.assertIsNone(self.boundary.focus)
        self.boundary.before_input=None
        with self.assertRaises(NativeUIError):self.flow.page(self.flow.capture())
        reused=deepcopy(self.before);reused['roots']=current['inventory']['roots']
        with self.assertRaises(NativeUIError):CreateFileUI(self.flow.io,lambda _v:None,DIRECTORY,RUN,TICKET,'import',reused)

    def test_frozen_retirement_inventory_cannot_accumulate_a_quiet_window(self):
        self.flow.wait_open();self.flow.input('create-file.cancel');self.boundary.frozen=True
        with self.assertRaises(NativeUIError):self.flow.retired()

    def test_host_quiet_and_increasing_native_inventory_cannot_replace_frozen_native_clock(self):
        self.flow.wait_open();self.flow.input('create-file.cancel');self.boundary.native_elapsed=0
        before=self.boundary.source_sequence
        with self.assertRaises(NativeUIError):self.flow.retired()
        self.assertGreater(self.boundary.clock,3)
        self.assertGreater(self.boundary.source_sequence,before)

    def test_unknown_late_picker_or_missing_original_editor_cannot_qualify_cleanup(self):
        self.flow.wait_open();self.flow.input('create-file.cancel');self.boundary.root='e'*32
        with self.assertRaises(NativeUIError):self.flow.retired()
        missing=deepcopy(self.before);missing['roots']=[]
        with self.assertRaises(NativeUIError):CreateFileUI(self.flow.io,lambda _v:None,DIRECTORY,RUN,TICKET,'import',missing)

    def test_failed_intent_covered_or_wrong_role_path_refuses_normal_input(self):
        def failed(_v):raise NativeUIError('synthetic journal unavailable')
        self.flow.intent=failed
        with self.assertRaises(NativeUIError):self.flow.input('create-file.name')
        self.assertEqual([],self.boundary.input)
        self.flow.intent=self.boundary.intents.append;self.boundary.covered=True
        with self.assertRaises(NativeUIError):self.flow.input('create-file.name')
        self.assertEqual([],self.boundary.input)
        self.boundary.covered=False;self.flow.input('create-file.name')
        before=len(self.boundary.input)
        for value in (PATH+'/export.json',PATH.replace(RUN,'f'*32)+'/entity-import.json','/foreign/entity-import.json'):
            with self.subTest(value=value),self.assertRaises(NativeUIError):self.flow.input('create-file.name','replace',value)
        self.assertEqual(before,len(self.boundary.input))

    def test_closed_raw_schemas_reject_unknown_fields_duplicate_roots_or_retired_reappearance(self):
        actual=self.flow.capture();page=next(r for r in actual['controls'] if r['id']=='create-file.page')
        for changes in ({'role':'scripts'},{'filter':'*.js'},{'inputReady':True},{'rootId':'0'*32},{'expected':True}):
            with self.subTest(changes=changes),self.assertRaises(NativeUIError):metadata(page|changes)
        for changes in ({'complete':False},{'roots':actual['inventory']['roots']*2},{'retiredRoots':['c'*32]}):
            with self.assertRaises(NativeUIError):inventory(actual['inventory']|changes)
        raw=self.capture();raw['createUiInventory']=actual['inventory']|{'expected':'closed'}
        with self.assertRaises(NativeUIError):validate_snapshot(raw,123,self.native.epoch_milliseconds(self.native.target))


if __name__=='__main__':unittest.main()
