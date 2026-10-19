"""Private carrier logic on real temporary originals, not native qualification."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
import uuid
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from adapters.normal_feature_state import PrivateFeatureState
from adapters.private_login_input import PrivateLoginInput,filename,command,input_command
from adapters.normal_ui import NativeUIError

RUN='a'*32
BINDING=dict(scope='NATIVE_UI_COMPONENT_ONLY',processIdentity='42',sessionId='owned-source',generation=1,targetFingerprint='b'*64)
INPUT=dict(schemaVersion=1,commandId=str(uuid.uuid4()),instance=str(uuid.uuid4()),sequence=1,
    observedElapsedMs=0,fieldToken=str(uuid.uuid4()),operation='replace',text='synthetic-private-fixture-password')


class Boundary:
    """Explicit synthetic native seam. OS files/FDs and input bytes are real."""
    pid=42
    def __init__(self,root,store):
        self.root=root;self.store=store;self.clock=0.;self.sequence=0;self.instance='c'*32
        self.rows={};self.commands=[];self.value=None;self.fault='';self.alive=True
        self.actual=None;self.deliveries=0;self.write_journal=None;self.deferred=None;self.drains=0
    def guard(self):
        if not self.alive:raise NativeUIError('Synthetic process is unavailable')
    def sleep(self,value):self.clock+=value
    def row(self,request):return self.rows.get(request['inputId'])
    def path(self,request):return self.root/filename(request['inputId'])
    def original(self,name):return (self.root/name).read_bytes()
    def write(self,name,raw):
        self.write_journal=deepcopy(self.store.read())
        if self.fault in ('late-push','drain-error'):
            self.deferred=(name,raw);raise NativeUIError('Synthetic transfer response was lost')
        if self.fault=='push-ack':return
        path=self.root/name
        if self.fault=='foreign-inode':path.unlink();path.write_bytes(raw);path.chmod(0o600)
        else:
            with path.open('r+b') as output:output.seek(0);output.write(raw);output.truncate();output.flush();os.fsync(output.fileno())
        if self.fault=='process-loss':self.alive=False
        if self.fault=='late-write':self.clock+=16
    def drain(self,name):
        self.drains+=1
        if self.fault=='drain-error':raise RuntimeError('Synthetic private transport remains unresolved')
        if self.deferred is not None:
            filename,raw=self.deferred;assert filename==name
            path=self.root/name
            with path.open('r+b') as output:output.seek(0);output.write(raw);output.truncate()
            self.deferred=None
        return self.original(name)
    def owned(self,path,row):
        if row is None or row.get('fd') is None or not path.exists():return False
        value=path.lstat();original=row['original']
        return stat.S_ISREG(value.st_mode) and value.st_nlink==1 and value.st_uid==os.geteuid() and (value.st_dev,value.st_ino)==(original.st_dev,original.st_ino)
    def erase(self,path,row,close=False):
        if path.exists():
            if not self.owned(path,row):return False
            path.unlink()
        if row.get('fd') is not None:
            os.ftruncate(row['fd'],0)
            if close:os.close(row['fd']);row['fd']=None
        return True
    def send(self,request):
        self.guard();command(request);self.commands.append(deepcopy(request));self.sequence+=1
        path=self.path(request);row=self.row(request);operation=request['operation'];available=True
        if row is not None and row['run']!=request['runId']:available=False
        elif operation=='reserve':
            if row is None and not path.exists():
                fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
                row=dict(run=request['runId'],reserved=True,retired=False,attempted=False,fd=fd,original=os.fstat(fd))
                self.rows[request['inputId']]=row
            if row is None or row['retired']:available=False
        elif operation=='retire':
            if row is None:
                row=dict(run=request['runId'],reserved=False,retired=True,attempted=False,fd=None)
                self.rows[request['inputId']]=row
            if self.fault!='cleanup-ack':
                row['retired']=True;available=self.erase(path,row,close=self.fault!='fd-retained')
        elif operation=='deliver':
            if row is None or row['retired'] or row['attempted'] or not self.owned(path,row):available=False
            else:
                row['attempted']=True;raw=path.read_bytes();payload=json.loads(raw)
                if payload['runId']!=request['runId'] or payload['inputId']!=request['inputId']:available=False
                else:
                    input_command(payload['input']);value=payload['input']
                    available=self.erase(path,row)
                    if available:
                        self.deliveries+=1
                        if self.fault!='ignored-input':self.actual=value['text']
                        row['inputStatus']=dict(schemaVersion=1,commandId=value['commandId'],instance=value['instance'],sequence=value['sequence'],
                            performed=self.actual==value['text'],processId=self.pid,sampleEpochMs=20000+round(self.clock*1000))
        state=dict(reserved=row is not None and row['reserved'],retired=row is not None and row['retired'],
            attempted=row is not None and row['attempted'],filePresent=path.exists(),fileOwned=self.owned(path,row),pending=False,
            openFiles=int(row is not None and row.get('fd') is not None))
        if row is not None and 'inputStatus' in row:state['inputStatus']=deepcopy(row['inputStatus'])
        self.value=dict(inputVersion=2,commandId=request['commandId'],operation=operation,runId=request['runId'],inputId=request['inputId'],
            instance=self.instance,processId=self.pid,capturedEpochMs=20000+round(self.clock*1000),elapsedMs=round(self.clock*1000),
            sequence=self.sequence,available=available,source=state)
        if self.fault=='stale-sequence':self.value['sequence']=1
        elif self.fault=='foreign-source':self.value['instance']='d'*32
        elif self.fault=='foreign-nonce':self.value['commandId']='ios-'+'d'*32
        elif self.fault=='pending':self.value['source']['pending']=True
        elif self.fault=='missing-result' and operation=='inspect':self.value['source'].pop('inputStatus',None)
    def read(self):return json.dumps(self.value)
    def close(self):
        for row in self.rows.values():
            if row.get('fd') is not None:os.close(row['fd']);row['fd']=None


class PrivateLoginInputTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.root.chmod(0o700)
        self.store=PrivateFeatureState(self.root/'owner.json');self.native=Boundary(self.root,self.store)
        self.addCleanup(self.native.close)
        self.owner=self.make()
    def make(self):return PrivateLoginInput(self.native,self.store,BINDING,RUN,monotonic=lambda:self.native.clock,sleep=self.native.sleep)

    def test_original_private_bytes_deliver_once_and_actual_file_fd_cleanup_precedes_journal_removal(self):
        self.owner.replace(INPUT)
        self.assertEqual(INPUT['text'],self.native.actual);self.assertEqual(1,self.native.deliveries)
        self.assertIsNone(self.store.read());self.assertEqual([],list(self.root.glob('feature-login-input-*')))
        self.assertTrue(all(r['fd'] is None and r['retired'] for r in self.native.rows.values()))
        self.assertNotIn(INPUT['text'],repr(self.native.commands)+repr(self.native.value)+repr(self.native.write_journal))

    def test_push_ack_without_original_bytes_never_reaches_product_input(self):
        self.native.fault='push-ack'
        with self.assertRaises(NativeUIError):self.owner.replace(INPUT)
        self.assertEqual(0,self.native.deliveries);self.assertIsNone(self.store.read())

    def test_ignored_native_field_input_and_missing_original_status_cannot_pass(self):
        for fault in ('ignored-input','missing-result'):
            self.native.fault=fault
            with self.assertRaises(NativeUIError):self.owner.replace(INPUT)
            self.assertIsNone(self.store.read())
            self.native.fault=''

    def test_valid_copied_bytes_in_foreign_inode_are_not_adopted_or_removed(self):
        self.native.fault='foreign-inode'
        with self.assertRaises(NativeUIError):self.owner.replace(INPUT)
        self.assertEqual(0,self.native.deliveries);self.assertIsNotNone(self.store.read())
        row=self.store.read();self.assertTrue((self.root/filename(row['inputId'])).exists())
        with self.assertRaises(NativeUIError):self.make().retire()
        self.assertTrue((self.root/filename(row['inputId'])).exists())

    def test_cleanup_ack_and_unclosed_real_descriptor_keep_original_ownership(self):
        for fault in ('cleanup-ack','fd-retained'):
            self.native.fault=fault
            with self.assertRaises(NativeUIError):self.owner.replace(INPUT)
            self.assertIsNotNone(self.store.read());self.assertTrue(any(r.get('fd') is not None for r in self.native.rows.values()))
            self.native.fault='';self.make().retire();self.assertIsNone(self.store.read());self.owner=self.make()

    def test_changed_process_blocks_cleanup_and_retains_private_file_intent(self):
        self.native.fault='process-loss'
        with self.assertRaises(NativeUIError):self.owner.replace(INPUT)
        self.assertIsNotNone(self.store.read());self.assertEqual(0,self.native.deliveries)
        self.native.alive=True;self.native.fault='';self.make().retire();self.assertIsNone(self.store.read())

    def test_stale_foreign_pending_or_missing_nonce_cannot_be_fresh_original_evidence(self):
        for fault in ('stale-sequence','foreign-nonce','pending'):
            self.native.fault=fault
            with self.assertRaises(NativeUIError):self.owner.replace(INPUT)
            self.assertEqual(0,self.native.deliveries);self.assertIsNotNone(self.store.read())
            self.native.fault='';self.make().retire();self.owner=self.make()

    def test_source_instance_switch_after_original_binding_cannot_retire_another_context(self):
        self.native.fault='cleanup-ack'
        with self.assertRaises(NativeUIError):self.owner.replace(INPUT)
        before=deepcopy(self.store.read());self.native.fault='foreign-source'
        with self.assertRaises(NativeUIError):self.make().retire()
        self.assertEqual(before,self.store.read())
        self.native.fault='';self.make().retire()

    def test_invalid_input_never_mutates_or_discards_an_existing_unresolved_scope(self):
        self.native.fault='cleanup-ack'
        with self.assertRaises(NativeUIError):self.owner.replace(INPUT)
        before=deepcopy(self.store.read());count=len(self.native.commands)
        with self.assertRaises(NativeUIError):self.owner.replace(dict(INPUT,text='bad\ninput'))
        self.assertEqual(count,len(self.native.commands));self.assertEqual(before,self.store.read())
        self.native.fault='';self.make().retire()

    def test_wrong_binding_or_run_cannot_adopt_an_existing_private_journal(self):
        self.native.fault='cleanup-ack'
        with self.assertRaises(NativeUIError):self.owner.replace(INPUT)
        with self.assertRaises(NativeUIError):PrivateLoginInput(self.native,self.store,dict(BINDING,generation=2),RUN)
        with self.assertRaises(NativeUIError):PrivateLoginInput(self.native,self.store,BINDING,'d'*32)

    def test_native_input_and_cleanup_deadlines_include_transport_time(self):
        self.native.fault='late-write'
        with self.assertRaises(NativeUIError):self.owner.replace(INPUT)
        self.assertEqual(0,self.native.deliveries);self.assertIsNone(self.store.read())

    def test_uncertain_transfer_is_drained_before_retirement_and_cannot_write_late_data(self):
        self.native.fault='late-push'
        with self.assertRaises(NativeUIError):self.owner.replace(INPUT)
        self.assertEqual(1,self.native.drains);self.assertIsNone(self.native.deferred)
        self.assertIsNone(self.store.read());self.assertEqual([],list(self.root.glob('feature-login-input-*')))
        self.assertEqual(0,self.native.deliveries)

    def test_missing_private_transport_drain_keeps_intent_until_real_fence_recovery(self):
        self.native.fault='drain-error'
        with self.assertRaises(NativeUIError):self.owner.replace(INPUT)
        self.assertTrue(self.store.read()['transferPending']);self.assertIsNotNone(self.native.deferred)
        self.assertFalse(any(r['operation']=='retire' for r in self.native.commands))
        self.native.fault='';self.make().retire()
        self.assertIsNone(self.store.read());self.assertIsNone(self.native.deferred)

    def test_stalled_clock_and_ignored_receipts_are_attempt_bounded(self):
        self.native.fault='foreign-nonce';self.owner.sleep=lambda _:None
        with self.assertRaises(NativeUIError):self.owner.replace(INPUT)
        self.assertLessEqual(len(self.native.commands),2);self.assertIsNotNone(self.store.read())

    def test_expected_results_and_private_text_are_rejected_by_public_metadata_contract(self):
        metadata=dict(schemaVersion=1,commandId='ios-'+'b'*32,action='feature-private-login-input',operation='reserve',runId=RUN,inputId='c'*32)
        for extra in ({'text':INPUT['text']},{'expected':{'performed':True}},{'input':INPUT}):
            with self.assertRaises(NativeUIError):command(dict(metadata,**extra))

    def test_real_fixture_accepts_only_closed_metadata_and_never_a_private_payload(self):
        sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'fixture'))
        from serve import FixtureState
        fixture=FixtureState();metadata=dict(schemaVersion=1,commandId='ios-'+'b'*32,action='feature-private-login-input',
            operation='inspect',runId=RUN,inputId='c'*32)
        self.assertEqual(metadata,fixture.set_client_command(metadata))
        for extra in ({'text':INPUT['text']},{'input':INPUT},{'expected':True}):
            with self.assertRaises(ValueError):fixture.set_client_command(dict(metadata,**extra))
        self.assertEqual(metadata,fixture.snapshot_client_command());self.assertNotIn(INPUT['text'],repr(fixture.snapshot_client_command()))

    def test_original_javascript_dispatch_has_no_text_channel_and_missing_hook_is_unavailable(self):
        from self_tests.test_native_feature_observation import probe_source
        program=r'''const Uuid={generate:()=>"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"};
const objectKeysMatch=(v,k)=>JSON.stringify(Object.keys(v).sort())===JSON.stringify(k.sort());
let calls=[],files=[];
const Test={iosPrivateLoginInput:r=>{calls.push({...r});return {commandId:r.commandId,inputVersion:2,available:true};},
saveObject:(v,name)=>files.push({v,name})};
SOURCE
const request={schemaVersion:1,commandId:"ios-"+"a".repeat(32),action:"feature-private-login-input",operation:"reserve",runId:"b".repeat(32),inputId:"c".repeat(32)};
applyClientCommand(request);applyClientCommand(request);
if(calls.length!==1||files[0].name!=="feature-private-login-input.json")throw Error("original dispatch/replay");
applyClientCommand({...request,commandId:"ios-"+"d".repeat(32),text:"private-input-must-not-travel-here"});
if(calls.length!==1||JSON.stringify(files).includes("private-input-must-not-travel-here"))throw Error("public payload leak");
delete Test.iosPrivateLoginInput;applyClientCommand({...request,commandId:"ios-"+"e".repeat(32)});
if(files[1].v.available!==false)throw Error("unavailable hook green");
'''.replace('SOURCE',probe_source())
        result=subprocess.run(['node','-e',program],capture_output=True,text=True,timeout=5)
        self.assertEqual(0,result.returncode,result.stderr)

    def test_private_payload_schema_rejects_extra_expected_values_and_key_codes(self):
        for value in (dict(INPUT,expected='success'),dict(INPUT,text='\ue007'),dict(INPUT,sequence=True),dict(INPUT,text='')):
            with self.assertRaises(NativeUIError):self.owner.replace(value)
        self.assertEqual([],self.native.commands);self.assertIsNone(self.store.read())
