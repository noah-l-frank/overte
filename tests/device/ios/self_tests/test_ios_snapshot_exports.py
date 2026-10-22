"""Real host weak lifetimes/reader codec, modeled Photos/UIKit callback facts."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import subprocess
from pathlib import Path
import unittest
import uuid
import weakref
from adapters.normal_ui import NativeUIError
from ios.adapters import snapshot_exports as source

RUN='a'*32


class Operation:
    def __init__(self,action,run):
        self.id=str(uuid.uuid4());self.action=action;self.file='parity-'+run[:16]+'-still-png-snap_100010_1.png'
        self.state=dict(current=True,cancelled=False,phase=1,ownerAlive=True,
            sheetPresent=False,sheetPresenting=False,sheetDismissing=False,sheetAttached=False)


class Native:
    def __init__(self):
        self.now=100000;self.rows={};self.events=[];self.requests=[];self.sequence=0;self.authorization=3
    def tick(self):self.now+=1;return self.now
    def clock(self):return dict(epochMs=self.tick(),monotonicMs=self.now-99999)
    def event(self,op,kind,**detail):
        self.events.append(dict(sequence=len(self.events)+1,operation=op.id,kind=kind,clock=self.clock(),detail=detail))
    def start(self,action='save',run=RUN):
        op=Operation(action,run);self.rows[op.id]=(weakref.ref(op),dict(id=op.id,action=action,fileName=op.file,owned=True))
        self.event(op,'created');return op
    def callback(self,op,name,body):
        self.event(op,'callback-enter',name=name)
        try:body()
        finally:self.event(op,'callback-returned',name=name)
    def finish(self,op,status='success'):
        op.state.update(current=False,cancelled=False,phase=0)
        self.event(op,'delivery-enqueued',status=status,hasError=status=='error')
        def delivered():
            self.event(op,'delivery-owner',present=True);self.event(op,'qt-completed',status=status,hasError=status=='error')
        self.callback(op,'qt-delivery',delivered)
    def save(self,op):
        op.state['phase']=2;self.event(op,'photos-authorization-requested')
        def authorized():self.event(op,'photos-authorization',status=3);self.event(op,'main-enqueued',name='photos-authorized-main')
        self.callback(op,'photos-authorization',authorized)
        def commit():
            op.state['phase']=4;self.event(op,'photos-commit-enqueued')
            self.callback(op,'photos-changes',lambda:self.event(op,'photos-placeholder',identifier='actual-native-placeholder/L0/001'))
        self.callback(op,'photos-authorized-main',commit)
        def complete():self.event(op,'photos-completed',success=True,hasError=False);self.finish(op)
        self.callback(op,'photos-completion',complete)
    def send(self,query):
        self.requests.append(deepcopy(query));self.sequence+=1;before=self.clock();rows=[]
        for _weak,original in self.rows.values():
            op=_weak();rows.append(dict(original,alive=op is not None,state={} if op is None else deepcopy(op.state)))
        observed=dict(iosSnapshotExportsSourceVersion=1,instance='b'*32,bornEpochMs=99999,complete=True,
            clock=self.clock(),authorization=self.authorization,operations=rows,events=deepcopy(self.events))
        self.packet=dict(iosSnapshotExportsVersion=1,requestId=query['commandId'],runId=query['runId'],instance='c'*32,
            sequence=self.sequence,processId=42,clockDomain='native-main-snapshot-exports',clockBefore=before,clockAfter=self.clock(),source=observed)
    def reader(self):return source.IOSSnapshotExports(self.send,lambda:json.dumps(self.packet),self.tick,lambda:True,42,
        monotonic=lambda:self.now/1000,sleep=lambda _delay:None)


class SnapshotExportsTests(unittest.TestCase):
    def test_actual_photos_native_success_still_requires_destination_original_and_shared_callback_expiry(self):
        native=Native();reader=native.reader();empty=reader.read(RUN);source.drained(empty)
        op=native.start();native.save(op);identifier=op.id;current=reader.read(RUN)
        outcome=source.photos_asset(current,identifier);self.assertTrue(outcome['destinationOriginalRequired'])
        self.assertEqual('actual-native-placeholder/L0/001',outcome['photosIdentifier'])
        with self.assertRaises(NativeUIError):source.drained(current)
        del op;gone=reader.read(RUN);self.assertEqual([identifier],source.drained(gone)['operations'])
        self.assertNotIn('saved',outcome);self.assertNotIn('shares',outcome)
    def test_cancelled_share_and_native_success_never_prove_receiver_bytes(self):
        native=Native();reader=native.reader();op=native.start('share');op.state['phase']=3
        native.event(op,'share-created');native.event(op,'share-presentation-requested')
        native.callback(op,'share-completion',lambda:native.event(op,'share-completed',completed=False,hasError=False))
        native.finish(op,'cancelled');current=reader.read(RUN);self.assertEqual('cancelled',source.outcome(current,op.id)['nativeResult']['detail']['status'])
        with self.assertRaises(NativeUIError):source.photos_asset(current,op.id)
        del op;source.drained(reader.read(RUN))
    def test_forged_native_success_without_original_photos_commit_and_callback_is_refused(self):
        native=Native();op=native.start();native.finish(op);packet=native.reader().read(RUN)
        with self.assertRaises(NativeUIError):source.photos_asset(packet,op.id)
        changed=deepcopy(packet);changed['source']['events'][-2]['detail']['status']='error'
        with self.assertRaises(NativeUIError):source.original(changed)
        changed=deepcopy(packet);changed['source']['events'][0]['kind']='photos-completed'
        changed['source']['events'][0]['detail']=dict(success=True,hasError=False)
        with self.assertRaises(NativeUIError):source.original(changed)
    def test_stale_foreign_reused_or_rolled_back_originals_do_not_gain_new_freshness(self):
        native=Native();reader=native.reader();op=native.start();first=reader.read(RUN);native.save(op);second=reader.read(RUN)
        query=dict(schemaVersion=1,commandId=second['requestId'],action=source.ACTION,runId=RUN)
        for fault in ('pid','birth','history','nonce','clock','revived'):
            value=deepcopy(second)
            if fault=='pid':value['processId']=43
            elif fault=='birth':value['source']['instance']='f'*32
            elif fault=='history':value['source']['events'][0]['clock']['epochMs']+=1
            elif fault=='nonce':value['requestId']=first['requestId']
            elif fault=='clock':value['clockAfter']['epochMs']=1
            else:value['source']['operations'][0]['fileName']='parity-'+'f'*16+'-still-png-snap_1_1.png'
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):source.validate(value,query,42,previous=first)
    def test_native_hooks_are_passive_gated_and_placeholder_is_not_a_saved_byte_receipt(self):
        root=Path(__file__).resolve().parents[4];cpp=(root/'ios/snapshot/IOSSnapshotAdapter.mm').read_text()
        self.assertIn('#define exportEvent(...) ((void)0)',cpp);self.assertIn('std::weak_ptr<IOSSnapshotNativeOperation>',cpp)
        self.assertIn('featureObservedState()',cpp);self.assertIn('photos-placeholder',cpp)
        self.assertIn('authorizationStatusForAccessLevel:PHAccessLevelAddOnly',cpp)
        self.assertNotIn('requestImageData',cpp);self.assertNotIn('deleteAssets:',cpp)

    def test_genuine_other_run_photos_success_cannot_be_assigned_to_the_query_run(self):
        native=Native();op=native.start(run='f'*32);native.save(op);actual=native.reader().read(RUN)
        source.original(actual)
        with self.assertRaises(NativeUIError):source.photos_asset(actual,op.id)

    def test_actual_probe_branch_is_one_send_and_preserves_the_original_native_result(self):
        root=Path(__file__).resolve().parents[4];probe=(root/'tests/device/probe/overte_e2e_probe.js').read_text()
        start=probe.index('        if (command && command.action === "feature-ios-snapshot-exports")')
        end=probe.index('        if (command && command.action === "feature-ios-avatar-state")',start)
        script='''const assert=require('assert');let iosNewSourceRequests={},iosNewSourceRequestCount=0,saved=[],calls=0;
const Test={saveObject:(value,file)=>saved.push({value,file})};
function objectKeysMatch(v,keys){return JSON.stringify(Object.keys(v).sort())===JSON.stringify(keys.slice().sort());}
function apply(command){BRANCH}
const query={schemaVersion:1,commandId:'ios-'+'a'.repeat(32),action:'feature-ios-snapshot-exports',runId:'b'.repeat(32)};
apply(query);apply(query);assert.equal(saved.length,1);assert.equal(saved[0].value.status,'unavailable');
const original={iosSnapshotExportsVersion:1,requestId:'ios-'+'c'.repeat(32),nativeFact:'untouched'};
Test.featureIOSSnapshotExports=command=>{calls++;return original;};
apply({...query,commandId:original.requestId});apply({...query,commandId:original.requestId});
assert.equal(calls,1);assert.strictEqual(saved[1].value,original);assert.equal(saved[1].file,'feature-ios-snapshot-exports.json');
apply({...query,commandId:'ios-'+'d'.repeat(32),wanted:{saved:1}});assert.equal(saved.length,2);
'''.replace('BRANCH',probe[start:end])
        result=subprocess.run(['node','-e',script],capture_output=True,text=True,check=False)
        self.assertEqual(0,result.returncode,result.stderr)


if __name__=='__main__':unittest.main()
