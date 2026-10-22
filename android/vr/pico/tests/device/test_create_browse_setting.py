"""Durable fixed-key ownership, uncertainty and original-source counterexamples."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[5];sys.path.insert(0,str(ROOT/'tests/device'))
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.pico4.create_browse_setting import NativeCreateBrowseSetting,OwnedCreateBrowseSetting,source,validate,continuity,ACTION
from self_tests.test_native_script_files import BINDING
from self_tests.test_native_feature_observation import probe_source

RUN='a'*32;TICKET='b'*32


def raw(text=None):
    data=b'original-invalid-variant' if text is None else text.encode()
    return dict(present=text is not None,typeId=0 if text is None else 10,typeName=None if text is None else 'QString',
        base64=base64.b64encode(data).decode(),sha256=hashlib.sha256(data).hexdigest(),stringValue=text)


class Boundary:
    def __init__(self):
        self.value=None;self.sequence=0;self.raw='';self.sent=[];self.lose=None;self.before_loss=False
        self.setting=raw();self.clock=0.;self.freeze_writer=False
    def send(self,command):
        self.sent.append(deepcopy(command));op=command['operation']
        if self.lose==op and self.before_loss:raise NativeUIError('lost before native dispatch')
        if op=='reserve':
            if self.value is not None:raise AssertionError('native reserve resent')
            self.value=dict(createBrowseSettingVersion=2,leaseId='c'*32,runId=RUN,createdEpochMs=10000,original=raw(),current=raw(),
                claims=[],reads=[],owned=raw(),writer=dict(id='6'*32,capturedEpochMs=20000,raw=raw()),restoreAttempted=False,restored=False,released=False)
        elif op=='claim-read':
            self.value['reads'].append(dict(dialogId='d'*32,sourceInstance='e'*32,ticket=TICKET,role='import',claimedEpochMs=13000,
                read=dict(before=dict(capturedEpochMs=11000,raw=deepcopy(self.setting)),after=dict(capturedEpochMs=12000,raw=deepcopy(self.setting)))))
            self.value['owned']=deepcopy(self.setting)
        elif op=='claim':
            self.setting=raw('/original/owned/directory');self.value['claims'].append(dict(dialogId='d'*32,sourceInstance='e'*32,ticket=TICKET,
                role='import',responseSha256='f'*64,setting=deepcopy(self.setting),registeredEpochMs=11000,returnedEpochMs=15000,claimedEpochMs=16000))
            self.value['owned']=deepcopy(self.setting)
        elif op=='restore':
            self.value['restoreAttempted']=True
            if self.setting==self.value['claims'][-1]['setting']:self.setting=deepcopy(self.value['original']);self.value['restored']=True
        elif op=='release':self.value['released']=True
        if self.lose==op:raise NativeUIError('lost after native effect')
        self.value['current']=deepcopy(self.setting)
        if not self.freeze_writer:self.value['writer']['raw']=deepcopy(self.setting)
        self.sequence+=1
        self.raw=json.dumps(dict(schemaVersion=1,requestId=command['commandId'],instance='9'*32,sequence=self.sequence,
            requestedEpochMs=20000,capturedEpochMs=20000,processId=123,runId=RUN,operation=op,source=self.value),indent=2)+'\n'
    def native(self):return NativeCreateBrowseSetting(self.send,lambda:self.raw,lambda:20000,lambda:True,123,
        monotonic=lambda:self.clock,sleep=lambda seconds:setattr(self,'clock',self.clock+seconds))


class CreateBrowseSettingTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup);path=Path(temporary.name);path.chmod(0o700)
        self.store=PrivateFeatureState(path/'setting.json');self.b=Boundary()
    def make(self):return OwnedCreateBrowseSetting(self.b.native(),self.store,BINDING)
    def claim(self,owner):
        if not owner.observe()['reads']:
            owner.claim_read(dict(ticket=TICKET,ownerToken='8'*64),dict(dialogId='d'*32,role='import'))
        return owner.claim(dict(ticket=TICKET,ownerToken='8'*64),dict(dialogId='d'*32,role='import'))
    def test_lost_reserve_claim_restore_release_recover_by_original_reads_without_resend(self):
        owner=self.make();self.b.lose='reserve'
        with self.assertRaises(NativeUIError):owner.reserve(RUN)
        owner=self.make();self.b.lose=None;owner.reserve(RUN)
        self.b.lose='claim'
        with self.assertRaises(NativeUIError):self.claim(owner)
        owner=self.make();self.b.lose=None;self.claim(owner)
        self.b.lose='restore'
        with self.assertRaises(NativeUIError):owner.restore()
        owner=self.make();self.b.lose=None;self.assertEqual(raw(),owner.restore()['current'])
        self.b.lose='release'
        with self.assertRaises(NativeUIError):owner.release()
        owner=self.make();self.b.lose=None;owner.release();self.assertIsNotNone(self.store.read())
        owner.retire();self.assertIsNone(self.store.read())
        for operation in ('reserve','claim','restore','release'):
            self.assertEqual(1,sum(c['operation']==operation for c in self.b.sent))
    def test_uncertain_original_read_claim_is_observed_once_and_never_resent(self):
        for before in (False,True):
            with self.subTest(before=before):
                if self.store.read() is not None:self.store.discard(self.store.read())
                self.b=Boundary();owner=self.make();owner.reserve(RUN);self.b.lose='claim-read';self.b.before_loss=before
                files=dict(ticket=TICKET,ownerToken='8'*64);binding=dict(dialogId='d'*32,role='import')
                with self.assertRaises(NativeUIError):owner.claim_read(files,binding)
                owner=self.make();self.b.lose=None
                if before:
                    with self.assertRaises(NativeUIError):owner.claim_read(files,binding)
                else:self.assertEqual(1,len(owner.claim_read(files,binding)['reads']))
                self.assertEqual(1,sum(c['operation']=='claim-read' for c in self.b.sent));self.assertIsNotNone(self.store.read())
    def test_unsent_uncertain_claim_or_restore_is_retained_and_cannot_be_retried(self):
        for operation in ('claim','restore'):
            with self.subTest(operation=operation):
                if self.store.read() is not None:self.store.discard(self.store.read())
                self.b=Boundary();owner=self.make();owner.reserve(RUN)
                if operation=='restore':self.claim(owner)
                self.b.lose=operation;self.b.before_loss=True
                with self.assertRaises(NativeUIError):(self.claim(owner) if operation=='claim' else owner.restore())
                owner=self.make();self.b.lose=None
                with self.assertRaises(NativeUIError):(self.claim(owner) if operation=='claim' else owner.restore())
                self.assertEqual(1,sum(c['operation']==operation for c in self.b.sent));self.assertIsNotNone(self.store.read())
    def test_foreign_actual_setting_is_preserved_and_never_reports_restored(self):
        owner=self.make();owner.reserve(RUN);self.claim(owner);self.b.setting=raw('/foreign/location')
        with self.assertRaises(NativeUIError):owner.restore()
        self.assertEqual('/foreign/location',self.b.setting['stringValue']);self.assertFalse(self.b.value['restored'])
        with self.assertRaises(NativeUIError):self.make().restore()
        self.assertEqual(1,sum(c['operation']=='restore' for c in self.b.sent));self.assertIsNotNone(self.store.read())
    def test_restored_manager_memory_with_unrestored_original_writer_cannot_retire(self):
        owner=self.make();owner.reserve(RUN);self.claim(owner);self.b.freeze_writer=True
        with self.assertRaises(NativeUIError):owner.restore()
        self.assertEqual(raw(),self.b.value['current']);self.assertNotEqual(raw(),self.b.value['writer']['raw'])
        with self.assertRaises(NativeUIError):self.make().release()
        self.assertIsNotNone(self.store.read());self.assertEqual(1,sum(c['operation']=='restore' for c in self.b.sent))
        self.assertFalse(any(c['operation']=='release' for c in self.b.sent))
    def test_corrupt_original_raw_history_or_candidate_cannot_rebind(self):
        owner=self.make();owner.reserve(RUN);self.claim(owner);before=owner.native.last
        for change in (lambda p:p['source']['original'].update(sha256='0'*64),lambda p:p['source'].update(leaseId='7'*32),
                lambda p:p['source'].update(claims=[]),lambda p:p.update(instance='7'*32),lambda p:p['source']['writer'].update(id='7'*32)):
            value=deepcopy(before);value['sequence']+=1;change(value)
            with self.subTest(change=change),self.assertRaises(NativeUIError):
                validate(value,value['requestId'],123,20000);continuity(before,value)
        state=self.store.read();state['binding']['artifactSha256']='0'*64;self.store.write(state,self.store.read())
        with self.assertRaises(NativeUIError):self.make()
    def test_closed_probe_forwards_original_only_and_never_accepts_requested_restore_value(self):
        program='''const assert=require('assert');let calls=[],saved=[];
const Uuid={generate:()=>'{aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa}'};
const Test={featureCreateBrowseSetting:c=>{calls.push(c);return {requestId:c.commandId,source:{original:'native-only'}};},saveObject:(v,n)=>saved.push({v,n})};
function objectKeysMatch(v,k){return JSON.stringify(Object.keys(v).sort())===JSON.stringify(k.sort());}
'''+probe_source()+'''
let c={schemaVersion:1,commandId:'a'.repeat(32),action:'feature-create-browse-setting',runId:'b'.repeat(32),ownerToken:'c'.repeat(64),operation:'restore'};
applyAndroidControlCommand(c);assert.equal(calls.length,1);assert.equal(saved[0].n,'feature-create-browse-setting.json');
assert.deepStrictEqual(saved[0].v.source,{original:'native-only'});applyAndroidControlCommand(c);assert.equal(calls.length,1);
applyAndroidControlCommand({...c,commandId:'d'.repeat(32),value:'requested replacement'});assert.equal(calls.length,1);
applyAndroidControlCommand({...c,commandId:'e'.repeat(32),operation:'write'});assert.equal(calls.length,1);
'''
        subprocess.run(['node','-e',program],check=True,timeout=5)


if __name__=='__main__':unittest.main()
