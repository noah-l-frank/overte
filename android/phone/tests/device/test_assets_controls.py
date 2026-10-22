"""Original UI transport/recipe negatives; explicit synthetic widget buffers only."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT/'tests/device'),str(ROOT/'tests/device/adapters/android-phone')]
from adapters.normal_ui import NativeUIError
from adapters.token_assets_ui import TokenAssetsUI,snapshot,metadata,same_reference
from overte_phone_assets_controls import PhoneAssetsIO,validate
from self_tests.test_native_feature_observation import probe_source

RUN='b'*32
DIRECTORY='/private/feature-assets-'+RUN


class Widgets:
    def __init__(self):
        self.epoch=1700000000000;self.clock=0.;self.sequence=0;self.source_sequence=0;self.focus=None
        self.texts={'assets.filter':''};self.write=True;self.dialog=None;self.status='';self.selected='/e2e-'+RUN+'/main.gltf'
        self.ignore=set();self.no_counter=False;self.covered=False;self.before=None;self.intents=[];self.inputs=[]
        self.packet=None;self.fault=None
    def rows(self):
        rows=[]
        def row(identifier,**more):
            value=dict(id=identifier,enabled=True,focused=self.focus==identifier,inputReady=not self.covered)|more
            value['token']=hashlib.sha256(json.dumps([value,self.selected,self.dialog],sort_keys=True).encode()).hexdigest()[:32];rows.append(value)
        row('assets.page',inputReady=False,profile='native-assets-v1',canWrite=self.write,canImport=True,busy=False,
            status=self.status,selectedPath=self.selected,selectedUrl='atp:'+self.selected,selection=[dict(path=self.selected,folder=False,status='--')],
            selectedStatus='--',treeRevision=1,uploadedPrimaryUrl='',uploadActive=False,pendingBundle=False)
        row('assets.filter',text=self.texts['assets.filter']);row('assets.rename');row('assets.delete',enabled=self.write,inputReady=self.write and not self.covered)
        row('assets.baking',checked=False,enabled=False,inputReady=False)
        if self.dialog=='rename':
            row('assets.rename.path',text=self.texts.get('assets.rename.path',self.selected));row('assets.rename.accept');row('assets.rename.cancel')
        return rows
    def send(self,outer):
        request=outer['request'];self.source_sequence+=1
        if request['action']=='observe':
            self.packet=dict(schemaVersion=1,commandId=request['commandId'],action='observe',instance='a'*32,generation='c'*32,
                sourceSequence=self.source_sequence,lastCommandSequence=self.sequence,elapsedMs=int(self.clock*1000),capturedEpochMs=self.epoch,
                processId=321,assetsControlsVersion=1,ready=True,controls=self.rows())
            if self.fault:self.fault(self.packet)
        else:
            self.inputs.append(deepcopy(request));self.sequence+=not self.no_counter
            if request['controlId'] not in self.ignore:
                identifier=request['controlId']
                if request['action']=='replace':self.texts[identifier]=request['text']
                elif request['action']=='activate':
                    self.focus=identifier
                    if identifier=='assets.rename':self.dialog='rename'
                    elif identifier in ('assets.rename.accept','assets.rename.cancel'):self.dialog=None
            self.packet=dict(schemaVersion=1,commandId=request['commandId'],action=request['action'],performed=True,
                instance='a'*32,generation='c'*32,sequence=request['sequence'],processId=321)
    def original(self):
        if self.before:self.before()
        return json.dumps(self.packet)
    def sleep(self,value):self.clock+=value;self.epoch+=round(value*1000)
    def io(self):return PhoneAssetsIO(self.send,self.original,lambda:self.epoch,lambda:True,321,monotonic=lambda:self.clock,sleep=self.sleep)
    def recipe(self):return TokenAssetsUI(self.io(),self.intents.append,monotonic=lambda:self.clock,sleep=self.sleep)


class AssetsControlsTests(unittest.TestCase):
    def test_real_transport_reference_is_consumed_and_actual_text_read_back(self):
        b=Widgets();ui=b.recipe();ui.replace('assets.filter','main.gltf')
        self.assertEqual('main.gltf',b.texts['assets.filter']);self.assertEqual(2,len(b.inputs));self.assertEqual(2,len(b.intents))
        self.assertEqual(['activate','replace'],[value['action'] for value in b.inputs]);self.assertEqual(2,ui.sequence)
    def test_ack_without_widget_effect_or_consumed_counter_stays_red(self):
        for fault in ('ignored','counter'):
            b=Widgets()
            if fault=='ignored':b.ignore.add('assets.filter')
            else:b.no_counter=True
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):b.recipe().replace('assets.filter','main.gltf')
            self.assertLessEqual(len(b.inputs),2)
    def test_actual_disabled_delete_and_obstructed_input_are_refused(self):
        for change in ('write','covered'):
            b=Widgets()
            if change=='write':b.write=False
            else:b.covered=True
            with self.subTest(change=change),self.assertRaises(NativeUIError):b.recipe().input('assets.delete')
            self.assertEqual([],b.inputs)
    def test_explicit_disabled_delete_probe_consumes_normal_input_without_enabling(self):
        b=Widgets();b.write=False;ui=b.recipe();ui.input('assets.delete','probe-disabled')
        self.assertEqual('probe-disabled',b.inputs[-1]['action']);self.assertFalse(ui.row(ui.capture(),'assets.delete',enabled=False)['enabled'])
        self.assertFalse(ui.row(ui.capture(),'assets.delete',enabled=False)['inputReady']);self.assertIsNone(b.dialog)
        b=Widgets()
        for identifier in ('assets.delete','assets.rename'):
            with self.subTest(identifier=identifier),self.assertRaises(NativeUIError):b.recipe().input(identifier,'probe-disabled')
        self.assertEqual([],b.inputs)

    def test_foreign_context_or_replaced_control_is_not_retargeted(self):
        for change in (lambda p:p.update(generation='d'*32),lambda p:p['controls'][1].update(token='d'*32)):
            b=Widgets();io=b.io();original=io.capture();b.fault=change
            with self.subTest(change=change),self.assertRaises(NativeUIError):io.activate('assets.filter',reference=original)
            self.assertEqual([],b.inputs)
    def test_stale_process_epoch_scope_and_slow_raw_read_stay_red(self):
        for change in (lambda p:p.update(processId=322),lambda p:p.update(capturedEpochMs=1699999990000),
                lambda p:p.update(sourceSequence=0),lambda p:p.update(ready=False)):
            b=Widgets();b.fault=change
            with self.subTest(change=change),self.assertRaises(NativeUIError):b.io().capture()
        b=Widgets();io=b.io();b.before=lambda:setattr(b,'clock',b.clock+5.1)
        with self.assertRaises(NativeUIError):io.capture()
    def test_strict_missing_false_and_unknown_page_metadata_cannot_default_to_facts(self):
        for change in (lambda r:r.pop('canWrite'),lambda r:r.update(canWrite=1),lambda r:r.update(sceneModel=False),lambda r:r.update(inputReady=True)):
            b=Widgets();row=b.rows()[0];change(row)
            with self.subTest(change=change),self.assertRaises(NativeUIError):metadata(row)
    def test_rename_uses_only_original_dialog_fields_and_cancel_remains_normal_input(self):
        b=Widgets();ui=b.recipe();ui.input('assets.rename');ui.replace('assets.rename.path','/renamed-'+RUN+'/');ui.input('assets.rename.cancel')
        self.assertEqual('/renamed-'+RUN+'/',b.texts['assets.rename.path']);self.assertIsNone(b.dialog)
        self.assertEqual('assets.rename.cancel',b.inputs[-1]['controlId'])
    def test_changed_mapping_and_expired_reference_are_refused(self):
        b=Widgets();io=b.io();original=io.capture();b.selected='/foreign/main.gltf'
        # Selecting another mapping invalidates page-bound controls at native
        # admission. This synthetic buffer explicitly advances the token too.
        b.fault=lambda packet:packet['controls'][1].update(token='f'*32)
        with self.assertRaises(NativeUIError):io.activate('assets.filter',reference=original)
        b=Widgets();io=b.io();original=io.capture();b.sleep(5.1)
        with self.assertRaises(NativeUIError):io.activate('assets.filter',reference=original)
    def test_unowned_file_directory_or_primary_cannot_open_picker_or_select_file(self):
        b=Widgets();ui=b.recipe()
        for directory in ('/foreign','/private/feature-assets-'+RUN+'/../other'):
            with self.subTest(directory=directory),self.assertRaises(NativeUIError):ui.upload_bundle(directory,'gltf-bundle/main.gltf','/e2e-'+RUN+'/')
        with self.assertRaises(NativeUIError):ui.select_file('file:///foreign/main.gltf')
        self.assertEqual([],b.inputs)
    def test_closed_bundle_recipe_preserves_common_primary_and_companion_inputs(self):
        class Inputs(TokenAssetsUI):
            def __init__(self):self.selected=[];self.operations=[]
            def open_picker(self):self.operations.append('open')
            def navigate_files(self,path):self.operations.append(('folder',path))
            def select_file(self,path):self.selected.append(path)
            def capture(self):return None
            def file_picker(self,_value):return dict(selectedUrls=self.selected)
            def review_bundle(self,primary):self.operations.append(('primary',primary))
            def destination(self,path):self.operations.append(('destination',path))
        ui=Inputs();ui.upload_bundle(DIRECTORY,'gltf-bundle/main.gltf','/e2e-'+RUN+'/')
        self.assertEqual(['file://'+DIRECTORY+'/gltf-bundle/'+name for name in ('main.gltf','mesh/triangle.bin','textures/checker.png')],ui.selected)
        self.assertIn(('primary','main.gltf'),ui.operations);self.assertEqual(('destination','/e2e-'+RUN+'/'),ui.operations[-1])
        ui=Inputs();ui.upload_bundle(DIRECTORY,'asset-stand.fbx','/e2e-'+RUN+'/')
        self.assertEqual(['file://'+DIRECTORY+'/fbx-bundle/stand.fbx'],ui.selected)
        with self.assertRaises(NativeUIError):Inputs().upload_bundle(DIRECTORY,'asset-stand.fbx','/e2e-'+'a'*32+'/')
    def test_readonly_admission_allows_only_original_ui_observe(self):
        from appium_adapter import readonly_feature_command
        request=dict(schemaVersion=1,commandId='e'*32,action='phone-assets-ui',request=dict(schemaVersion=1,commandId='e'*32,action='observe'))
        readonly_feature_command(request)
        for inner in (request['request']|dict(action='activate'),request['request']|dict(expected=[])):
            with self.subTest(inner=inner),self.assertRaises((ValueError,NativeUIError)):readonly_feature_command(request|dict(request=inner))
    def test_actual_probe_closed_ui_grammar_deduplicates_and_keeps_missing_native_red(self):
        program=r'''const Uuid={generate:()=>"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"};
const objectKeysMatch=(v,k)=>JSON.stringify(Object.keys(v).sort())===JSON.stringify(k.sort());
let calls=[],files=[],counter=0;const Test={phoneAssetsUi:r=>{calls.push(r);return {commandId:r.commandId,performed:true};},saveObject:(v,n)=>files.push({v,n})};
SOURCE
let nonce=()=> (++counter).toString(16).padStart(32,"0");
function send(r){applyAndroidControlCommand({schemaVersion:1,commandId:r.commandId,action:"phone-assets-ui",request:r});}
let read={schemaVersion:1,commandId:nonce(),action:"observe"};send(read);send(read);
if(calls.length!==1||files[0].n!=="phone-assets-ui.json")throw Error("routing or duplicate");
for(let [controlId,action,value] of [["assets.rename.path","replace","/renamed-"+"b".repeat(32)+"/"],["assets.destination.accept","activate",null],
 ["assets-file.folder","submit",null],["assets-file.primary","select-index",2],["assets-file.list","scroll","down"],["assets.delete.accept","activate",null]]){
 let commandId=nonce(),r={schemaVersion:1,commandId,action,controlId,instance:"a".repeat(32),generation:"b".repeat(32),controlToken:"c".repeat(32),sequence:1,observedElapsedMs:0};
 if(action==="replace")r.text=value;if(action==="select-index")r.index=value;if(action==="scroll")r.direction=value;
 let before=calls.length;send(r);if(calls.length!==before+1)throw Error("normal input refused "+controlId);
 for(let extra of [{expected:[]},{handler:"uploadBundle"},{sequence:true}]){send({...r,commandId:nonce(),...extra});if(calls.length!==before+1)throw Error("unknown input accepted");}
}
delete Test.phoneAssetsUi;send({...read,commandId:nonce()});if(files.at(-1).v.available!==false)throw Error("missing native source green");
'''.replace('SOURCE',probe_source())
        result=subprocess.run(['node','-e',program],capture_output=True,text=True,timeout=5)
        self.assertEqual(0,result.returncode,result.stderr)


if __name__=='__main__':unittest.main()
