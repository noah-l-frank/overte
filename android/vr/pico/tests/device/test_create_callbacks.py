"""Create callback-source counterexamples on substituted native boundaries."""
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
from adapters.pico4.create_callbacks import NativeCreateCallbacks,active,continuity,validate,FILE,ACTION
from adapters.normal_ui import NativeUIError
from self_tests.test_native_feature_observation import probe_source


def frame(request='a'*32,sequence=1):
    return dict(schemaVersion=1,requestId=request,instance='b'*32,sequence=sequence,processId=123,
        requestedEpochMs=20000,capturedEpochMs=20000,source=dict(createCallbackSourceVersion=1,complete=True,
        membershipRevision=1,managers=[dict(membership=dict(instance='c'*32,assigned=True,
            url='file:///original/defaultScripts.js',loadGeneration=1,assignedEpochMs=10000),
            compiled=dict(compiledSourcesVersion=1,complete=True,compilations=[dict(scriptId=17,
                resourceName='file:///original/create/edit.js',encoding='utf-16le-code-units',codeUnits=1,
                sha256=hashlib.sha256(b'x\0').hexdigest(),compiledEpochMs=12000)]),
            callbacks=dict(callbackSourceVersion=1,instance='d'*32,sequence=2,complete=True,
                proxies=[dict(id='e'*32,targetClass='WindowScriptingInterface',signal='browseChanged(QString)',
                    createdEpochMs=15000,retiredEpochMs=0,dispatches=0)],
                callbacks=[dict(id='f'*32,proxyId='e'*32,scriptId=17,connectedEpochMs=16000,disconnectedEpochMs=0)]))]))


class Boundary:
    def __init__(self):self.clock=0.;self.sequence=0;self.value=frame();self.raw='';self.commands=[];self.mutate=None;self.guard_ok=True
    def send(self,command):
        self.commands.append(deepcopy(command));self.sequence+=1
        value=deepcopy(self.value);value.update(requestId=command['commandId'],sequence=self.sequence)
        if self.mutate:self.mutate(value)
        self.raw=json.dumps(value,indent=2)+'\n'
    def sleep(self,value):self.clock+=value
    def reader(self):return NativeCreateCallbacks(self.send,lambda:self.raw,lambda:20000,lambda:self.guard_ok,123,
        monotonic=lambda:self.clock,sleep=self.sleep)


