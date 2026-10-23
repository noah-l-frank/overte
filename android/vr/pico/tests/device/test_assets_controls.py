"""Actual Pico binding/navigation against explicit native widget/SDK boundaries."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import inspect
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import uuid
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[4]
sys.path[:0]=[str(ROOT/'tests/device'),str(HERE)]
import test_normal_scripts as original
from adapters.pico4.navigation import NativeNavigationIO,NavigationError
from adapters.normal_ui import NativeUIError
from adapters.pico4.assets_ui import project


class AssetsControlsTests(unittest.TestCase):
    def setUp(self):
        self.fixture=original.PicoNormalScriptsTests(methodName='runTest');self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.adapter,self.native=self.fixture.instance,self.fixture.native;self.native.opened=True
        self.text='';self.focus=False;self.allowed=True;self.ignore=False;self.counter=True;self.intents=[];self.inputs=[];self.receipts=[]
        self.mutation=None
        before_read=self.native.read_debug_app_file
        def read(target,package,path,**kwargs):
            if path=='files/overte-e2e/navigation-ui-observation.json':return json.dumps(self.snapshot())
            return before_read(target,package,path,**kwargs)
        def write(target,package,path,raw):
            self.assertEqual('files/overte-e2e/navigation-ui-command.json',path);command=json.loads(raw);row=next(row for row in self.snapshot()['controls'] if row['id']==command['controlId'])
            self.assertEqual(row['token'],command['controlToken']);self.assertEqual(self.native.sequence+1,command['sequence']);self.inputs.append(deepcopy(command))
            if self.counter:self.native.sequence+=1
            if not self.ignore:
                if command['action']=='activate':self.focus=command['controlId']=='assets.filter'
                elif command['action']=='replace':self.assertTrue(self.focus);self.text=command['text']
                else:self.assertEqual(('assets.delete','probe-disabled'),(command['controlId'],command['action']));self.assertFalse(self.allowed)
            self.native.status=dict(schemaVersion=1,bridgeId=self.native.bridge_id,commandId=command['commandId'],sequence=command['sequence'],performed=True,error='',processId=123,updatedEpochMs=self.native.epoch_milliseconds(self.native.target))
        for boundary in (patch.object(self.native,'read_debug_app_file',side_effect=read),patch.object(self.native,'write_debug_app_file',side_effect=write)):
            boundary.start();self.addCleanup(boundary.stop)
    def snapshot(self):
        rows=[]
        def add(identifier,**extra):
            row=dict(id=identifier,enabled=True,focused=False,inputReady=True)|extra
            row['token']=str(uuid.uuid5(uuid.NAMESPACE_URL,json.dumps(row,sort_keys=True)));rows.append(row)
        add('assets.page',inputReady=False,profile='native-assets-v1',canWrite=self.allowed,canImport=True,busy=False,status='',selectedPath='',selectedUrl='',selection=[],selectedStatus='',treeRevision=1,uploadedPrimaryUrl='',uploadActive=False,pendingBundle=False)
        add('assets.filter',text=self.text,focused=self.focus);add('assets.delete',enabled=self.allowed,inputReady=self.allowed)
        add('assets.upload');rows.append(dict(id='tablet.home',token='99999999-9999-4999-8999-999999999999',enabled=True,focused=False))
        value=dict(schemaVersion=1,bridgeId=self.native.bridge_id,generation=self.native.generation,processId=123,elapsedMs=self.native.native_elapsed,
            updatedEpochMs=self.native.epoch_milliseconds(self.native.target),lastCommandSequence=self.native.sequence,open=True,ready=True,featureControlsVersion=1,assetsControlsVersion=1,controls=rows)
        if self.mutation:self.mutation(value)
        return value
    def controls(self,*,before_send=None):return self.adapter._assets_controls(self.native.target,self.intents.append,before_send=before_send)
    def test_normal_pico_binding_source_and_consumed_text_input(self):
        ui=self.controls(before_send=lambda command,navigation:self.receipts.append(deepcopy(command)));ui.replace('assets.filter','main.gltf')
        self.assertEqual('main.gltf',self.text);self.assertEqual(2,len(self.inputs));self.assertEqual(self.inputs,self.receipts);self.assertEqual(2,len(self.intents))
        self.assertTrue(any(row['id']=='tablet.home' and row['inputReady'] for row in ui.capture()['controls']))
    def test_ack_without_consumed_sequence_or_effect_never_passes(self):
        for fault in ('counter','effect'):
            with self.subTest(fault=fault):
                self.counter=fault!='counter';self.ignore=fault=='effect';before=len(self.inputs)
                with self.assertRaises((NativeUIError,NavigationError)):self.controls().replace('assets.filter','main.gltf')
                self.assertLessEqual(len(self.inputs)-before,2)
    def test_disabled_probe_is_closed_and_does_not_enable_or_confirm(self):
        self.allowed=False;ui=self.controls();ui.input('assets.delete','probe-disabled')
        self.assertEqual(1,len(self.inputs));self.assertFalse(ui.row(ui.capture(),'assets.delete',enabled=False)['enabled']);self.assertEqual('probe-disabled',self.inputs[-1]['action'])
        before=len(self.inputs)
        for identifier in ('assets.upload','assets.delete'):
            self.allowed=identifier=='assets.delete'
            with self.assertRaises((NativeUIError,NavigationError)):self.controls().input(identifier,'probe-disabled')
        self.assertEqual(before,len(self.inputs))
    def test_last_original_guard_refuses_before_writer(self):
        actual=NativeNavigationIO.guard;fired=[]
        def guard(io):
            actual(io)
            if inspect.currentframe().f_back.f_code.co_name=='send':fired.append(True)
        def fence(command,navigation):
            self.assertTrue(fired);raise NativeUIError('Declared changed original phase at final input fence')
        with patch.object(NativeNavigationIO,'guard',guard),self.assertRaises((NativeUIError,NavigationError)):self.controls(before_send=fence).input('assets.upload')
        self.assertTrue(fired);self.assertFalse(self.inputs);self.assertEqual(1,len(self.intents))
    def test_stale_foreign_and_missing_marker_references_never_publish(self):
        ui=self.controls();saved=ui.capture();self.allowed=False
        with self.assertRaises((NativeUIError,NavigationError)):ui.io.probe_disabled('assets.delete',reference=saved)
        self.assertFalse(self.inputs)
        foreign=deepcopy(ui.capture());foreign['scope']['instance']='aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'
        with self.assertRaises((NativeUIError,NavigationError)):ui.io.activate('assets.upload',reference=foreign)
        self.assertFalse(self.inputs)
        self.mutation=lambda packet:packet.pop('assetsControlsVersion')
        with self.assertRaises((NativeUIError,NavigationError)):self.controls().capture()
        self.assertFalse(self.inputs)


if __name__=='__main__':unittest.main()
