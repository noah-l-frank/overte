"""Actual private Pico transport/factory, native source and explicit OS seams."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import json
import subprocess
import sys
import unittest
from unittest.mock import patch
import test_native_execution_binding as original
ROOT=Path(__file__).resolve().parents[5]
sys.path.insert(0,str(ROOT/'tests/device'))
from self_tests.test_pico_snapshot_exports import PicoSnapshotExportsTests,PicoSnapshotExportControlTests,packet
from self_tests.test_pico_snapshot_saved_files import PicoSnapshotSavedFilesTests
from adapters.pico4.snapshot_exports import PicoSnapshotExportIO
from adapters.normal_ui import NativeUIError


class PicoSnapshotExportFactoryTests(unittest.TestCase):
    def fixture(self):
        owner=original.NativeExecutionBindingTest();owner.setUp();self.addCleanup(owner.doCleanups);owner.snapshot_setup()
        return owner,owner.instance(),owner.fake
    def test_actual_factory_uses_parent_lock_last_admission_then_original_writer_without_aliases(self):
        fixture,adapter,native=self.fixture();seen=[];current={};lock=adapter._script_journey()._lock(native.target)
        def reject(command):seen.append(command);raise NativeUIError('Explicit parent source refusal')
        source=adapter._snapshot_exports(native.target,read_only=False,before_send=reject,source_lock=lock)
        self.assertIs(source.lock,lock);self.assertIsInstance(source.io,PicoSnapshotExportIO)
        with patch.object(native,'write_debug_app_file',side_effect=AssertionError('Write after parent rejection')):
            with self.assertRaises(NativeUIError):source.request('a'*32,'retire-copies')
        self.assertEqual(1,len(seen));self.assertEqual('retire-copies',seen[0]['operation'])
        source=adapter._snapshot_exports(native.target,source_lock=lock)
        def write(target,package,path,raw):
            self.assertEqual((native.target,'org.overte.pico','files/overte-e2e/android-control-command.json'),(target,package,path))
            value=packet(json.loads(raw),epoch=native.epoch_milliseconds(native.target));value['processId']=int(native.identity.split(':')[0]);current.update(value)
        def read(target,package,path,**options):
            self.assertEqual('files/overte-e2e/feature-pico-snapshot-exports.json',path);self.assertEqual({'attempts':1},options)
            return json.dumps(current)
        # The JNI endpoint packet is an explicit synthetic transport seam;
        # native gate/Qt/JNI bodies have separate actual compiler ownership.
        with patch.object(native,'write_debug_app_file',side_effect=write),patch.object(native,'read_debug_app_file',side_effect=read):
            value=source.request('a'*32);self.assertEqual(current,value)
        native.digest='f'*64
        with patch.object(native,'write_debug_app_file',side_effect=AssertionError('Changed candidate writer')):
            with self.assertRaises((ValueError,RuntimeError)):source.request('a'*32)
        self.assertFalse(any(cap.startswith('feature.snapshots.') for cap in adapter.capabilities(native.target)))
    def test_final_original_sdk_guard_with_frozen_native_clock_cannot_publish_late_control(self):
        fixture,adapter,native=self.fixture();source=adapter._snapshot_exports(native.target);clock=[1.]
        source.monotonic=lambda:clock[0];guard=source.io.guard
        def slow():guard();clock[0]+=2
        with patch.object(source.io,'guard',side_effect=slow),patch.object(native,'write_debug_app_file',side_effect=AssertionError('Late writer')):
            with self.assertRaises(NativeUIError):source.request('a'*32)
        self.assertIsNone(source.last)
    def test_original_probe_forwards_whole_raw_dto_once_and_rejects_desired_results_or_open_shapes(self):
        source=(ROOT/'tests/device/probe/overte_e2e_probe.js').read_text();marker=source.index('&& command.action === "feature-pico-snapshot-exports"')
        start=source.rfind('        if (command &&',0,marker);end=source.index('        if (command &&',marker)
        harness=r'''
const assert=require('node:assert/strict');let lastPicoSnapshotExportsRequest='',calls=[],saved=[],actual;
const objectKeysMatch=(v,k)=>Object.keys(v).sort().join('|')===k.sort().join('|');
const Test={featurePicoSnapshotExports:command=>{calls.push(command);return actual;},saveObject:(value,file)=>saved.push({value,file})};
function apply(command){BODY}
const command={schemaVersion:1,commandId:'a'.repeat(32),runId:'b'.repeat(32),action:'feature-pico-snapshot-exports',operation:'observe',exportRequest:'',resourceId:''};
actual={requestId:command.commandId,exportsRaw:'original Java bytes',lease:{actualNativeHandle:'original'}};
apply(command);assert.strictEqual(saved[0].value,actual);apply(command);assert.equal(calls.length,1);
assert.equal(saved[0].file,'feature-pico-snapshot-exports.json');
for(const bad of [{...command,commandId:'c'.repeat(32),expectedSaved:true},{...command,schemaVersion:true},
    {...command,commandId:'c'.repeat(32),operation:'delete-by-path'}, {...command,commandId:'c'.repeat(32),operation:'read',exportRequest:''}])apply(bad);
assert.equal(calls.length,1);actual=null;apply({...command,commandId:'c'.repeat(32)});assert.equal(saved[1].value.available,false);
'''.replace('BODY',source[start:end])
        subprocess.run(['node','-e',harness],check=True,timeout=5)


class PicoSnapshotExportNativeTests(unittest.TestCase):
    def test_actual_original_jni_lease_pointer_and_bounded_source_getter(self):
        subprocess.run([sys.executable,str(ROOT/'tests/device/contracts/snapshot/test_snapshot_exports_native.py')],check=True,timeout=90)


class PicoSnapshotExportJavaTests(unittest.TestCase):
    def test_actual_original_java_stream_history_and_destination_contracts(self):
        subprocess.run([sys.executable,str(ROOT/'tests/device/contracts/snapshot/test_snapshot_exports_java.py')],check=True,timeout=30)


if __name__=='__main__':unittest.main()
