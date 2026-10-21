"""Real Phone factory/probe; all SDK/native interfaces are synthetic boundaries."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT/'tests/device'),str(ROOT/'tests/device/adapters/android-phone'),str(ROOT/'tests/device/self_tests')]
from adapters.normal_ui import NativeUIError
from test_native_animation_inventory import InventoryBoundary
from self_tests.test_native_feature_observation import probe_source


class PhoneAnimationInventoryTests(unittest.TestCase):
    def factory(self,*,read_only=False):
        import test_feature_adapters as bound
        setup=bound.FeatureAdapterTests();setup.setUp();self.addCleanup(setup.doCleanups);source=InventoryBoundary()
        def send(client,session,target,command,process):
            self.assertEqual({'running':True,'identity':'31:14'},process);source.send(command)
        def read(device,package,path,**options):
            self.assertEqual('files/overte-e2e/feature-animation-inventory.json',path);self.assertEqual({'attempts':1},options)
            return source.original()
        for boundary in (patch.object(setup.adapter,'write_android_client_command',side_effect=send),
            patch.object(setup.fixture.adb,'read_debug_app_file',side_effect=read,create=True),
            patch.object(setup.fixture.adb,'epoch_milliseconds',return_value=20000,create=True)):
            boundary.start();self.addCleanup(boundary.stop)
        if read_only:setup.read_only_boundaries()
        return setup,source,setup.adapter._animation_inventory(bound.SELECTOR,read_only=read_only)

    def test_actual_candidate_bound_factory_queries_only_passive_inventory(self):
        setup,source,reader=self.factory();first=reader.read(0);reader.read(first['sequence'])
        self.assertEqual(12,len(first['source']['resources']));self.assertEqual([],setup.native.inputs)
        self.assertEqual([],setup.native.lifecycle_inputs)
        self.assertTrue(all(set(command)=={'schemaVersion','commandId','action'} for command in source.commands))

    def test_read_only_factory_does_not_repair_or_accept_resource_selection(self):
        setup,source,reader=self.factory(read_only=True);reader.read(0)
        with self.assertRaises((ValueError,RuntimeError)):
            reader.send(dict(schemaVersion=1,commandId='a'*32,action='feature-animation-inventory-observe',url='qrc:/expected.fbx'))
        self.assertEqual(1,len(source.commands));self.assertEqual([],setup.native.inputs)

    def test_changed_installed_candidate_rejects_next_query_before_transport(self):
        setup,source,reader=self.factory();first=reader.read(0);setup.fixture.adb.digest='f'*64
        with self.assertRaises(NativeUIError):reader.read(first['sequence'])
        self.assertEqual(1,len(source.commands))

    def test_original_probe_dispatch_is_closed_deduplicated_and_missing_hook_is_unavailable(self):
        program=r'''
const Uuid={generate:()=>"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"};
const objectKeysMatch=(v,keys)=>JSON.stringify(Object.keys(v).sort())===JSON.stringify(keys.sort());
let calls=[],files=[];
const Test={featureAnimationInventory:r=>{calls.push(r);return {commandId:r.commandId,source:{complete:true,registrySlots:0,expiredSlots:0,resources:[]}};},
saveObject:(v,name)=>files.push({v,name})};
SOURCE
const request={schemaVersion:1,commandId:"a".repeat(32),action:"feature-animation-inventory-observe"};
applyAndroidControlCommand(request);applyAndroidControlCommand(request);
if(calls.length!==1||files[0].name!=="feature-animation-inventory.json"||files[0].v.source.resources.length!==0)throw Error("original dispatch");
for(const edit of [{url:"qrc:/expected.fbx"},{expectedSha256:"f".repeat(64)},{commandId:["b".repeat(32)]},
 {commandId:"b".repeat(32)+"\n"},{schemaVersion:true},{prefetch:true}]){
 applyAndroidControlCommand({...request,commandId:"b".repeat(32),...edit});}
if(calls.length!==1)throw Error("resource selection accepted");
delete Test.featureAnimationInventory;applyAndroidControlCommand({...request,commandId:"c".repeat(32)});
if(files[1].v.available!==false)throw Error("missing native getter supplied readiness");
'''.replace('SOURCE',probe_source())
        result=subprocess.run(['node','-e',program],capture_output=True,text=True,timeout=5)
        self.assertEqual(0,result.returncode,result.stderr)


if __name__=='__main__':unittest.main()
