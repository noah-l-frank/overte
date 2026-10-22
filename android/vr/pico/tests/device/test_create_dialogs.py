"""Original native Create modal/Qt resource joins on substituted boundaries."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[5]/'tests/device'))
from adapters.normal_ui import NativeUIError
from adapters.pico4.create_dialogs import NativeCreateDialogs,active,continuity,validate,ui_bindings,joined,FILE,ACTION
from self_tests.test_native_feature_observation import probe_source


def frame(request='a'*32,sequence=1):
    return dict(schemaVersion=1,requestId=request,instance='a'*32,sequence=sequence,processId=123,
        requestedEpochMs=20000,capturedEpochMs=20000,source=dict(createDialogSourceVersion=1,instance='b'*32,
        sequence=sequence,elapsedMs=sequence*100,complete=True,dialogs=[dict(id='c'*32,rootId='d'*32,listenerId='e'*32,
            contextId='f'*32,windowId='1'*32,role='import',componentSource='file:///original/dialogs/TabletFileDialog.qml',
            registeredEpochMs=10000,enteredEpochMs=0,returnedEpochMs=0,pending=True,dispatches=0,
            listenerAlive=True,rootAlive=True,contextAlive=True,windowAlive=True)]))


def bound(value):
    row=value['source']['dialogs'][0]
    return dict(bindingVersion=1,sourceInstance=value['source']['instance'],dialogId=row['id'],
        **{k:row[k] for k in ('rootId','listenerId','contextId','windowId','role')})


class Boundary:
    def __init__(self):self.clock=0.;self.sequence=0;self.value=frame();self.raw='';self.commands=[];self.mutate=None;self.guard_ok=True
    def send(self,command):
        self.commands.append(deepcopy(command));self.sequence+=1;value=deepcopy(self.value)
        value.update(requestId=command['commandId'],sequence=self.sequence);value['source'].update(sequence=self.sequence,elapsedMs=round(self.clock*1000))
        if self.mutate:self.mutate(value)
        self.raw=json.dumps(value,indent=2)+'\n'
    def sleep(self,value):self.clock+=value
    def reader(self):return NativeCreateDialogs(self.send,lambda:self.raw,lambda:20000,lambda:self.guard_ok,123,
        monotonic=lambda:self.clock,sleep=self.sleep)


class CreateDialogTests(unittest.TestCase):
    def test_original_queued_or_running_delivery_and_retained_context_are_resources(self):
        boundary=Boundary();reader=boundary.reader();first=reader.read();descriptor=bound(first)
        self.assertEqual(boundary.raw,reader.last_raw);self.assertEqual(hashlib.sha256(boundary.raw.encode()).hexdigest(),reader.last_sha256)
        row=boundary.value['source']['dialogs'][0];row.update(listenerAlive=False,rootAlive=False,contextAlive=False)
        self.assertEqual(1,len(active(reader.read()))) # Native delivery still pending despite dead views/listener.
        row.update(enteredEpochMs=18000,dispatches=1)
        self.assertEqual(1,len(active(reader.read())))
        row.update(returnedEpochMs=19000,dispatches=0,pending=False)
        released=reader.read();self.assertEqual([],active(released));self.assertEqual(row,joined(descriptor,released))
        retained=deepcopy(released);retained['source']['dialogs'][0]['contextAlive']=True
        self.assertEqual(1,len(active(retained))) # Root/listener absence never implies internal Qt context death.
        self.assertTrue(all(c['action']==ACTION and set(c)=={'schemaVersion','commandId','action'} for c in boundary.commands))

    def test_v2_response_hash_is_original_immutable_and_required_only_after_response(self):
        before=frame();before['source']['createDialogSourceVersion']=2;row=before['source']['dialogs'][0];row['responseSha256']=None
        validate(before,before['requestId'],123,20000)
        after=deepcopy(before);after['sequence']=2;after['source'].update(sequence=2,elapsedMs=200)
        after['source']['dialogs'][0].update(enteredEpochMs=18000,returnedEpochMs=19000,pending=False,responseSha256='1'*64)
        validate(after,after['requestId'],123,20000);continuity(before,after)
        for change in (lambda p:p['source']['dialogs'][0].update(responseSha256=None),
                lambda p:p['source']['dialogs'][0].update(responseSha256='2'*64)):
            value=deepcopy(after);value['sequence']=3;value['source'].update(sequence=3,elapsedMs=300);change(value)
            with self.assertRaises(NativeUIError):validate(value,value['requestId'],123,20000);continuity(after,value)
        row['responseSha256']='1'*64
        with self.assertRaises(NativeUIError):validate(before,before['requestId'],123,20000)

    def test_v3_original_browse_read_is_time_bound_and_never_retimed_or_replaced(self):
        from test_create_browse_setting import raw
        before=frame();before['source']['createDialogSourceVersion']=3
        row=before['source']['dialogs'][0];row.update(responseSha256=None,browseSettingRead=dict(
            before=dict(capturedEpochMs=8000,raw=raw()),after=dict(capturedEpochMs=9000,raw=raw())))
        validate(before,before['requestId'],123,20000)
        for change in (lambda p:p['source']['dialogs'][0]['browseSettingRead']['after'].update(capturedEpochMs=11000),
                lambda p:p['source']['dialogs'][0]['browseSettingRead']['before'].update(raw=raw('/foreign/value')),
                lambda p:p['source']['dialogs'][0].update(browseSettingRead=None)):
            value=deepcopy(before);value['sequence']=2;value['source'].update(sequence=2,elapsedMs=200);change(value)
            with self.assertRaises(NativeUIError):validate(value,value['requestId'],123,20000);continuity(before,value)

    def test_original_ui_pointer_binding_requires_same_inventory_role_and_native_source(self):
        original=frame();native=bound(original)
        inventory=dict(inventoryVersion=1,instance='2'*32,sequence=8,complete=True,retiredRoots=[],roots=[dict(id='3'*32,
            profile='create-import-json-v1',visible=True,inCurrentTree=True,closing=False,requestId='',
            componentSource='file:///original/dialogs/TabletFileDialog.qml')])
        binding=dict(bindingVersion=1,inventoryInstance='2'*32,inventorySequence=8,complete=True,
            bindings=[dict(uiRootId='3'*32,native=native)])
        self.assertEqual(binding,ui_bindings(binding,inventory));self.assertEqual(original['source']['dialogs'][0],joined(native,original))
        for change in (lambda p:p.update(inventorySequence=7),lambda p:p.update(bindings=[]),
                lambda p:p['bindings'][0].update(uiRootId='4'*32),lambda p:p['bindings'][0]['native'].update(role='export')):
            value=deepcopy(binding);change(value)
            with self.subTest(change=change),self.assertRaises(NativeUIError):ui_bindings(value,inventory)
        for key in ('sourceInstance','rootId','listenerId','contextId','windowId','dialogId'):
            value=deepcopy(native);value[key]='5'*32
            with self.subTest(key=key),self.assertRaises(NativeUIError):joined(value,original)

    def test_lost_originals_retiming_weak_resurrection_or_replaced_sources_fail(self):
        first=frame();first['source']['dialogs'][0]['listenerAlive']=False
        changes=[lambda p:p['source'].update(dialogs=[]),lambda p:p['source'].update(instance='0'*32),
            lambda p:p['source'].update(sequence=1),lambda p:p['source'].update(elapsedMs=0),
            lambda p:p['source']['dialogs'][0].update(registeredEpochMs=11000),
            lambda p:p['source']['dialogs'][0].update(listenerAlive=True),
            lambda p:p['source']['dialogs'][0].update(contextId='4'*32)]
        for change in changes:
            later=deepcopy(first);later['sequence']=2;later['source'].update(sequence=2,elapsedMs=200);change(later)
            with self.subTest(change=change),self.assertRaises(NativeUIError):
                validate(later,later['requestId'],123,20000);continuity(first,later)

    def test_frozen_nonce_wrong_process_unknown_component_or_impossible_delivery_never_advances(self):
        changes=[lambda p:p.update(processId=124),lambda p:p.update(requestId='0'*32),
            lambda p:p.update(capturedEpochMs=10000),lambda p:p['source'].update(complete=False),
            lambda p:p['source']['dialogs'][0].update(componentSource='file:///original/dialogs/Foreign.qml'),
            lambda p:p['source']['dialogs'][0].update(componentSource='file:///original/dialogs/TabletFileDialog.qml?expected=true'),
            lambda p:p['source']['dialogs'][0].update(pending=False),lambda p:p['source']['dialogs'][0].update(dispatches=1),
            lambda p:p['source']['dialogs'][0].update(returnedEpochMs=18000)]
        for change in changes:
            boundary=Boundary();boundary.mutate=change
            with self.subTest(change=change),self.assertRaises(NativeUIError):boundary.reader().read()

    def test_bound_pico_factory_retains_candidate_process_and_original_bytes(self):
        import test_normal_scripts as sources
        fixture=sources.PicoNormalScriptsTests();fixture.setUp();self.addCleanup(fixture.doCleanups)
        native=fixture.native;boundary=Boundary();write_original=native.write_debug_app_file;read_original=native.read_debug_app_file
        def write(target,package,path,raw):
            command=json.loads(raw)
            if command['action']==ACTION:
                boundary.send(command);value=json.loads(boundary.raw);epoch=native.epoch_milliseconds(target)
                value.update(requestedEpochMs=epoch,capturedEpochMs=epoch);boundary.raw=json.dumps(value)+'\n'
            else:return write_original(target,package,path,raw)
        def read(target,package,path,**kwargs):
            if path.endswith('/'+FILE):self.assertEqual({'attempts':1},kwargs);return boundary.raw
            return read_original(target,package,path,**kwargs)
        with patch.object(native,'write_debug_app_file',side_effect=write),patch.object(native,'read_debug_app_file',side_effect=read):
            observer=fixture.instance._create_dialog_observer(native.target);value=observer.read()
            self.assertEqual(boundary.raw,observer.last_raw);self.assertTrue(active(value));native.identity='124:replacement'
            with self.assertRaises(NativeUIError):observer.read()
            self.assertEqual(1,len(boundary.commands))

    def test_closed_original_probe_command_only_forwards_native_result(self):
        program='''const assert=require('assert');let calls=[],saved=[];
const Uuid={generate:()=>'{aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa}'};
const Test={featureCreateDialogs:id=>{calls.push(id);return {requestId:id,source:{original:'native-modal'}};},saveObject:(v,n)=>saved.push({v,n})};
function objectKeysMatch(v,k){return JSON.stringify(Object.keys(v).sort())===JSON.stringify(k.sort());}
'''+probe_source()+'''
let command={schemaVersion:1,commandId:'a'.repeat(32),action:'feature-create-dialogs-observe'};
applyAndroidControlCommand(command);assert.equal(calls.length,1);assert.equal(saved[0].n,'feature-create-dialogs.json');
assert.deepStrictEqual(saved[0].v.source,{original:'native-modal'});applyAndroidControlCommand(command);assert.equal(calls.length,1);
applyAndroidControlCommand({...command,commandId:'b'.repeat(32),expected:[]});assert.equal(calls.length,1);
applyAndroidControlCommand({...command,commandId:'ios-'+'c'.repeat(32)});assert.equal(calls.length,1);
'''
        subprocess.run(['node','-e',program],check=True,timeout=5)


if __name__=='__main__':unittest.main()
