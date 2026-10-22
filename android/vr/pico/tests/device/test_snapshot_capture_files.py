"""Original native file/FD closure and actual private factory admission."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import subprocess
import json
import sys
import unittest
from unittest.mock import patch
import test_native_execution_binding as original
ROOT=Path(__file__).resolve().parents[5]
sys.path.insert(0,str(ROOT/'tests/device'))
from self_tests.test_pico_snapshot_capture_source import SnapshotCaptureSourceTests
from adapters.normal_ui import NativeUIError
from adapters.pico4.snapshot_capture_source import PicoSnapshotCaptureFileIO


class PicoSnapshotCaptureFilesTests(unittest.TestCase):
    def test_actual_factory_uses_exact_source_lock_and_final_control_callback(self):
        fixture=original.NativeExecutionBindingTest();fixture.setUp();self.addCleanup(fixture.doCleanups)
        fixture.snapshot_setup();adapter=fixture.instance();native=fixture.fake;seen=[]
        lock=adapter._script_journey()._lock(native.target)
        def reject(command):seen.append(command);raise NativeUIError('Parent intent rejected')
        reader=adapter._snapshot_capture_file_source(native.target,read_only=False,before_send=reject,source_lock=lock)
        self.assertIs(lock,reader.lock);self.assertIsInstance(reader.io,PicoSnapshotCaptureFileIO)
        with patch.object(native,'write_debug_app_file',side_effect=AssertionError('Write after rejection')):
            with self.assertRaises(NativeUIError):reader.request('a'*32,'plan',prefix='parity-'+('a'*16)+'-animated',operation_id='b'*32)
        self.assertEqual(1,len(seen));self.assertEqual('pico-snapshot-files-control',seen[0]['action'])
        native.digest='f'*64
        with self.assertRaises((ValueError,RuntimeError)):reader.request('a'*32)
        self.assertEqual(1,len(seen))
        self.assertFalse(any(cap.startswith('feature.snapshots.') for cap in adapter.capabilities(native.target)))
    def test_final_original_candidate_change_cannot_accept_an_observer_packet(self):
        fixture=original.NativeExecutionBindingTest();fixture.setUp();self.addCleanup(fixture.doCleanups)
        fixture.snapshot_setup();adapter=fixture.instance();native=fixture.fake
        reader=adapter._snapshot_capture_file_source(native.target)
        epoch=native.epoch_milliseconds(native.target);current={}
        def synthetic_reply(request):
            current.update(schemaVersion=1,requestId=request['commandId'],runId=request['runId'],instance='a'*32,sequence=1,
                processId=int(native.identity.split(':')[0]),requestedEpochMs=epoch,capturedEpochMs=epoch,accepted=True,
                source=dict(picoSnapshotCaptureFilesVersion=1,instance='b'*32,complete=True,sequence=1,capturedEpochMs=epoch,rows=[],captures=[],plans=[]))
        def changed():native.digest='f'*64;return json.dumps(current)
        # The packet is an explicit observer transport seam. No native state or
        # capture effect is claimed; the actual final candidate guard is real.
        with patch.object(reader.io,'send',side_effect=synthetic_reply),patch.object(reader.io,'raw',side_effect=changed):
            with self.assertRaises((ValueError,RuntimeError)):reader.request('a'*32)
        self.assertIsNone(reader.last)
    def test_original_probe_forwards_actual_dto_once_and_rejects_open_command_shapes(self):
        source=(ROOT/'tests/device/probe/overte_e2e_probe.js').read_text()
        marker=source.index('&& ((command.action === "pico-snapshot-files-observe"')
        start=source.rfind('        if (command &&',0,marker);end=source.index('        if (command &&',marker)
        harness=r"""
const assert=require('node:assert/strict');let lastPicoSnapshotFilesRequest='',calls=[],saved=[],actual;
const objectKeysMatch=(v,k)=>Object.keys(v).sort().join('|')===k.sort().join('|');
const Test={featurePicoSnapshotCaptureFiles:command=>{calls.push(command);return actual;},saveObject:(value,file)=>saved.push({value,file})};
function apply(command){BODY}
const command={schemaVersion:1,commandId:'a'.repeat(32),runId:'b'.repeat(32),action:'pico-snapshot-files-observe'};
actual={requestId:command.commandId,originalMarker:true};apply(command);assert.strictEqual(saved[0].value,actual);
apply(command);assert.equal(calls.length,1);assert.equal(saved[0].file,'feature-pico-snapshot-files.json');
for(const bad of [{...command,commandId:'c'.repeat(32),expectedClosed:true},{...command,schemaVersion:true}])apply(bad);
assert.equal(calls.length,1);actual=null;apply({...command,commandId:'c'.repeat(32)});
assert.equal(saved[1].value.available,false);assert.equal(calls.length,2);
""".replace('BODY',source[start:end])
        subprocess.run(['node','-e',harness],check=True,timeout=5)
    def test_original_writer_callback_and_fresh_reply_wiring_then_slow_sdk_admission_refuses_writer(self):
        fixture=original.NativeExecutionBindingTest();fixture.setUp();self.addCleanup(fixture.doCleanups)
        fixture.snapshot_setup();adapter=fixture.instance();native=fixture.fake;commands=[];current={}
        reader=adapter._snapshot_capture_file_source(native.target);epoch=native.epoch_milliseconds(native.target)
        def write(target,package,path,raw):
            self.assertEqual('files/overte-e2e/android-control-command.json',path)
            request=json.loads(raw);commands.append(request)
            current.update(schemaVersion=1,requestId=request['commandId'],runId=request['runId'],instance='a'*32,sequence=len(commands),
                processId=int(native.identity.split(':')[0]),requestedEpochMs=epoch,capturedEpochMs=epoch,accepted=True,
                source=dict(picoSnapshotCaptureFilesVersion=1,instance='b'*32,complete=True,sequence=len(commands),capturedEpochMs=epoch,rows=[],captures=[],plans=[]))
        def read(target,package,path,**options):
            self.assertEqual('files/overte-e2e/feature-pico-snapshot-files.json',path)
            self.assertEqual({'attempts':1},options);return json.dumps(current)
        # The native source payload is a synthetic transport seam; this proves
        # the unchanged actual writer/final callback path, not empty resources.
        with patch.object(native,'write_debug_app_file',side_effect=write),patch.object(native,'read_debug_app_file',side_effect=read):
            value=reader.request('a'*32);self.assertEqual(commands[0]['commandId'],value['requestId'])
        reader=adapter._snapshot_capture_file_source(native.target);host=[1.]
        reader.monotonic=lambda:host[0];reader.clock_ms=lambda:epoch;original_guard=reader.io.guard
        def late():original_guard();host[0]+=2
        with patch.object(reader.io,'guard',side_effect=late),patch.object(native,'write_debug_app_file',side_effect=AssertionError('Late publication')):
            with self.assertRaises((ValueError,RuntimeError)):reader.request('a'*32)
        self.assertEqual(1,len(commands))
    def test_original_png_and_gif_descriptor_history_and_one_send_retirement(self):
        subprocess.run([sys.executable,str(ROOT/'tests/device/contracts/snapshot/test_snapshot_capture_files_native.py')],check=True,timeout=90)


if __name__=='__main__':unittest.main()
