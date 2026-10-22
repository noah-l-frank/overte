"""Original Create file-role transport/owner checks on substituted native files."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[5]/'tests/device'))
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.pico4.create_files import NativeCreateFiles, OwnedCreateFiles, validate_command, ROLE, NAMES
from self_tests.test_native_script_files import BINDING, RUN
from self_tests.test_native_feature_observation import probe_source

TICKET='b'*32
URL='http://controlled.test/feature-fixture/v1/runs/'+RUN+'/'


class NativeBoundary:
    def __init__(self, path):
        self.path, self.root = path, path/('feature-create-'+RUN+'-'+TICKET)
        self.commands, self.sample = [], None
        self.clock, self.sequence = 0., 0
        self.owner, self.fault, self.mutate = None, '', None

    def send(self, command):
        validate_command(command);self.commands.append(deepcopy(command));self.sequence+=1
        operation=command['operation']
        if self.owner not in (None, command['ownerToken']):source={}
        elif operation=='stage':
            self.owner=command['ownerToken']
            if self.fault!='ack-only':
                self.root.mkdir(mode=0o700)
                for name,encoded in command['files'].items():
                    (self.root/name).write_bytes(base64.b64decode(encoded,validate=True));(self.root/name).chmod(0o600)
            source={'performed':True}
            if self.fault=='lost-stage':raise NativeUIError('synthetic uncertain native result')
        elif operation=='release':
            if self.fault!='ignored-release' and self.root.exists():
                for name in NAMES:(self.root/name).unlink(missing_ok=True)
                self.root.rmdir()
            source={'performed':True}
        elif operation=='locate':source=dict(locationVersion=1,exists=self.root.exists(),directory=self.root.as_uri())
        elif not self.root.exists():source=dict(exists=False,files=[])
        else:
            rows=[]
            for name in NAMES:
                path=self.root/name
                if not path.exists():rows.append(dict(name=name,exists=False));continue
                raw=path.read_bytes();info=path.stat()
                def clock(value):return str(value//1000000000)+'.'+str(value%1000000000).zfill(9)
                rows.append(dict(name=name,exists=True,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),
                    base64=base64.b64encode(raw).decode(),device=str(info.st_dev),inode=str(info.st_ino),mode=info.st_mode&0o777,
                    modified=clock(info.st_mtime_ns),changed=clock(info.st_ctime_ns)))
            source=dict(exists=True,directory=self.root.as_uri(),files=rows)
        self.sample=dict(schemaVersion=1,requestId=command['commandId'],instance='d'*32,sequence=self.sequence,
            requestedEpochMs=20000,capturedEpochMs=20000,processId=31,runId=command['runId'],ticket=TICKET,
            sourceRole=ROLE,operation=operation,source=source)
        if self.mutate:self.mutate(self.sample)

    def native(self):
        return NativeCreateFiles(self.send,lambda:json.dumps(self.sample),lambda:20000,lambda:True,31,
            ticket=TICKET,monotonic=lambda:self.clock,sleep=self.sleep)
    def sleep(self,value):self.clock+=value


class CreateFilesTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.path=Path(temporary.name);self.path.chmod(0o700)
        self.boundary=NativeBoundary(self.path);self.store=PrivateFeatureState(self.path/'owner.json')
        self.files=OwnedCreateFiles(self.boundary.native(),self.store,BINDING)

    def reserve_stage(self):
        self.files.reserve(RUN,URL)
        return self.files.stage()

    def test_original_input_and_product_output_are_distinct_actual_files(self):
        observed=self.reserve_stage();state=self.store.read()
        self.assertTrue(state['stageAttempted']);self.assertTrue(observed['files'][0]['exists'])
        self.assertFalse(observed['files'][1]['exists']);self.assertFalse((self.boundary.root/'export.json').exists())
        original=b'{"DataVersion":0,"Entities":[{"name":"actual-output"}]}\n'
        (self.boundary.root/'export.json').write_bytes(original)
        actual=self.files.exported()
        self.assertEqual(original,base64.b64decode(actual['base64'],validate=True))
        self.assertEqual(hashlib.sha256(original).hexdigest(),self.store.read()['exportSha256'])
        self.assertNotEqual(actual['inode'],observed['files'][0]['inode'])
        self.files.release();self.assertFalse(self.boundary.root.exists());self.assertIsNone(self.store.read())

    def test_ack_only_stage_cannot_prove_original_input_and_stage_is_not_replayed(self):
        self.boundary.fault='ack-only'
        with self.assertRaises(NativeUIError):self.reserve_stage()
        with self.assertRaises(NativeUIError):self.files.stage()
        self.assertEqual(1,sum(row['operation']=='stage' for row in self.boundary.commands))
        self.assertTrue(self.store.read()['stageAttempted'])

    def test_uncertain_stage_recovers_only_by_independent_original_read(self):
        self.boundary.fault='lost-stage'
        with self.assertRaises(NativeUIError):self.reserve_stage()
        with self.assertRaises(NativeUIError):self.files.stage()
        self.boundary.fault='';observed=self.files.verify()
        self.assertTrue(observed['files'][0]['exists'])
        self.files.release();self.assertIsNone(self.store.read())
        self.assertEqual(1,sum(row['operation']=='stage' for row in self.boundary.commands))

    def test_unknown_changed_or_ignored_export_release_preserves_owner(self):
        self.reserve_stage();path=self.boundary.root/'export.json';path.write_bytes(b'original-product-output')
        before=len(self.boundary.commands)
        with self.assertRaises(NativeUIError):self.files.release()
        self.assertFalse(any(row['operation']=='release' for row in self.boundary.commands[before:]))
        self.files.exported();path.write_bytes(b'changed-product-output')
        with self.assertRaises(NativeUIError):self.files.release()
        path.write_bytes(b'original-product-output');self.boundary.fault='ignored-release'
        with self.assertRaises(NativeUIError):self.files.release()
        self.assertIsNotNone(self.store.read());self.assertTrue(path.exists())
        self.boundary.fault='';self.files.release()

    def test_foreign_role_ticket_process_nonce_clocks_or_inode_metadata_fail(self):
        self.reserve_stage()
        changes=[lambda p:p.update(sourceRole='scripts'),lambda p:p.update(ticket='f'*32),
            lambda p:p.update(processId=32),lambda p:p.update(requestId='f'*32),
            lambda p:p.update(capturedEpochMs=10000),lambda p:p.update(sequence=1),
            lambda p:p['source']['files'][0].update(inode=123),
            lambda p:p['source']['files'][0].update(mode=420),
            lambda p:p['source']['files'][0].update(modified='retimed'),
            lambda p:p['source']['files'][0].update(sha256='0'*64)]
        for change in changes:
            self.boundary.mutate=change
            with self.subTest(change=change),self.assertRaises(NativeUIError):self.files.verify()
            self.assertIsNone(self.files.native.last_packet);self.assertIsNotNone(self.store.read())

    def test_original_role_dispatch_preserves_native_bytes_and_script_role_stays_closed(self):
        program='''const assert=require('assert');let calls=[],saved=[];
const Uuid={generate:()=>'{aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa}'};
const Test={featureScriptFiles:c=>{calls.push(c);return {requestId:c.commandId,source:{original:'actual-native-result'}};},
saveObject:(v,n)=>saved.push({v,n})};
function objectKeysMatch(v,keys){return JSON.stringify(Object.keys(v).sort())===JSON.stringify(keys.sort());}
'''+probe_source()+'''
const c={schemaVersion:1,commandId:'b'.repeat(32),action:'feature-script-files',sourceRole:'create-json-v1',
operation:'observe',runId:'a'.repeat(32),ticket:'c'.repeat(32),ownerToken:'d'.repeat(64)};
applyAndroidControlCommand(c);applyAndroidControlCommand(c);
assert.equal(calls.length,1);assert.equal(saved[0].n,'feature-create-files.json');
assert.deepEqual(saved[0].v.source,{original:'actual-native-result'});
for(const changed of [{sourceRole:'script'}, {ticket:undefined}, {expected:'exported'}, {schemaVersion:true}]){
applyAndroidControlCommand({...c,...changed,commandId:'e'.repeat(32)});}
assert.equal(calls.length,1);
'''
        result=subprocess.run(['node','-e',program],capture_output=True,text=True,timeout=10)
        self.assertEqual(0,result.returncode,result.stderr)


if __name__=='__main__':unittest.main()