class CreateCallbackTests(unittest.TestCase):
    def test_original_connection_and_live_self_disconnected_dispatch_are_separate_resources(self):
        boundary=Boundary();reader=boundary.reader();first=reader.read()
        self.assertEqual(17,active(first)[0]['scriptId']);self.assertEqual(boundary.raw,reader.last_raw)
        self.assertEqual(hashlib.sha256(boundary.raw.encode()).hexdigest(),reader.last_sha256)
        source=boundary.value['source']['managers'][0]['callbacks'];source['sequence']=4
        source['callbacks'][0]['disconnectedEpochMs']=19000;source['proxies'][0]['dispatches']=1
        running=reader.read();self.assertEqual(1,active(running)[0]['dispatches'])
        source['sequence']=6;source['proxies'][0].update(dispatches=0,retiredEpochMs=20000)
        self.assertEqual([],active(reader.read()))
        self.assertTrue(all(set(c)=={'schemaVersion','commandId','action'} and c['action']==ACTION for c in boundary.commands))

    def test_missing_compilation_pending_dispatch_wrong_owner_and_invalid_times_fail(self):
        changes=[lambda p:p.update(processId=124),lambda p:p.update(requestId='0'*32),
            lambda p:p.update(capturedEpochMs=10000),lambda p:p.update(sequence=True),
            lambda p:p['source']['managers'][0]['compiled'].update(compilations=[]),
            lambda p:p['source']['managers'][0]['callbacks'].update(complete=False),
            lambda p:p['source']['managers'][0]['callbacks']['callbacks'][0].update(scriptId=18),
            lambda p:p['source']['managers'][0]['callbacks']['callbacks'][0].update(proxyId='1'*32),
            lambda p:p['source']['managers'][0]['callbacks']['proxies'][0].update(targetClass='foreign'),
            lambda p:p['source']['managers'][0]['callbacks']['proxies'][0].update(retiredEpochMs=18000),
            lambda p:p['source']['managers'][0]['callbacks']['callbacks'][0].update(connectedEpochMs=11000)]
        for change in changes:
            boundary=Boundary();boundary.mutate=change
            with self.subTest(change=change),self.assertRaises(NativeUIError):boundary.reader().read()

    def test_retiming_disappearance_callback_reconnection_or_source_replacement_fails_continuity(self):
        first=frame();validate(first,first['requestId'],123,20000)
        changes=[lambda p:p['source'].update(managers=[]),
            lambda p:p['source']['managers'][0]['callbacks'].update(instance='0'*32),
            lambda p:p['source']['managers'][0]['callbacks'].update(callbacks=[]),
            lambda p:p['source']['managers'][0]['callbacks']['callbacks'][0].update(connectedEpochMs=17000),
            lambda p:p['source']['managers'][0]['callbacks']['proxies'][0].update(dispatches=1),
            lambda p:p['source']['managers'][0]['compiled']['compilations'][0].update(sha256='0'*64)]
        for change in changes:
            later=deepcopy(first);later['sequence']=2;change(later)
            with self.subTest(change=change),self.assertRaises(NativeUIError):
                validate(later,later['requestId'],123,20000);continuity(first,later)
        first['source']['managers'][0]['callbacks']['callbacks'][0]['disconnectedEpochMs']=19000
        later=frame(sequence=2);later['source']['managers'][0]['callbacks']['sequence']=3
        with self.assertRaises(NativeUIError):continuity(first,later)

    def test_frozen_request_failed_guard_and_duplicate_original_json_do_not_advance(self):
        boundary=Boundary();reader=boundary.reader();original=reader.read()
        boundary.guard_ok=False
        with self.assertRaises(NativeUIError):reader.read()
        self.assertEqual(1,len(boundary.commands));self.assertEqual(original,reader.last)
        boundary.guard_ok=True;reader.send=lambda command:None
        with self.assertRaises(NativeUIError):reader.read()
        self.assertEqual(original,reader.last)
        boundary=Boundary();reader=boundary.reader();original_send=reader.send
        def duplicated(command):
            original_send(command);boundary.raw=boundary.raw.replace('"schemaVersion": 1','"schemaVersion": 1, "schemaVersion": 1',1)
        reader.send=duplicated
        with self.assertRaises(NativeUIError):reader.read()
        self.assertIsNone(reader.last)

    def test_actual_bound_pico_factory_keeps_original_transport_and_candidate_guard(self):
        import test_normal_scripts as sources
        fixture=sources.PicoNormalScriptsTests();fixture.setUp();self.addCleanup(fixture.doCleanups)
        native=fixture.native;boundary=Boundary()
        write_original=native.write_debug_app_file;read_original=native.read_debug_app_file
        def write(target,package,path,raw):
            command=json.loads(raw)
            if command['action']==ACTION:
                boundary.send(command);value=json.loads(boundary.raw)
                epoch=native.epoch_milliseconds(target);value.update(requestedEpochMs=epoch,capturedEpochMs=epoch)
                boundary.raw=json.dumps(value)+'\n'
            else:return write_original(target,package,path,raw)
        def read(target,package,path,**kwargs):
            if path.endswith('/'+FILE):
                self.assertEqual({'attempts':1},kwargs);return boundary.raw
            return read_original(target,package,path,**kwargs)
        with patch.object(native,'write_debug_app_file',side_effect=write),patch.object(native,'read_debug_app_file',side_effect=read):
            observer=fixture.instance._create_callback_observer(native.target);value=observer.read()
            self.assertEqual(17,active(value)[0]['scriptId']);self.assertEqual(boundary.raw,observer.last_raw)
            native.identity='124:replacement'
            with self.assertRaises(NativeUIError):observer.read()
            self.assertEqual(1,len(boundary.commands))

    def test_original_probe_routes_only_closed_read_command_and_preserves_source_bytes(self):
        program='''const assert=require('assert');let calls=[],saved=[];
const Uuid={generate:()=>'{aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa}'};
const Test={featureCreateCallbacks:id=>{calls.push(id);return {requestId:id,source:{original:'native'}};},saveObject:(v,n)=>saved.push({v,n})};
function objectKeysMatch(v,k){return JSON.stringify(Object.keys(v).sort())===JSON.stringify(k.sort());}
'''+probe_source()+'''
let command={schemaVersion:1,commandId:'a'.repeat(32),action:'feature-create-callbacks-observe'};
applyAndroidControlCommand(command);assert.equal(calls.length,1);assert.equal(saved[0].n,'feature-create-callbacks.json');
assert.deepStrictEqual(saved[0].v.source,{original:'native'});applyAndroidControlCommand(command);assert.equal(calls.length,1);
applyAndroidControlCommand({...command,commandId:'b'.repeat(32),expected:[]});assert.equal(calls.length,1);
applyAndroidControlCommand({...command,commandId:'ios-'+'c'.repeat(32)});assert.equal(calls.length,1);
'''
        subprocess.run(['node','-e',program],check=True,timeout=5)


if __name__=='__main__':unittest.main()
