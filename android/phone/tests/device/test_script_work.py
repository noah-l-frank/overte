"""Actual Phone factory/probe routing with explicit synthetic SDK/native seams."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT/'tests/device'),str(ROOT/'tests/device/adapters/android-phone')]
from adapters.normal_ui import NativeUIError
from self_tests.test_native_script_work import WorkBoundary,MANAGER
from self_tests.test_native_feature_observation import probe_source


class PhoneScriptWorkTests(unittest.TestCase):
    def factory(self):
        import test_feature_adapters as bound
        setup=bound.FeatureAdapterTests();setup.setUp();self.addCleanup(setup.doCleanups);setup.read_only_boundaries()
        source=WorkBoundary()
        def send(client,session,target,command,process):
            self.assertEqual({'running':True,'identity':'31:14'},process);source.send(command)
        def read(device,package,path,**kwargs):
            self.assertEqual('files/overte-e2e/feature-script-work.json',path);self.assertEqual({'attempts':1},kwargs)
            return source.original()
        for boundary in (patch.object(setup.adapter,'write_android_client_command',side_effect=send),
            patch.object(setup.fixture.adb,'read_debug_app_file',side_effect=read,create=True),
            patch.object(setup.fixture.adb,'epoch_milliseconds',return_value=20000,create=True)):
            boundary.start();self.addCleanup(boundary.stop)
        return setup,source,setup.adapter._script_work(bound.SELECTOR)

    def test_actual_factory_reads_original_work_without_input_or_session_repair(self):
        setup,source,reader=self.factory();first=reader.read(MANAGER);second=reader.read(MANAGER,first['sequence'])
        self.assertEqual(source.value,second);self.assertEqual([],setup.native.inputs);self.assertEqual([],setup.native.lifecycle_inputs)
        self.assertEqual(2,len(source.commands));self.assertEqual(MANAGER,second['source']['manager']['instance'])

    def test_expected_results_or_mutations_are_refused_by_the_actual_read_only_channel(self):
        setup,source,reader=self.factory();reader.read(MANAGER)
        request=dict(schemaVersion=1,commandId='f'*32,action='feature-script-work-observe',managerInstance=MANAGER)
        for edit in (dict(expectedTimers=0),dict(action='clear-script-work'),dict(managerInstance=MANAGER+'\n')):
            with self.subTest(edit=edit),self.assertRaises((ValueError,RuntimeError)):reader.send(request|edit)
        self.assertEqual(1,len(source.commands));self.assertEqual([],setup.native.inputs)

    def test_changed_candidate_and_non_read_only_mode_are_rejected(self):
        import test_feature_adapters as bound
        setup,source,reader=self.factory();first=reader.read(MANAGER);setup.fixture.adb.digest='f'*64
        with self.assertRaises(NativeUIError):reader.read(MANAGER,first['sequence'])
        self.assertEqual(1,len(source.commands))
        with self.assertRaises((RuntimeError,ValueError)):setup.adapter._script_work(bound.SELECTOR,read_only=False)

    def test_component_does_not_advertise_incomplete_emote_capabilities(self):
        setup,_source,_reader=self.factory()
        self.assertFalse(any(value.startswith('feature.emotes.') for value in setup.adapter.advertised_capabilities(setup.target)))

    def test_actual_js_probe_polls_only_the_same_read_and_cancels_replaced_observation_timers(self):
        program=r'''
const Uuid={generate:()=>"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"};
const objectKeysMatch=(value,keys)=>JSON.stringify(Object.keys(value).sort())===JSON.stringify(keys.sort());
let calls=[],files=[],queue=new Map(),next=1,cleared=[];
const Script={setTimeout:(fn,ms)=>{if(ms!==50)throw Error("unexpected wait");const id=next++;queue.set(id,fn);return id;},
 clearTimeout:id=>{cleared.push(id);queue.delete(id);}};
const counts=new Map();
const Test={featureScriptWork:r=>{calls.push({...r});const n=(counts.get(r.commandId)||0)+1;counts.set(r.commandId,n);
 if(n===1)return {requestId:r.commandId,pending:true};
 return {schemaVersion:1,requestId:r.commandId,source:{actualTimerHandle:7}};},saveObject:(value,name)=>files.push({value,name})};
SOURCE
const request={schemaVersion:1,commandId:"a".repeat(32),action:"feature-script-work-observe",managerInstance:"c".repeat(32)};
applyAndroidControlCommand(request);applyAndroidControlCommand(request);
if(calls.length!==1||queue.size!==1||files.length!==0)throw Error("pending is not a completed observation");
let entry=[...queue.entries()][0];queue.delete(entry[0]);entry[1]();
if(calls.length!==2||files[0].value.source.actualTimerHandle!==7||files[0].name!=="feature-script-work.json")throw Error("original result");
for(const edit of [{expectedTimers:0},{code:"Script.clearTimeout(7)"},{managerInstance:["c".repeat(32)]},
 {managerInstance:"c".repeat(32)+"\n"},{commandId:["b".repeat(32)]},{schemaVersion:true}]){
 applyAndroidControlCommand({...request,commandId:"b".repeat(32),...edit});}
if(calls.length!==2)throw Error("expected results or foreign command admitted");
applyAndroidControlCommand({...request,commandId:"d".repeat(32)});
const old=[...queue.values()][0];
applyAndroidControlCommand({...request,commandId:"e".repeat(32)});
const before=calls.length;old();if(calls.length!==before||cleared.length!==1)throw Error("replaced read callback survived");
delete Test.featureScriptWork;applyAndroidControlCommand({...request,commandId:"f".repeat(32)});
if(files[1].value.available!==false)throw Error("missing native owner green");
'''.replace('SOURCE',probe_source())
        result=subprocess.run(['node','-e',program],capture_output=True,text=True,timeout=5)
        self.assertEqual(0,result.returncode,result.stderr)

    def test_actual_js_pending_deadline_never_synthesizes_zero_timers(self):
        program=r'''
const Uuid={generate:()=>"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"};
const objectKeysMatch=(value,keys)=>JSON.stringify(Object.keys(value).sort())===JSON.stringify(keys.sort());
let calls=0,files=[],queue=[];
const Script={setTimeout:fn=>{queue.push(fn);return queue.length;},clearTimeout:()=>{}};
const Test={featureScriptWork:r=>{calls++;return {requestId:r.commandId,pending:true};},saveObject:value=>files.push(value)};
SOURCE
applyAndroidControlCommand({schemaVersion:1,commandId:"a".repeat(32),action:"feature-script-work-observe",managerInstance:"c".repeat(32)});
while(queue.length){const fn=queue.shift();fn();}
if(calls!==51||files.length!==1||files[0].available!==false||"source" in files[0])throw Error("pending guessed empty work");
'''.replace('SOURCE',probe_source())
        result=subprocess.run(['node','-e',program],capture_output=True,text=True,timeout=5)
        self.assertEqual(0,result.returncode,result.stderr)


if __name__=='__main__':unittest.main()
