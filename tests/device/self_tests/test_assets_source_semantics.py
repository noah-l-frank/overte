"""Original Assets/picker JS bodies and original fixture bytes, without Qt.

VM boundaries are synthetic and cannot prove upload, bake, render or devices.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import unittest

DEVICE=Path(__file__).resolve().parents[1]
ROOT=DEVICE.parents[1]
sys.path.insert(0,str(DEVICE))
from feature_journeys.asset_fixture import bundle
from feature_journeys.fixtures import companion,payload,pinned_resource

RUN,TICKET='a'*32,'b'*32
URL='http://owned.test/feature-fixture/v1/runs/'+RUN+'/'
SETUP=r'''
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const assets=fs.readFileSync(process.argv[1],'utf8'),picker=fs.readFileSync(process.argv[2],'utf8');
function section(source,start,end){const a=source.indexOf(start),b=source.indexOf(end,a+start.length);
 assert(a>=0&&b>a,'Original QML handler boundary changed');return source.slice(a,b);}
let status='--',bakeCalls=[],finished=[];
const scope={tree:{revision:1,selectedIndexes:[{}],currentIndex:{}},assetProxyModel:{data:()=>status},
 selectedItemCount:1,root:{assetWriteAllowed:true,busy:false,selectedItemCount:1},
 busy:false,writable:()=>scope.root.assetWriteAllowed,selectedPaths:()=>['/owned/main.gltf'],
 Assets:{setBakingEnabled:(paths,enabled,callback)=>bakeCalls.push({paths,enabled})},resultHandler:()=>()=>{}};
vm.createContext(scope);vm.runInContext(section(assets,'    function bakingAvailable(', '    function importSucceeded('),scope);
'''


class AssetsSourceSemantics(unittest.TestCase):
    def run_case(self,body):
        result=subprocess.run(['node','-e',SETUP+body,
            str(ROOT/'interface/resources/qml/hifi/dialogs/TabletAssetServer.qml'),
            str(ROOT/'interface/resources/qml/dialogs/NativeFileBrowser.qml')],
            capture_output=True,text=True,timeout=5)
        self.assertEqual(0,result.returncode,result.stdout+result.stderr)

    def test_original_import_requires_a_primary_file_extension(self):
        self.run_case(r'''
for(const name of ['main.gltf','main.obj','stand.fbx'])assert(scope.canAddToWorld('atp:/owned/'+name));
for(const name of ['owned','owned/','main.fst'])assert(!scope.canAddToWorld('atp:/'+name));
scope.selectedItemCount=2;assert(!scope.canAddToWorld('atp:/owned/main.gltf'));
''')

    def test_original_baking_control_rejects_unavailable_and_toggles_both_ways(self):
        self.run_case(r'''
assert(!scope.bakingAvailable());scope.setBakingEnabled(true);assert.equal(bakeCalls.length,0);
status='Not Baked';assert(scope.bakingAvailable());scope.setBakingEnabled(true);
assert.equal(bakeCalls.length,1);assert.equal(bakeCalls[0].enabled,true);
scope.busy=false;status='Baked';scope.setBakingEnabled(false);
assert.equal(bakeCalls.length,2);assert.equal(bakeCalls[1].enabled,false);
scope.busy=false;scope.root.assetWriteAllowed=false;scope.setBakingEnabled(true);
assert.equal(bakeCalls.length,2);
''')

    def test_original_delete_control_is_disabled_instead_of_dispatching_an_error(self):
        self.run_case(r'''
const line=assets.split('\n').find(s=>s.includes('objectName: "assetDelete"'));
assert(line);const binding=/enabled:\s*([^;]+)/.exec(line);assert(binding);
assert.equal(vm.runInContext(binding[1],scope),true);
scope.root.assetWriteAllowed=false;assert.equal(vm.runInContext(binding[1],scope),false);
scope.root.assetWriteAllowed=true;scope.root.busy=true;assert.equal(vm.runInContext(binding[1],scope),false);
scope.root.busy=false;scope.root.selectedItemCount=0;assert.equal(vm.runInContext(binding[1],scope),false);
''')

    def test_original_picker_rechecks_actual_file_before_finishing_selection(self):
        self.run_case(r'''
let available=true;
Object.assign(scope,{selectDirectory:false,saveDialog:false,multiSelect:true,chosen:['file:///owned/main.gltf'],
 helper:{urlIsFile:()=>available},finish:urls=>finished.push(urls),error:''});
vm.runInContext(section(picker,'    function accept(', '    onDirChanged:'),scope);
available=false;scope.accept();assert.equal(finished.length,0);
assert.equal(scope.error,'A selected file is no longer available.');
available=true;scope.accept();assert.equal(finished.length,1);assert.equal(scope.error,'');
''')

    def test_closed_bundles_preserve_actual_original_files_and_relative_paths(self):
        for resource in ('gltf-bundle/main.gltf','obj-bundle/main.obj','asset-stand.fbx'):
            value=bundle(RUN,TICKET,URL,resource)
            registry=json.loads((DEVICE/'contract-versions.json').read_text())
            self.assertEqual(registry['contracts']['asset-input-bundle']['current'],value['assetBundleVersion'])
            self.assertEqual('/e2e-'+RUN+'/',value['destination'])
            self.assertIn(value['primaryPath'],[row['relativePath'] for row in value['files']])
            for row in value['files']:
                name=row['resourceUrl'].removeprefix(URL+'tickets/'+TICKET+'/')
                content=payload(name,RUN,TICKET)
                raw=content[1] if content is not None else companion(name)
                self.assertEqual(len(raw),row['bytes'])
                self.assertEqual(hashlib.sha256(raw).hexdigest(),row['sha256'])
        raw=pinned_resource('asset-stand.fbx')
        self.assertTrue(raw.startswith(b'Kaydara FBX Binary  \x00\x1a\x00'))
        self.assertLess(len(raw),32768)

    def test_bundle_refuses_old_fictitious_primary_and_foreign_scope_before_staging(self):
        for resource in ('model.gltf','missing.gltf','../stand.fbx','wearable.json'):
            with self.subTest(resource=resource),self.assertRaises(ValueError):bundle(RUN,TICKET,URL,resource)
        with self.assertRaises(ValueError):bundle(RUN,TICKET,URL.replace(RUN,'c'*32),'asset-stand.fbx')


if __name__=='__main__':unittest.main()
