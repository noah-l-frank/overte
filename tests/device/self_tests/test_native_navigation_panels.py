"""Original Python/probe/private Pico route; all Qt/QObject boundaries synthetic."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace
import subprocess
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from adapters.native_navigation_panels import NativeNavigationPanels,command,retired
from adapters.normal_ui import NativeUIError
from fixture.serve import FixtureState
from self_tests.test_native_feature_observation import probe_source

RUN='a'*32

class Boundary:
    def __init__(self):
        self.clock=0.;self.sequence=0;self.commands=[];self.packet=None;self.rows=[];self.edit=None;self.ignore=False
        self.alive=True;self.input_sequence=0;self.open=True;self.bridge='1'*32;self.generation='2'*32
    def epoch(self):return 20000+round(self.clock*1000)
    def sleep(self,s):self.clock+=s
    def create(self,profile='pico-address-v1',root='e'*32):
        row=dict(rootId=root,profile=profile,sourceSha256='d'*64,firstObservedEpochMs=self.epoch(),alive=True,inCurrentTree=True,visible=True)
        self.rows.append(row);return row
    def send(self,request):
        self.commands.append(deepcopy(request))
        if self.ignore:return
        self.sequence+=1
        self.packet=dict(navigationPanelsVersion=1,commandId=request['commandId'],runId=request['runId'],instance='f'*32,
            sequence=self.sequence,processId=31,capturedEpochMs=self.epoch(),complete=True,roots=deepcopy(self.rows),
            ui=dict(bridgeId=self.bridge,generation=self.generation,sequence=self.input_sequence,elapsedMs=100+round(self.clock*1000),
                observedEpochMs=self.epoch(),open=self.open,ready=self.open))
        if self.edit:self.edit(self.packet)
    def reader(self):
        return NativeNavigationPanels(self.send,lambda:json.dumps(self.packet) if self.packet else '',self.epoch,lambda:self.alive,31,
            monotonic=lambda:self.clock,sleep=self.sleep)

class NavigationPanelsTests(unittest.TestCase):
    def setUp(self):self.model=Boundary()
    def test_current_hidden_retained_and_destroyed_qobjects_are_distinct_original_observations(self):
        r=self.model.reader();self.assertEqual([],r.read(RUN)['roots']);row=self.model.create();r.read(RUN)
        row.update(visible=False,inCurrentTree=False)
        with self.assertRaises(NativeUIError):retired(r.read(RUN),['e'*32])
        row['alive']=False;self.assertTrue(retired(r.read(RUN),['e'*32]))
        with self.assertRaises(NativeUIError):retired(r.read(RUN),['8'*32])
    def test_original_birth_profiles_hashes_and_root_history_cannot_drop_change_or_resurrect(self):
        for mutate in (lambda v:v['roots'].clear(),lambda v:v['roots'][0].update(profile='pico-places-v1'),
                       lambda v:v['roots'][0].update(sourceSha256='8'*64),lambda v:v['roots'][0].update(firstObservedEpochMs=19999),
                       lambda v:v.update(instance='8'*32),lambda v:v.update(sequence=1)):
            self.model=Boundary();self.model.create();r=self.model.reader();r.read(RUN);self.model.edit=mutate
            with self.subTest(mutate=mutate),self.assertRaises(NativeUIError):r.read(RUN)
        self.model=Boundary();row=self.model.create();r=self.model.reader();r.read(RUN)
        row.update(alive=False,inCurrentTree=False,visible=False);r.read(RUN);row['alive']=True
        with self.assertRaises(NativeUIError):r.read(RUN)
    def test_closed_shape_complete_inventory_pid_clock_and_visible_scope_fail_closed(self):
        edits=(lambda v:v.update(complete=False),lambda v:v.update(expected='closed'),lambda v:v.update(processId=32),
               lambda v:v.update(navigationPanelsVersion=True),lambda v:v.update(capturedEpochMs=18000),
               lambda v:v['ui'].update(observedEpochMs=18000),lambda v:v['ui'].update(open=False),
               lambda v:v['roots'][0].update(alive=False),lambda v:v['roots'][0].update(visible=1))
        for edit in edits:
            self.model=Boundary();self.model.create();self.model.edit=edit
            with self.subTest(edit=edit),self.assertRaises(NativeUIError):self.model.reader().read(RUN)
    def test_reused_query_or_unknown_old_birth_is_not_adopted_after_a_fresh_source(self):
        r=self.model.reader();first=r.read(RUN)
        with patch('adapters.native_navigation_panels.uuid.uuid4',return_value=SimpleNamespace(hex=first['commandId'])):
            with self.assertRaises(NativeUIError):r.read(RUN)
        self.model.clock+=1;row=self.model.create();row['firstObservedEpochMs']=19999
        with self.assertRaises(NativeUIError):r.read(RUN)
    def test_missing_reply_and_process_guard_keep_single_original_query_and_bounded_wait(self):
        self.model.ignore=True;r=self.model.reader()
        with self.assertRaises(NativeUIError):r.read(RUN)
        self.assertEqual(1,len(self.model.commands));self.assertLessEqual(self.model.clock,5.01)
        self.model.ignore=False;self.model.alive=False
        with self.assertRaises(NativeUIError):self.model.reader().read(RUN)
        self.assertEqual(1,len(self.model.commands))
    def test_original_probe_and_fixture_accept_only_nonce_run_source_requests(self):
        request=dict(schemaVersion=1,commandId='9'*32,action='feature-navigation-panels',runId=RUN)
        FixtureState().set_client_command(request)
        for extra in ({'expected':'closed'},{'rootId':'e'*32},{'schemaVersion':True},{'destroy':True}):
            with self.assertRaises((ValueError,NativeUIError)):command(request|extra)
            with self.assertRaises(ValueError):FixtureState().set_client_command(request|extra)
        program=r'''
const objectKeysMatch=(v,k)=>JSON.stringify(Object.keys(v).sort())===JSON.stringify(k.sort());
const Uuid={generate:()=>"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"};let calls=0,files=[];
const Test={featureNavigationPanels:c=>{calls++;return {commandId:c.commandId,original:true};},saveObject:(v,name)=>files.push({v,name})};
SOURCE
const c={schemaVersion:1,commandId:'9'.repeat(32),action:'feature-navigation-panels',runId:'a'.repeat(32)};
applyClientCommand(c);if(calls!==1||files[0].name!=='feature-navigation-panels.json'||!files[0].v.original)throw Error('Original missing');
applyClientCommand({...c,destroy:true});if(calls!==1)throw Error('Unexpected input authority');delete Test.featureNavigationPanels;
applyClientCommand({...c,commandId:'8'.repeat(32)});if(files[1].v.status!=='unavailable')throw Error('Missing source became empty cleanup');
'''.replace('SOURCE',probe_source())
        result=subprocess.run(['node','-e',program],capture_output=True,text=True,timeout=5);self.assertEqual(0,result.returncode,result.stderr)
    def test_actual_private_pico_factory_uses_original_fixed_file_and_process_clock(self):
        root=Path(__file__).resolve().parents[3];sys.path.insert(0,str(root/'android/vr/pico/tests/device'))
        import test_native_execution_binding as f
        fixture=f.NativeExecutionBindingTest();fixture.setUp();self.addCleanup(fixture.doCleanups);adapter=fixture.instance()
        adapter._native_feature_observer=lambda target:SimpleNamespace(send=self.model.send,clock_ms=self.model.epoch,
            guard=lambda:self.model.alive,pid=31,monotonic=lambda:self.model.clock,sleep=self.model.sleep)
        def read(target,package,path,*,attempts):
            self.assertEqual(('owned','org.overte.pico','files/overte-e2e/feature-navigation-panels.json',1),(target,package,path,attempts))
            return json.dumps(self.model.packet)
        adapter.adb.read_debug_app_file=read
        self.model.create();self.assertEqual(self.model.rows,adapter._navigation_panels('owned').read(RUN)['roots'])

if __name__=='__main__':unittest.main()
