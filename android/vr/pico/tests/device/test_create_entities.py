"""Original Create domain-source transport and history counterexamples."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[5];sys.path.insert(0,str(ROOT/'tests/device'))
from adapters.normal_ui import NativeUIError
from adapters.pico4.create_entities import validate,continuity,ACTION,FILE
from self_tests.test_native_feature_observation import probe_source


class CreateEntitySourceTests(unittest.TestCase):
    def setUp(self):
        from test_create_picker_owner import OriginalBackend
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup);self.path=Path(temporary.name);self.path.chmod(0o700)
        self.b=OriginalBackend(self.path)
    def test_actual_source_identity_and_append_only_tracked_ids_are_required(self):
        reader=self.b.reader('entities');first=reader.read();native=deepcopy(first)
        native['sequence']+=1;native['source']['absentIds']=['33333333-3333-3333-3333-333333333333'];continuity(first,native)
        with self.assertRaises(NativeUIError):continuity(native,first|dict(sequence=3))
        for change in (lambda p:p['source'].update(domainId='44444444-4444-4444-4444-444444444444'),
                lambda p:p['source'].update(sessionId='44444444-4444-4444-4444-444444444444'),
                lambda p:p['source'].update(domainConnected=False),lambda p:p.update(instance='8'*32)):
            value=deepcopy(first);value['sequence']+=1;change(value)
            with self.subTest(change=change),self.assertRaises(NativeUIError):continuity(first,value)
        command=json.loads(reader.last_raw);self.assertEqual(first,command)
    def test_stale_wrong_process_unknown_scopes_and_nonfinite_originals_fail(self):
        first=self.b.reader('entities').read()
        for change in (lambda p:p.update(requestId='0'*32),lambda p:p.update(processId=124),lambda p:p.update(capturedEpochMs=10000),
                lambda p:p['source'].update(runId='c'*32),lambda p:p['source']['scan'].update(radiusMeters=128.0),
                lambda p:p['source']['scan'].update(center=[float('nan'),0,0]),lambda p:p['source'].update(expectedEntities=[])):
            value=deepcopy(first);change(value)
            with self.subTest(change=change),self.assertRaises(NativeUIError):validate(value,first['requestId'],123,20000,'a'*32)
    def test_bound_factory_retains_candidate_process_guard_and_original_bytes(self):
        import test_normal_scripts as sources
        fixture=sources.PicoNormalScriptsTests();fixture.setUp();self.addCleanup(fixture.doCleanups)
        native=fixture.native;original_write=native.write_debug_app_file;original_read=native.read_debug_app_file
        boundary=self.b.reader('entities');sent=[];raw=''
        def write(target,package,path,text):
            nonlocal raw
            command=json.loads(text)
            if command['action']!=ACTION:return original_write(target,package,path,text)
            sent.append(command);boundary.send(command);packet=json.loads(self.b.frames['entities']);epoch=native.epoch_milliseconds(target)
            packet.update(requestedEpochMs=epoch,capturedEpochMs=epoch);raw=json.dumps(packet,indent=2)+'\n'
        def read(target,package,path,**kwargs):
            if path.endswith('/'+FILE):self.assertEqual({'attempts':1},kwargs);return raw
            return original_read(target,package,path,**kwargs)
        with patch.object(native,'write_debug_app_file',side_effect=write),patch.object(native,'read_debug_app_file',side_effect=read):
            reader=fixture.instance._create_entity_observer(native.target,'a'*32);value=reader.read()
            self.assertEqual(raw,reader.last_raw);self.assertEqual('a'*32,value['source']['runId'])
            native.identity='124:replacement'
            with self.assertRaises(NativeUIError):reader.read()
            self.assertEqual(1,len(sent))
    def test_closed_probe_only_preserves_original_native_source(self):
        program='''const assert=require('assert');let calls=[],saved=[];
const Uuid={generate:()=>'{aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa}'};
const Test={featureCreateEntities:c=>{calls.push(c);return {requestId:c.commandId,source:{original:'actual-domain-properties'}};},saveObject:(v,n)=>saved.push({v,n})};
function objectKeysMatch(v,k){return JSON.stringify(Object.keys(v).sort())===JSON.stringify(k.sort());}
'''+probe_source()+'''
let command={schemaVersion:1,commandId:'a'.repeat(32),action:'feature-create-entities-observe',runId:'b'.repeat(32)};
applyAndroidControlCommand(command);assert.equal(calls.length,1);assert.equal(saved[0].n,'feature-create-entities.json');
assert.deepStrictEqual(saved[0].v.source,{original:'actual-domain-properties'});applyAndroidControlCommand(command);assert.equal(calls.length,1);
applyAndroidControlCommand({...command,commandId:'c'.repeat(32),expected:[]});assert.equal(calls.length,1);
applyAndroidControlCommand({...command,commandId:'ios-'+'d'.repeat(32)});assert.equal(calls.length,1);
'''
        subprocess.run(['node','-e',program],check=True,timeout=5)


if __name__=='__main__':unittest.main()
