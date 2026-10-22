"""Actual private Pico source factory; renderer and device transports are seams."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch
import test_normal_scripts as original
ROOT=Path(__file__).resolve().parents[5]
sys.path.insert(0,str(ROOT/'tests/device'))
from adapters.pico4.snapshot_originals import ACTION,FILE
from adapters.android.adapter import ANDROID_CONTROL_COMMAND
from self_tests.test_pico_snapshot_originals import SnapshotOriginalTests,Boundary,RUN


class PicoSnapshotOriginalTests(unittest.TestCase):
    def test_actual_factory_binds_private_command_channel_process_candidate_and_exact_source_lock(self):
        fixture=original.PicoNormalScriptsTests();fixture.setUp();self.addCleanup(fixture.doCleanups)
        adapter,native=fixture.instance,fixture.native;boundary=Boundary()
        original_write=native.write_debug_app_file;original_read=native.read_debug_app_file
        def write(target,package,path,raw):
            command=json.loads(raw)
            if command.get('action')!=ACTION:return original_write(target,package,path,raw)
            self.assertEqual(ANDROID_CONTROL_COMMAND,path);self.assertEqual('org.overte.pico',package)
            boundary.epoch=native.epoch_milliseconds(target);boundary.send(command)
            boundary.value['pid']=int(native.identity.split(':')[0])
        def read(target,package,path,**options):
            if path!='files/overte-e2e/'+FILE:return original_read(target,package,path,**options)
            self.assertEqual({'attempts':1},options);return boundary.read()
        with patch.object(native,'write_debug_app_file',side_effect=write),patch.object(native,'read_debug_app_file',side_effect=read):
            lock=adapter._script_journey()._lock(native.target);reader=adapter._snapshot_native_originals(native.target,source_lock=lock)
            self.assertIs(lock,reader.lock)
            with lock.held():packet=reader.capture(RUN,'arm')
            self.assertEqual([],packet['requests']);self.assertEqual([],native.inputs)
            native.digest='f'*64
            with self.assertRaises((ValueError,RuntimeError)):reader.capture(RUN)
            self.assertEqual(1,len(boundary.commands))
            self.assertFalse(any(cap.startswith('feature.snapshots.') for cap in adapter.capabilities(native.target)))
    def test_original_probe_forwards_actual_dto_and_deduplicates_closed_commands(self):
        source=(ROOT/'tests/device/probe/overte_e2e_probe.js').read_text();action=source.index('command.action === "'+ACTION+'"')
        start=source.rfind('        if (command &&',0,action);end=source.index('        if (command &&',action)
        harness=r'''
const assert=require('node:assert/strict');let lastSnapshotCaptureRequest='',saved=[],calls=[],result;
const objectKeysMatch=(value,keys)=>Object.keys(value).sort().join('|')===keys.sort().join('|');
const Test={featureSnapshotCaptureOriginals:value=>{calls.push(value);return result;},saveObject:(value,file)=>saved.push({value,file})};
function apply(command){BODY}
const command={schemaVersion:1,commandId:'a'.repeat(32),runId:'b'.repeat(32),action:'feature-snapshot-capture-originals',operation:'arm'};
result={...command,nativeOriginal:true};apply(command);assert.strictEqual(saved[0].value,result);apply(command);assert.equal(calls.length,1);
for(const bad of [{...command,commandId:'c'.repeat(32),expectedPhase:'complete'},{...command,operation:'cancel'},{...command,schemaVersion:true}])apply(bad);
assert.equal(calls.length,1);result=null;apply({...command,commandId:'c'.repeat(32),operation:'read'});
assert.equal(saved[1].value.available,false);assert.equal(saved[1].file,'feature-snapshot-capture-originals.json');
'''.replace('BODY',source[start:end])
        subprocess.run(['node','-e',harness],check=True,timeout=5)
    def test_actual_original_snapshot_and_whole_pico_nonpico_getter_bodies(self):
        subprocess.run([sys.executable,str(ROOT/'tests/device/contracts/snapshot/test_snapshot_originals.py')],check=True,timeout=90)


if __name__=='__main__':unittest.main()
