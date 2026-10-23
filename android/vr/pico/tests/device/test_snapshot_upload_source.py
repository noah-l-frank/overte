"""Original native upload source, real Pico factory and explicit IO seams."""
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
from self_tests.test_pico_snapshot_upload_source import SnapshotUploadSourceTests,packet
from adapters.normal_ui import NativeUIError
from adapters.pico4.snapshot_upload_source import FILE


class SnapshotUploadFactoryTests(unittest.TestCase):
    def fixture(self):
        fixture=original.NativeExecutionBindingTest();fixture.setUp();self.addCleanup(fixture.doCleanups);fixture.snapshot_setup()
        return fixture,fixture.instance(),fixture.fake
    def test_actual_factory_same_parent_lock_current_candidate_and_ordinary_foreground_guards(self):
        fixture,adapter,native=self.fixture();lock=adapter._script_journey()._lock(native.target);reader=adapter._snapshot_upload_source(native.target,source_lock=lock)
        self.assertIs(reader.lock,lock);current={};sent=[]
        def write(target,package,path,raw):
            self.assertEqual((native.target,'org.overte.pico','files/overte-e2e/android-control-command.json'),(target,package,path))
            request=json.loads(raw);sent.append(request);value=packet(request,len(sent),native.epoch_milliseconds(native.target));value['processId']=int(native.identity.split(':')[0]);current.update(value)
        def read(target,package,path,**options):
            self.assertEqual((native.target,'org.overte.pico','files/overte-e2e/'+FILE),(target,package,path));self.assertEqual(dict(attempts=1),options);return json.dumps(current)
        with patch.object(native,'write_debug_app_file',side_effect=write),patch.object(native,'read_debug_app_file',side_effect=read):
            value=reader.read('b'*32);self.assertEqual(current,value)
            native.digest='f'*64
            with self.assertRaises((ValueError,RuntimeError)):reader.read('b'*32)
        self.assertEqual(1,len(sent));self.assertEqual({'schemaVersion','commandId','action','runId'},set(sent[0]))
        self.assertFalse(any(cap.startswith('feature.snapshots.') for cap in adapter.capabilities(native.target)))
    def test_original_probe_publishes_whole_actual_dto_once_and_rejects_effect_requests(self):
        source=(ROOT/'tests/device/probe/overte_e2e_probe.js').read_text();marker=source.index('&& command.action === "feature-pico-snapshot-upload"')
        start=source.rfind('        if (command &&',0,marker);end=source.index('        if (command &&',marker)
        harness=r'''
const assert=require('node:assert/strict');let lastPicoSnapshotUploadRequest='',calls=[],saved=[],actual;
const objectKeysMatch=(v,k)=>Object.keys(v).sort().join('|')===k.sort().join('|');
const Test={featurePicoSnapshotUpload:command=>{calls.push(command);return actual;},saveObject:(value,file)=>saved.push({value,file})};
function apply(command){BODY}
const command={schemaVersion:1,commandId:'a'.repeat(32),runId:'b'.repeat(32),action:'feature-pico-snapshot-upload'};
actual={requestId:command.commandId,source:{originalFile:'actual FD',actualReply:'retained bytes'}};
apply(command);assert.strictEqual(saved[0].value,actual);apply(command);assert.equal(calls.length,1);
assert.equal(saved[0].file,'feature-pico-snapshot-upload.json');
for(const bad of [{...command,commandId:'c'.repeat(32),expectedUploaded:true},{...command,schemaVersion:true},{...command,commandId:'c'.repeat(32),url:'https://foreign.invalid'}])apply(bad);
assert.equal(calls.length,1);actual=null;apply({...command,commandId:'c'.repeat(32)});assert.equal(saved[1].value.available,false);
'''.replace('BODY',source[start:end])
        subprocess.run(['node','-e',harness],check=True,timeout=5)


class SnapshotUploadNativeTests(unittest.TestCase):
    def test_actual_original_fd_read_lifetime_uploader_and_bounded_tsi_source(self):
        subprocess.run([sys.executable,str(ROOT/'tests/device/contracts/snapshot/test_snapshot_upload_native.py')],check=True,timeout=90)


if __name__=='__main__':unittest.main()
