"""Actual Phone source factory and probe, with synthetic native/SDK boundaries."""
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
from self_tests.test_native_script_roots import RootBoundary
from self_tests.test_native_feature_observation import probe_source


class PhoneScriptRootsTests(unittest.TestCase):
    def factory(self,*,read_only=False):
        import test_feature_adapters as bound
        setup=bound.FeatureAdapterTests();setup.setUp();self.addCleanup(setup.doCleanups)
        source=RootBoundary()
        def send(client,session,target,command,process):
            self.assertEqual({'running':True,'identity':'31:14'},process);source.send(command)
        def read(device,package,path,**kwargs):
            self.assertEqual('files/overte-e2e/feature-script-roots.json',path);self.assertEqual({'attempts':1},kwargs)
            return source.original()
        for boundary in (patch.object(setup.adapter,'write_android_client_command',side_effect=send),
            patch.object(setup.fixture.adb,'read_debug_app_file',side_effect=read,create=True),
            patch.object(setup.fixture.adb,'epoch_milliseconds',return_value=20000,create=True)):
            boundary.start();self.addCleanup(boundary.stop)
        if read_only:setup.read_only_boundaries()
        return setup,source,setup.adapter._script_roots(bound.SELECTOR,read_only=read_only)

    def test_actual_candidate_bound_factory_retains_original_configured_resource_root(self):
        setup,source,reader=self.factory();first=reader.read(0);source.running_url='file:///foreign/phoneEmote.js'
        second=reader.read(first['sequence'])
        self.assertEqual(source.root,second['source']['defaultScriptsUrl']);self.assertEqual(first['source'],second['source'])
        self.assertEqual([],setup.native.inputs);self.assertEqual([],setup.native.lifecycle_inputs)
        self.assertTrue(all(set(command)=={'schemaVersion','commandId','action'} for command in source.commands))

    def test_actual_read_only_factory_never_repairs_session_or_accepts_root_selection(self):
        setup,source,reader=self.factory(read_only=True);first=reader.read(0)
        with self.assertRaises((ValueError,RuntimeError)):
            reader.send(dict(schemaVersion=1,commandId='a'*32,action='feature-script-roots-observe',root='file:///expected/scripts'))
        self.assertEqual(1,len(source.commands));self.assertEqual([],setup.native.inputs)
        self.assertEqual(first['source'],reader.last['source'])

    def test_changed_installed_candidate_is_rejected_before_any_new_getter_command(self):
        setup,source,reader=self.factory();first=reader.read(0);setup.fixture.adb.digest='f'*64
        with self.assertRaises(NativeUIError):reader.read(first['sequence'])
        self.assertEqual(1,len(source.commands))

    def test_actual_probe_reads_only_closed_original_metadata_and_refuses_missing_native_hook(self):
        program=r'''
const Uuid={generate:()=>"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"};
const objectKeysMatch=(v,keys)=>JSON.stringify(Object.keys(v).sort())===JSON.stringify(keys.sort());
let calls=[],files=[];
const Test={featureScriptRoots:r=>{calls.push(r);return {commandId:r.commandId,source:{defaultScriptsUrl:"file:///actual/scripts"}};},
saveObject:(v,name)=>files.push({v,name})};
SOURCE
const request={schemaVersion:1,commandId:"a".repeat(32),action:"feature-script-roots-observe"};
applyAndroidControlCommand(request);applyAndroidControlCommand(request);
if(calls.length!==1||files[0].name!=="feature-script-roots.json"||files[0].v.source.defaultScriptsUrl!=="file:///actual/scripts")throw Error("original dispatch");
for(const edit of [{root:"file:///expected/scripts"},{expectedProfile:"known"},{commandId:["b".repeat(32)]},
 {commandId:"b".repeat(32)+"\n"},{schemaVersion:true},{sourceUrl:"file:///foreign/phoneEmote.js"}]){
 applyAndroidControlCommand({...request,commandId:"b".repeat(32),...edit});}
if(calls.length!==1)throw Error("root or profile input accepted");
delete Test.featureScriptRoots;applyAndroidControlCommand({...request,commandId:"c".repeat(32)});
if(files[1].v.available!==false)throw Error("missing native getter inferred a root");
'''.replace('SOURCE',probe_source())
        result=subprocess.run(['node','-e',program],capture_output=True,text=True,timeout=5)
        self.assertEqual(0,result.returncode,result.stderr)


if __name__=='__main__':unittest.main()
