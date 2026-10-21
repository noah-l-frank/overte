"""Real private files and synthetic native issuer; no C++/client/device run."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from adapters.normal_ui import NativeUIError
from adapters.world_render_receipts import NativeWorldReceiptInventory,inventory_command
from adapters.world_render_storage import receipt_file
from fixture.serve import FixtureState
from self_tests.test_native_feature_observation import probe_source


class Boundary:
    def __init__(self,root,*,ios=False):
        prefix='ios-' if ios else ''
        self.root,self.ios=root,ios
        self.owner=dict(capture=dict(commandId=prefix+'a'*32),receipts=[prefix+'b'*32,prefix+'c'*32])
        self.issued={};self.commands=[];self.value=None;self.sequence=0;self.clock=0.;self.epoch=20000
        self.okay=True;self.ignore_remove=False;self.partial=0;self.delay=0.;self.mutate=None
        self.retired,self.present,self.callbacks,self.png_bytes=True,False,0,0
        for nonce in self.owner['receipts']:self.issue(nonce)
        self.native=NativeWorldReceiptInventory(self.send,self.original,lambda:self.epoch,lambda:self.okay,31,
            lambda:deepcopy(self.owner),lambda:'d'*32,ios=ios,monotonic=lambda:self.clock,sleep=self.sleep)

    def issue(self,nonce,*,capture=None):
        path=self.root/receipt_file(nonce);path.write_text('original synthetic native receipt '+nonce);path.chmod(0o600)
        self.issued[nonce]=(capture or self.owner['capture']['commandId'],hashlib.sha256(path.read_bytes()).hexdigest())

    def send(self,request):
        inventory_command(request,ios=self.ios);self.commands.append(deepcopy(request));self.sequence+=1
        capture=request['requestId'];wanted=set(request['receiptIds'])
        valid=self.retired and not self.present and not self.callbacks and not self.png_bytes
        valid=valid and all(nonce in wanted for nonce,(owner,_digest) in self.issued.items() if owner==capture)
        for nonce in wanted:
            path=self.root/receipt_file(nonce);issued=self.issued.get(nonce)
            if (issued is not None and issued[0]!=capture or path.is_symlink()
                    or path.exists() and (not path.is_file() or path.stat().st_nlink!=1 or path.stat().st_uid!=os.geteuid()
                        or path.stat().st_mode&0o7777!=0o600
                        or issued is None or hashlib.sha256(path.read_bytes()).hexdigest()!=issued[1])):valid=False
        if not valid:self.value=dict(commandId=request['commandId'],available=False);return
        if request['operation']=='remove' and not self.ignore_remove:
            for nonce in wanted:
                if nonce in self.issued:(self.root/receipt_file(nonce)).unlink(missing_ok=True)
        rows=[]
        for nonce in request['receiptIds']:
            path=self.root/receipt_file(nonce);exists=path.exists() or path.is_symlink();issued=self.issued.get(nonce)
            rows.append(dict(receiptId=nonce,issued=issued is not None,exists=exists,
                originalMatches=issued is not None and exists and hashlib.sha256(path.read_bytes()).hexdigest()==issued[1]))
        source=dict(retired=self.retired,present=self.present,callbacks=self.callbacks,pngBytes=self.png_bytes,
            complete=True,receipts=rows)
        if request['operation']=='remove':source['performed']=True
        self.value=dict(receiptInventoryVersion=1,commandId=request['commandId'],requestId=capture,
            operation=request['operation'],instance='d'*32,sequence=self.sequence,processId=31,capturedEpochMs=self.epoch,source=source)
        if self.mutate:self.mutate(self.value)

    def original(self):
        self.clock+=self.delay
        if self.partial:self.partial-=1;return '{'
        return json.dumps(self.value)
    def sleep(self,seconds):self.clock+=seconds


class WorldReceiptInventoryTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory(prefix='overte-receipt-inventory-');self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name);self.source=Boundary(self.root);self.native=self.source.native

    def test_complete_original_set_is_removed_and_then_independently_observed_absent(self):
        proof=self.native.retire()
        self.assertEqual(['remove','inspect'],[r['operation'] for r in self.source.commands])
        self.assertNotEqual(proof['removed']['commandId'],proof['absent']['commandId'])
        self.assertEqual([],list(self.root.iterdir()));self.assertEqual(2,len(proof['absent']['source']['receipts']))
        self.assertTrue(all(row['issued'] and not row['exists'] for row in proof['absent']['source']['receipts']))
        self.assertNotIn('expected',json.dumps(self.source.commands));self.assertNotIn('path',json.dumps(self.source.commands))

    def test_unissued_intent_qualifies_only_with_original_retired_context_and_actual_absence(self):
        nonce='e'*32;self.source.owner['receipts'].append(nonce)
        proof=self.native.retire();row=next(r for r in proof['absent']['source']['receipts'] if r['receiptId']==nonce)
        self.assertEqual(dict(receiptId=nonce,issued=False,exists=False,originalMatches=False),row)

    def test_late_issuance_of_an_originally_unissued_intent_is_not_new_valid_history(self):
        nonce='e'*32;self.source.owner['receipts'].append(nonce)
        before=self.native.request('inspect')
        self.assertFalse(next(row for row in before['source']['receipts'] if row['receiptId']==nonce)['issued'])
        # Model a defective native producer dispatching a known old command late.
        # The actual new native ledger declines that nonce; the independent
        # reader must also refuse a producer that violates this guarantee.
        self.source.issue(nonce)
        with self.assertRaises(NativeUIError):self.native.request('inspect')
        self.assertEqual(1,self.native.sequence)
        self.assertTrue((self.root/receipt_file(nonce)).exists())

    def test_one_reader_keeps_separate_immutable_issuer_histories_for_successive_captures(self):
        first=deepcopy(self.source.owner);self.native.retire()
        self.source.owner=dict(capture=dict(commandId='e'*32),receipts=['f'*32])
        self.source.issue('f'*32);self.native.retire()
        self.assertEqual(2,len(self.native.histories));self.assertEqual([],list(self.root.iterdir()))
        self.source.owner=first
        self.source.mutate=lambda value:value['source']['receipts'][0].update(issued=False)
        with self.assertRaises(NativeUIError):self.native.request('inspect')

    def test_present_unknown_file_is_not_deleted_under_an_unissued_intent(self):
        nonce='e'*32;self.source.owner['receipts'].append(nonce)
        path=self.root/receipt_file(nonce);path.write_text('foreign');path.chmod(0o600)
        with self.assertRaises(NativeUIError):self.native.retire()
        self.assertEqual('foreign',path.read_text());self.assertEqual(3,len(list(self.root.iterdir())))

    def test_changed_receipt_prevents_deleting_any_other_file_in_the_set(self):
        path=self.root/receipt_file(self.source.owner['receipts'][-1]);path.write_text('foreign replacement')
        with self.assertRaises(NativeUIError):self.native.retire()
        self.assertEqual(2,len(list(self.root.iterdir())));self.assertEqual('foreign replacement',path.read_text())

    def test_exposed_special_mode_hardlink_and_symlink_receipts_preserve_the_entire_set(self):
        for fault in ('exposed','executable','special','hardlink','symlink'):
            root=self.root/fault;root.mkdir(mode=0o700);source=Boundary(root)
            path=root/receipt_file(source.owner['receipts'][0]);other=root/'unowned-link'
            if fault=='exposed':path.chmod(0o644)
            elif fault=='executable':path.chmod(0o700)
            elif fault=='special':path.chmod(0o4600)
            elif fault=='hardlink':os.link(path,other)
            else:path.rename(other);path.symlink_to(other.name)
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):source.native.retire()
            self.assertTrue(path.exists());self.assertTrue((root/receipt_file(source.owner['receipts'][1])).exists())

    def test_missing_host_prefix_or_foreign_capture_receipt_is_not_a_complete_original_set(self):
        self.source.issue('e'*32)
        with self.assertRaises(NativeUIError):self.native.request('inspect')
        self.assertEqual(3,len(list(self.root.iterdir())))
        self.source.owner['receipts'].append('e'*32);self.source.issued['e'*32]=('f'*32,self.source.issued['e'*32][1])
        with self.assertRaises(NativeUIError):self.native.request('inspect')

    def test_live_memory_or_callbacks_and_unretired_context_never_authorize_file_cleanup(self):
        for key,value in (('retired',False),('present',True),('callbacks',1),('png_bytes',4)):
            original=getattr(self.source,key);setattr(self.source,key,value)
            with self.subTest(key=key),self.assertRaises(NativeUIError):self.native.retire()
            setattr(self.source,key,original);self.assertEqual(2,len(list(self.root.iterdir())))

    def test_successful_ignored_remove_ack_cannot_hide_actual_remaining_files(self):
        self.source.ignore_remove=True
        with self.assertRaises(NativeUIError):self.native.retire()
        self.assertEqual(['remove','inspect'],[r['operation'] for r in self.source.commands]);self.assertEqual(2,len(list(self.root.iterdir())))
        self.source.ignore_remove=False;self.assertTrue(self.native.retire()['removed']['source']['performed'])

    def test_duplicate_missing_or_foreign_rows_fail_even_with_a_fresh_matching_nonce(self):
        for fault in ('duplicate','missing','foreign','extra','complete'):
            def mutate(value):
                rows=value['source']['receipts']
                if fault=='duplicate':rows[1]=deepcopy(rows[0])
                elif fault=='missing':rows.pop()
                elif fault=='foreign':rows[0]['receiptId']='f'*32
                elif fault=='extra':rows.append(deepcopy(rows[0]))
                else:value['source']['complete']=False
            self.source.mutate=mutate
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):self.native.request('inspect')

    def test_boolean_types_and_original_match_consistency_do_not_accept_coerced_or_impossible_rows(self):
        for change in (dict(issued=1),dict(exists=0),dict(originalMatches=1),dict(issued=False),dict(exists=False,originalMatches=True)):
            self.source.mutate=lambda value:value['source']['receipts'][0].update(change)
            with self.subTest(change=change),self.assertRaises(NativeUIError):self.native.request('inspect')

    def test_native_context_pid_original_clock_and_source_cursor_cannot_be_replaced(self):
        for change in (dict(instance='e'*32),dict(processId=32),dict(requestId='e'*32),dict(operation='remove'),
                dict(sequence=0),dict(capturedEpochMs=18000),dict(receiptInventoryVersion=True)):
            self.source.mutate=lambda value:value.update(change)
            with self.subTest(change=change),self.assertRaises(NativeUIError):self.native.request('inspect')
        self.assertEqual(0,self.native.sequence)

    def test_partial_original_metadata_retries_reads_without_repeating_deletion(self):
        self.source.partial=3;proof=self.native.retire()
        self.assertEqual(2,len(self.source.commands));self.assertFalse(any(row['exists'] for row in proof['absent']['source']['receipts']))

    def test_issued_status_cannot_change_between_original_remove_and_fresh_inspect(self):
        def mutate(value):
            if value['operation']=='inspect':value['source']['receipts'][0]['issued']=False
        self.source.mutate=mutate
        with self.assertRaises(NativeUIError):self.native.retire()

    def test_command_scope_is_closed_bounded_and_does_not_accept_expected_results_or_paths(self):
        value=dict(schemaVersion=1,commandId='a'*32,action='feature-world-render-receipts',requestId='b'*32,
            receiptIds=['c'*32],operation='inspect')
        self.assertEqual(value,inventory_command(value))
        for change in (dict(receiptIds=[]),dict(receiptIds=['c'*32]*2),dict(receiptIds=['file:///user.png']),
                dict(receiptIds=[str(i).zfill(32) for i in range(1025)]),dict(schemaVersion=True),dict(expectedAbsent=True),dict(operation='erase')):
            with self.subTest(change=str(change)[:80]),self.assertRaises(NativeUIError):inventory_command(value|change)

    def test_original_clock_query_cannot_hide_owner_or_process_guard_loss(self):
        for fault in ('guard','owner','clock'):
            calls=[]
            def clock():
                calls.append(1)
                if len(calls)>1:
                    if fault=='guard':self.source.okay=False
                    elif fault=='owner':self.source.owner['capture']['commandId']='f'*32
                    else:return 19999
                return 20000
            self.source.okay=True;self.source.owner['capture']['commandId']='a'*32;self.native.clock_ms=clock
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):self.native.request('inspect')
        self.assertEqual(0,self.native.sequence)

    def test_total_transfer_and_final_guard_latency_are_inside_the_existing_time_bounds(self):
        self.source.delay=5.01
        with self.assertRaises(NativeUIError):self.native.request('inspect')
        self.source.delay=0;self.source.clock=0;calls=[]
        def guard():
            calls.append(1)
            if len(calls)==4:self.source.clock+=1.501
            return True
        self.native.guard=guard
        with self.assertRaises(NativeUIError):self.native.request('inspect')

    def test_existing_fixture_dispatch_admits_only_the_exact_ios_prefixed_inventory_grammar(self):
        value=dict(schemaVersion=1,commandId='ios-'+'a'*32,action='feature-world-render-receipts',requestId='ios-'+'b'*32,
            receiptIds=['ios-'+'c'*32],operation='inspect')
        self.assertEqual(value,FixtureState().set_client_command(value))
        for change in (dict(path='private/user.png'),dict(receiptIds=['c'*32]),dict(expectedAbsent=True)):
            with self.subTest(change=change),self.assertRaises((ValueError,RuntimeError)):FixtureState().set_client_command(value|change)

    def test_actual_probe_preserves_native_inventory_and_deduplicates_only_the_same_command(self):
        program=r'''
const Uuid={generate:()=>"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"};
const objectKeysMatch=(v,keys)=>JSON.stringify(Object.keys(v).sort())===JSON.stringify(keys.sort());
let calls=[],files=[];const original={receiptInventoryVersion:1,commandId:"a".repeat(32),capturedEpochMs:17000,source:{receipts:[]}};
const Test={featureWorldRenderReceipts:v=>{calls.push(v);return original;},saveObject:(v,name)=>files.push({v,name})};
SOURCE
const request={schemaVersion:1,commandId:"a".repeat(32),action:"feature-world-render-receipts",requestId:"b".repeat(32),receiptIds:["c".repeat(32)],operation:"inspect"};
applyAndroidControlCommand(request);applyAndroidControlCommand(request);
if(calls.length!==1||files.length!==1||files[0].v!==original||original.capturedEpochMs!==17000)throw Error("original replaced or retimed");
if(files[0].name!=="world-render-receipts-result.json")throw Error("wrong original result file");
applyClientCommand({...request,commandId:"d".repeat(32),expectedAbsent:true});
if(calls.length!==1)throw Error("expected results reached original issuer");
delete Test.featureWorldRenderReceipts;applyClientCommand({...request,commandId:"e".repeat(32)});
if(files.length!==2||files[1].v.available!==false)throw Error("missing original source green");
'''.replace('SOURCE',probe_source())
        result=subprocess.run(['node','-e',program],capture_output=True,text=True,timeout=5)
        self.assertEqual(0,result.returncode,result.stderr)


if __name__=='__main__':unittest.main()
