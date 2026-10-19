"""Real local fixture files at a synthetic native seam; no client execution."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from adapters.native_account_origin import NativeAccountOrigin,OwnedAccountOrigin,command,origin_text,original_document,EMPTY
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from fixture.serve import FixtureState
from self_tests.test_native_feature_observation import probe_source

RUN='a'*32;INSTANCE='b'*32;ORIGIN='https://controlled.invalid:44321'
BINDING=dict(sourceRevision='c'*40,artifactSha256='d'*64,processIdentity='123:original',sessionId='owned-session',
             generation=1,targetFingerprint='e'*64)


class Boundary:
    """Only the explicit test seam models native operations; effects are real files."""
    def __init__(self,root):
        self.root=Path(root);self.root.mkdir(mode=0o700)
        self.path=self.root/'feature-account-origin.v1.json';self.manifest=self.root/'.feature-account-origin-owner.v1.json'
        self.clock=0.;self.sequence=0;self.commands=[];self.value=None;self.guard_ok=True;self.retired=set()
        self.fault=None;self.mutate=None;self.send_guard=None;self.issued={}
    def send(self,value):
        self.commands.append(deepcopy(value))
        if self.send_guard:self.send_guard(value)
        op=value['operation'];key=(value['runId'],value['ownerToken'])
        if self.fault=='ignore-command':return
        self.sequence+=1
        if op=='stage':
            if key in self.retired or self.path.exists() or self.manifest.exists():return self.unavailable(value)
            if self.fault!='ack-only':
                raw=original_document(value['runId'],value['origin'])
                meta=dict(schemaVersion=1,runId=value['runId'],ownerToken=value['ownerToken'],instance=value['instance'],
                          originSha256=hashlib.sha256(raw).hexdigest())
                self.manifest.write_text(json.dumps(meta,sort_keys=True,separators=(',',':'))+'\n');os.chmod(self.manifest,0o600)
                self.path.write_bytes(raw[:5] if self.fault=='partial-write' else raw);os.chmod(self.path,0o600)
                for path in (self.path,self.manifest):
                    info=path.stat();self.issued[path]=(key,info.st_dev,info.st_ino,path.read_bytes())
                if self.fault=='partial-write':return self.unavailable(value)
            source=dict(performed=True)
        else:
            raw=self.path.read_bytes() if self.path.exists() else b''
            manifest=self.manifest.read_bytes() if self.manifest.exists() else b''
            if op=='release' and self.fault!='missing-retirement':self.retired.add(key)
            for path in (self.path,self.manifest):
                if path.exists():
                    info=path.stat();actual=(key,info.st_dev,info.st_ino,path.read_bytes())
                    if actual!=self.issued.get(path):return self.unavailable(value)
            if op!='release':
                if manifest:
                    meta=json.loads(manifest)
                    if (meta['ownerToken']!=value['ownerToken'] or meta['instance']!=value['instance']
                            or raw and hashlib.sha256(raw).hexdigest()!=meta['originSha256']):return self.unavailable(value)
                elif raw:return self.unavailable(value)
            if op=='release':
                if self.fault!='keep-files':
                    self.path.unlink(missing_ok=True);self.manifest.unlink(missing_ok=True);self.issued.clear()
                source=dict(performed=True)
            else:
                source=dict(originExists=self.path.exists(),ownerExists=self.manifest.exists(),originBytes=len(raw),
                    originSha256=hashlib.sha256(raw).hexdigest(),originBase64=base64.b64encode(raw).decode(),
                    ownerBytes=len(manifest),ownerSha256=hashlib.sha256(manifest).hexdigest(),retired=key in self.retired)
        self.value=dict(originVersion=1,**{k:value[k] for k in ('commandId','instance','runId','operation')},
            processId=123,sequence=self.sequence,requestedEpochMs=20000,capturedEpochMs=20000,source=source)
        if self.mutate:self.mutate(self.value)
    def unavailable(self,value):self.value=dict(commandId=value['commandId'],available=False)
    def read(self):return json.dumps(self.value)
    def sleep(self,value):self.clock+=value


class AccountOriginTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory();self.addCleanup(self.temporary.cleanup)
        root=Path(self.temporary.name);os.chmod(root,0o700)
        self.boundary=Boundary(root/'native');self.store=PrivateFeatureState(root/'owner.json')
        self.source=NativeAccountOrigin(self.boundary.send,self.boundary.read,lambda:20000,lambda:self.boundary.guard_ok,123,INSTANCE,
            monotonic=lambda:self.boundary.clock,sleep=self.boundary.sleep)
        self.owned=OwnedAccountOrigin(self.source,self.store,BINDING)
        def persisted(_value):self.assertIsNotNone(self.store.read())
        self.boundary.send_guard=persisted

    def test_exclusive_stage_reads_original_canonical_bytes_and_observes_both_file_absences(self):
        self.assertEqual(ORIGIN,self.owned.stage(RUN,ORIGIN))
        self.assertEqual(original_document(RUN,ORIGIN),self.boundary.path.read_bytes())
        self.assertEqual(0o600,stat.S_IMODE(self.boundary.path.stat().st_mode))
        self.owned.release();self.assertFalse(self.boundary.path.exists());self.assertFalse(self.boundary.manifest.exists())
        self.assertIsNone(self.store.read());self.assertEqual(['stage','observe','release','observe'],[v['operation'] for v in self.boundary.commands])

    def test_stage_ack_without_actual_config_keeps_owner_and_fails(self):
        self.boundary.fault='ack-only'
        with self.assertRaises(NativeUIError):self.owned.stage(RUN,ORIGIN)
        self.assertIsNotNone(self.store.read());self.owned.release();self.assertIsNone(self.store.read())

    def test_ignored_stage_is_not_replayed_and_late_stage_is_retired_before_owner_deletion(self):
        self.boundary.fault='ignore-command'
        with self.assertRaises(NativeUIError):self.owned.stage(RUN,ORIGIN)
        late=deepcopy(self.boundary.commands[0]);self.assertEqual(1,len(self.boundary.commands))
        self.boundary.fault=None;self.owned.release();self.boundary.send_guard=None
        self.boundary.send(late);self.assertFalse(self.boundary.path.exists());self.assertIsNone(self.store.read())

    def test_cleanup_ack_with_retained_files_or_missing_retirement_cannot_clear_owner(self):
        self.owned.stage(RUN,ORIGIN)
        for fault in ('keep-files','missing-retirement'):
            # Each independent owned scope must start with its own real files.
            if fault=='missing-retirement':self.boundary.retired.clear()
            self.boundary.fault=fault
            with self.assertRaises(NativeUIError):self.owned.release()
            self.assertIsNotNone(self.store.read())
        self.boundary.fault=None;self.owned.release();self.assertIsNone(self.store.read())

    def test_foreign_owner_or_changed_original_bytes_are_never_adopted_or_deleted(self):
        self.owned.stage(RUN,ORIGIN);original=self.boundary.path.read_bytes()
        self.boundary.path.write_bytes(b'foreign-original')
        with self.assertRaises(NativeUIError):self.owned.release()
        self.assertEqual(b'foreign-original',self.boundary.path.read_bytes());self.assertIsNotNone(self.store.read())
        self.boundary.path.write_bytes(original)
        meta=json.loads(self.boundary.manifest.read_text());meta['ownerToken']='f'*64
        self.boundary.manifest.write_text(json.dumps(meta))
        with self.assertRaises(NativeUIError):self.owned.release()
        self.assertTrue(self.boundary.path.exists());self.assertIsNotNone(self.store.read())

    def test_partial_native_write_is_removed_only_with_actual_original_file_creation_evidence(self):
        self.boundary.fault='partial-write'
        with self.assertRaises(NativeUIError):self.owned.stage(RUN,ORIGIN)
        self.assertEqual(5,self.boundary.path.stat().st_size);self.assertIsNotNone(self.store.read())
        self.boundary.fault=None;self.owned.release()
        self.assertFalse(self.boundary.path.exists());self.assertFalse(self.boundary.manifest.exists());self.assertIsNone(self.store.read())

    def test_copied_valid_original_bytes_in_a_different_inode_cannot_be_deleted(self):
        self.owned.stage(RUN,ORIGIN);raw=self.boundary.path.read_bytes()
        descriptor=os.open(self.boundary.path,os.O_RDONLY);self.addCleanup(os.close,descriptor)
        self.boundary.path.unlink();self.boundary.path.write_bytes(raw);os.chmod(self.boundary.path,0o600)
        self.assertNotEqual(os.fstat(descriptor).st_ino,self.boundary.path.stat().st_ino)
        with self.assertRaises(NativeUIError):self.owned.release()
        self.assertEqual(raw,self.boundary.path.read_bytes());self.assertIsNotNone(self.store.read())

    def test_replaced_native_context_or_process_blocks_cleanup_without_dispatch(self):
        self.owned.stage(RUN,ORIGIN);before=len(self.boundary.commands)
        self.source.instance='f'*32
        with self.assertRaises(NativeUIError):self.owned.release()
        self.assertEqual(before,len(self.boundary.commands));self.assertIsNotNone(self.store.read())
        self.source.instance=INSTANCE;self.boundary.guard_ok=False
        with self.assertRaises(NativeUIError):self.owned.release()
        self.assertEqual(before,len(self.boundary.commands))

    def test_replaced_candidate_binding_and_second_stage_cannot_adopt_owned_scope(self):
        self.owned.stage(RUN,ORIGIN);before=len(self.boundary.commands)
        with self.assertRaises(NativeUIError):self.owned.stage(RUN,ORIGIN)
        self.owned.binding['artifactSha256']='f'*64
        with self.assertRaises(NativeUIError):self.owned.release()
        self.assertEqual(before,len(self.boundary.commands));self.assertIsNotNone(self.store.read())

    def test_controlled_origin_rejects_cleartext_credentials_paths_and_ambiguous_forms(self):
        for value in ('http://controlled.invalid','https://user:secret@host','https://@host','https://host/',
                      'https://host/path','https://host?','https://host#','https://host:','https://host:0',
                      'https://host:65536','https://HOST','https://höst','https://host\n'):
            with self.assertRaises(NativeUIError):origin_text(value)
        self.assertEqual(ORIGIN,origin_text(ORIGIN));self.assertEqual([],self.boundary.commands)

    def test_closed_native_fixture_input_rejects_desired_facts_and_foreign_epoch_scalar_types(self):
        self.owned.stage(RUN,ORIGIN)
        request=self.boundary.commands[0]
        for edit in ({'expected':True},{'schemaVersion':True},{'ownerToken':'foreign'},{'operation':'set-auth-url'}):
            with self.assertRaises(NativeUIError):command(request|edit)
        for edit in ({'processId':124},{'instance':'f'*32},{'sequence':0},{'capturedEpochMs':18499}):
            self.boundary.mutate=lambda value:value.update(edit)
            with self.assertRaises(NativeUIError):self.source.request(self.store.read()['data'],'observe')

    def test_actual_inventory_requires_original_hash_bytes_and_real_boolean_types(self):
        self.owned.stage(RUN,ORIGIN)
        for edit in ({'originExists':1},{'ownerExists':0},{'originBytes':0},{'originSha256':EMPTY},{'ownerSha256':EMPTY},{'originBase64':'Zm9yZWlnbg=='}):
            self.boundary.mutate=lambda value:value['source'].update(edit)
            with self.assertRaises(NativeUIError):self.source.request(self.store.read()['data'],'observe')

    def test_native_epoch_regression_between_separate_ios_acquisitions_is_rejected(self):
        self.source.ios=True;self.owned.stage(RUN,ORIGIN)
        self.boundary.mutate=lambda value:value.update(requestedEpochMs=19999,capturedEpochMs=19999)
        with self.assertRaises(NativeUIError):self.source.request(self.store.read()['data'],'observe')
        self.assertIsNotNone(self.store.read())

    def test_public_native_inventory_does_not_echo_private_ownership_token(self):
        self.owned.stage(RUN,ORIGIN);secret=self.store.read()['data']['ownerToken']
        self.assertNotIn(secret,json.dumps(self.boundary.value));self.assertNotIn('ownerToken',json.dumps(self.boundary.value))

    def test_partial_receipt_and_transport_deadline_never_repeat_the_stage(self):
        original=self.source.original;reads=[]
        def partial():reads.append(1);return '{' if len(reads)==1 else original()
        self.source.original=partial;self.owned.stage(RUN,ORIGIN)
        self.assertEqual(1,sum(value['operation']=='stage' for value in self.boundary.commands))
        def late():self.boundary.clock+=5;return original()
        self.source.original=late
        with self.assertRaises(NativeUIError):self.owned.release()
        self.assertIsNotNone(self.store.read())

    def test_ios_fixture_keeps_closed_scope_and_original_native_clock(self):
        self.source.ios=True;self.source.clock_ms=lambda:9000000
        self.owned.stage(RUN,ORIGIN);fixture=FixtureState()
        for value in self.boundary.commands:self.assertEqual(value,fixture.set_client_command(value))
        self.assertEqual(20000,self.boundary.value['capturedEpochMs']);self.owned.release()

    def test_actual_javascript_dispatch_deduplicates_stage_and_preserves_original_inventory(self):
        program='''
let calls=0,files=[];
const Uuid={generate:()=>"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"};
const objectKeysMatch=(v,keys)=>JSON.stringify(Object.keys(v).sort())===JSON.stringify(keys.sort());
const Test={featureAccountOrigin:c=>{calls++;return {originVersion:1,commandId:c.commandId,source:{actualBytes:77}};},
 saveObject:(v,name)=>files.push({v,name})};
SOURCE
const command={schemaVersion:1,commandId:"a".repeat(32),action:"feature-account-origin",operation:"stage",
 runId:"b".repeat(32),ownerToken:"c".repeat(64),instance:"d".repeat(32),origin:"https://controlled.invalid"};
applyAndroidControlCommand(command);applyAndroidControlCommand(command);
if(calls!==1||files[0].v.source.actualBytes!==77||files[0].name!=="feature-account-origin-result.json")throw Error("original stage");
applyClientCommand({...command,commandId:"e".repeat(32),expected:true});if(calls!==1)throw Error("desired outcome accepted");
delete Test.featureAccountOrigin;applyClientCommand({...command,commandId:"ios-"+"f".repeat(32)});
if(files[1].v.available!==false)throw Error("missing source green");
'''.replace('SOURCE',probe_source())
        result=subprocess.run(['node','-e',program],capture_output=True,text=True,timeout=5)
        self.assertEqual(0,result.returncode,result.stderr)


if __name__=='__main__':unittest.main()
