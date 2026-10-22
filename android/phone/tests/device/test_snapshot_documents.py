"""Independent SDK reader negatives with explicit synthetic provider transport."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
from io import BytesIO
import json
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT/'tests/device'),str(ROOT/'tests/device/adapters/android-phone')]
from adapters.normal_ui import NativeUIError
from overte_phone_snapshot_documents import PhoneSnapshotDocuments,SnapshotDocumentsTransport,source,continuity,PACKAGE,DOCUMENTS_AUTHORITY
from test_snapshot_documents_ui import Boundary as UI,NAME
RUN='a'*32;ARM='b'*32;DOC='doc-'+RUN+'-'+ARM+'-'+'c'*32;URI='content://'+DOCUMENTS_AUTHORITY+'/document/'+DOC


class Boundary:
    def __init__(self):
        from PIL import Image
        image=Image.new('RGB',(16,16),'red');image.putpixel((0,0),(0,0,255));out=BytesIO();image.save(out,format='PNG');self.bytes=out.getvalue()
        self.epoch=20000;self.clock=0.;self.okay=True;self.calls=[];self.seq=0;self.fault=lambda row:None
        self.identity_value=dict(package=PACKAGE,apkSha256='d'*64,uid=12000,processId=45,processIdentity='45:1234')
        self.document=dict(documentId=DOC,uri=URI,displayName=NAME,mimeType='image/png',createUid=10042,createdEpochMs=19000,device=7,inode=11,bytes=len(self.bytes),sha256=hashlib.sha256(self.bytes).hexdigest(),writerUid=11000,writeOpenedEpochMs=19001,writeClosedEpochMs=19002,deleteCalls=0,deletedEpochMs=0,absent=False,checkedEpochMs=0)
        self.plan={key:self.document[key] for key in ('documentId','createUid','createdEpochMs','displayName','mimeType')};self.plan['phase']='created'
        self.fd=dict(id='e'*32,documentId=DOC,mode='w',callerUid=11000,openedEpochMs=19001,closedEpochMs=19002,closed=True,error=False)
        self.root=dict(rootId='root-'+RUN,path='/data/user/0/'+PACKAGE+'/files/overte-snapshot-documents-'+RUN,device=7,inode=10,present=True,checkedEpochMs=20000)
        self.row=dict(snapshotDocumentsVersion=1,runId=RUN,armId=ARM,observationId='f'*32,instance='8'*32,sequence=1,capturedEpochMs=20000,processId=45,providerUid=12000,providerPackage=PACKAGE,complete=True,root=self.root,plans=[self.plan],documents=[self.document],fdLifetimes=[self.fd],retired=False,workersTerminated=False)
        self.native=dict(uri=URI,providerUid=12000,providerPackage=PACKAGE,ownerPackage=PACKAGE,displayName=NAME,device=7,inode=11,storage='documents',runId=RUN,armId=ARM,providerInstance='8'*32,documentId=DOC,createUid=10042,createdEpochMs=19000)
    def identity(self):return deepcopy(self.identity_value)
    def read(self,run,id):
        self.calls.append(('read',run,id));self.seq+=1;row=deepcopy(self.row);row.update(observationId=id,sequence=self.seq)
        self.fault(row);return json.dumps(row).encode()
    def binary(self,run,document,id):self.calls.append(('binary',run,document,id));return self.bytes
    def control(self,operation,run,arm):self.calls.append(('control',operation,run,arm))
    def sleep(self,value):self.clock+=value
    def reader(self,readonly=False,binding=None):return PhoneSnapshotDocuments(self,lambda:self.epoch,lambda:self.okay,RUN,ARM,read_only=readonly,binding=binding,monotonic=lambda:self.clock,sleep=self.sleep)
    def capture(self):return dict(bytes=len(self.bytes),sha256=hashlib.sha256(self.bytes).hexdigest())
    def retire_source(self):
        self.document.update(deleteCalls=1,deletedEpochMs=19900,absent=True,checkedEpochMs=20000)
        self.root['present']=False;self.row.update(retired=True,workersTerminated=True)


class SnapshotDocumentsTests(unittest.TestCase):
    def test_versioned_original_floor_rejects_metadata_only_binding_and_missing_retirement_history(self):
        b=Boundary();owner=b.reader();first=owner.observe();binding=owner.binding()
        self.assertEqual(2,binding['snapshotDocumentsBindingVersion']);self.assertEqual(first,binding['floor'])
        for fault in ('old','floor','provider','instance','root'):
            value=deepcopy(binding)
            if fault=='old':value.pop('snapshotDocumentsBindingVersion');value.pop('floor')
            elif fault=='floor':value['floor']={}
            elif fault=='provider':value['floor']['providerUid']+=1
            elif fault=='instance':value['floor']['instance']='9'*32
            else:value['floor']['root']['inode']+=1
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):b.reader(True,value)
        actor=b.reader(True,binding)
        b.row.update(plans=[],documents=[],fdLifetimes=[],retired=True,workersTerminated=True);b.root['present']=False
        # The imported original floor protects even the first current read.
        with self.assertRaises(NativeUIError):actor.require_retired()

    def test_actor_history_preserves_primary_floor_and_own_independent_rows_without_transport(self):
        b=Boundary();owner=b.reader();first=owner.observe();binding=owner.binding();actor=b.reader(True,binding)
        own=actor.observe();later=actor.observe();calls=deepcopy(b.calls)
        reconstructed=b.reader(True,binding);reconstructed.restore_history([binding['floor'],own,later])
        self.assertEqual(calls,b.calls);self.assertEqual(later,reconstructed.last)
        result=reconstructed.observe();self.assertGreater(result['sequence'],later['sequence'])
        self.assertNotEqual(result['observationId'],later['observationId'])
        self.assertEqual(result,reconstructed.binding()['floor'])
        missing=b.reader(True,binding)
        with self.assertRaises(NativeUIError):missing.restore_history([own,later])

    def test_reconstructed_reader_requires_original_history_before_retirement(self):
        b=Boundary();owner=b.reader();first=owner.observe();binding=owner.binding()
        actor=b.reader(True,binding);actor.restore_history([first])
        self.assertEqual(1,b.seq)  # Historical restoration sends no request.
        b.row.update(plans=[],documents=[],fdLifetimes=[],retired=True,workersTerminated=True);b.root['present']=False
        with self.assertRaises(NativeUIError):actor.require_retired()
        b=Boundary();owner=b.reader();first=owner.observe();actor=b.reader(True,owner.binding());actor.restore_history([first])
        b.retire_source();self.assertTrue(actor.require_retired()['workersTerminated'])
        with self.assertRaises(NativeUIError):actor.restore_history([first])

    def test_historical_rows_cannot_retime_replace_drop_or_replay_originals(self):
        for fault in ('sequence','instance','root','identity','nonce','drop'):
            b=Boundary();owner=b.reader();first=owner.observe();second=owner.observe();binding=owner.binding()
            if fault=='sequence':second['sequence']=first['sequence']
            elif fault=='instance':second['instance']='9'*32
            elif fault=='root':second['root']['inode']+=1
            elif fault=='identity':second['providerUid']+=1
            elif fault=='nonce':second['observationId']='invalid'
            else:second.update(plans=[],documents=[],fdLifetimes=[])
            actor=b.reader(True,binding)
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):actor.restore_history([first,second])
            self.assertIsNone(actor.last)
        b=Boundary();owner=b.reader();first=owner.observe();actor=b.reader(True,owner.binding());actor.restore_history([first])
        b.seq=0
        with self.assertRaises(NativeUIError):actor.observe()
        # Historical clock is used for validation only; a fresh read still needs
        # the real current epoch and a new provider sequence.
        b.epoch=30000
        with self.assertRaises(NativeUIError):actor.observe()

    def test_final_clock_cannot_hide_guard_loss_deadline_or_clock_regression(self):
        for operation in ('observe','retired'):
            for fault in ('guard','slow','regression'):
                b=Boundary();reader=b.reader();calls=[0]
                if operation=='retired':b.retire_source()
                def clock():
                    calls[0]+=1
                    if calls[0]==(3 if operation=='observe' else 4):
                        if fault=='guard':b.okay=False
                        else:b.clock=10 if fault=='slow' else -1
                    return b.epoch
                reader.clock_ms=clock
                with self.subTest(operation=operation,fault=fault),self.assertRaises(NativeUIError):
                    reader.observe() if operation=='observe' else reader.require_retired()

    def test_primary_and_independent_bound_actor_acquire_actual_decoded_bytes_and_original_completion(self):
        b=Boundary();primary=b.reader();first=primary.observe();actor=b.reader(True,primary.binding())
        for reader in (primary,actor):
            original,raw=reader.acquire(DOC,b.native,b.capture(),11000,UI().resolve())
            self.assertEqual(b.bytes,raw);self.assertEqual(19002,original['capturedEpochMs']);self.assertEqual(20000,original['acquiredEpochMs'])
            self.assertEqual('snapshot-document-original',original['source'])
        self.assertEqual([], [call for call in b.calls if call[0]=='control'])
        self.assertEqual(2,len({call[-1] for call in b.calls if call[0]=='binary'}))
        self.assertEqual(first['root']['inode'],actor.binding()['root']['inode'])
    def test_ignored_retirement_ack_live_fd_or_unfinished_root_never_qualifies(self):
        b=Boundary();reader=b.reader();reader.observe();reader.control('retire')
        with self.assertRaises(NativeUIError):reader.require_retired()
        b.retire_source();self.assertTrue(reader.require_retired()['workersTerminated'])
        for target in ('fd','root','worker','document'):
            b=Boundary();b.retire_source()
            if target=='fd':b.fd.update(closed=False,closedEpochMs=0)
            elif target=='root':b.root['present']=True
            elif target=='worker':b.row['workersTerminated']=False
            else:b.document['absent']=False
            with self.subTest(target=target),self.assertRaises(NativeUIError):b.reader().require_retired()
    def test_foreign_provider_process_run_arm_root_or_missing_result_cannot_supply_source(self):
        faults=[lambda v:v.update(runId='9'*32),lambda v:v.update(armId='9'*32),lambda v:v.update(processId=46),
            lambda v:v.update(providerUid=11000),lambda v:v.update(providerPackage='foreign.app'),lambda v:v.update(instance='bad'),
            lambda v:v['root'].update(path='/data/user/0/foreign/files/owned'),lambda v:v['root'].update(inode=0),
            lambda v:v['documents'].clear(),lambda v:v['documents'][0].update(uri='content://foreign/document/x'),
            lambda v:v['plans'][0].update(displayName='foreign.png'),lambda v:v['fdLifetimes'][0].update(callerUid=11001),
            lambda v:v.update(expected=True)]
        for index,fault in enumerate(faults):
            b=Boundary();b.fault=fault
            with self.subTest(index=index),self.assertRaises(NativeUIError):b.reader().observe()
    def test_prewrite_and_open_writer_are_original_states_and_never_written_file_evidence(self):
        for opened in (False,True):
            b=Boundary();b.document.update(bytes=0,sha256='',writeClosedEpochMs=0)
            b.fd.update(closed=False,closedEpochMs=0)
            if not opened:
                b.document.update(writerUid=0,writeOpenedEpochMs=0);b.row['fdLifetimes']=[]
            reader=b.reader();self.assertTrue(reader.observe()['complete'])
            with self.assertRaises(NativeUIError):reader.acquire(DOC,b.native,b.capture(),11000,UI().resolve())
            self.assertEqual([], [call for call in b.calls if call[0]=='binary'])
    def test_wrong_creator_writer_native_identity_or_capture_cannot_join_bytes(self):
        for target in ('creator','writer','provider','run','inode','hash','bytes','missing'):
            b=Boundary();native=deepcopy(b.native);capture=b.capture();id=DOC
            if target=='creator':native['createUid']=10043
            elif target=='writer':b.document['writerUid']=b.fd['callerUid']=11001
            elif target=='provider':native['providerUid']=11000
            elif target=='run':native['runId']='9'*32
            elif target=='inode':native['inode']=12
            elif target=='hash':capture['sha256']='0'*64
            elif target=='bytes':capture['bytes']+=1
            else:id=DOC[:-1]+'d'
            with self.subTest(target=target),self.assertRaises(NativeUIError):b.reader().acquire(id,native,capture,11000,UI().resolve())
    def test_actual_non_png_or_changed_binary_never_becomes_saved_evidence(self):
        for malformed in (b'not png',b'',b'old original'):
            b=Boundary();b.bytes=malformed
            b.document.update(bytes=len(malformed),sha256=hashlib.sha256(malformed).hexdigest())
            with self.subTest(raw=malformed),self.assertRaises(NativeUIError):b.reader().acquire(DOC,b.native,b.capture(),11000,UI().resolve())
    def test_stale_nonce_replay_slow_read_guard_loss_and_clock_regression_remain_red(self):
        for target in ('epoch','nonce','sequence','slow','guard','clock'):
            b=Boundary();reader=b.reader();reader.observe()
            def fault(row):
                if target=='epoch':row['capturedEpochMs']=18000
                elif target=='nonce':row['observationId']='7'*32
                elif target=='sequence':row['sequence']=1
                elif target=='slow':b.clock+=5
                elif target=='guard':b.okay=False
            b.fault=fault
            if target=='clock':b.clock=-1
            with self.subTest(target=target),self.assertRaises(NativeUIError):reader.observe()
    def test_original_rollback_replacement_or_lost_descriptors_are_rejected(self):
        for target in ('instance','root','document','fd','plan','resurrection'):
            b=Boundary();reader=b.reader();reader.observe()
            if target=='instance':b.row['instance']='9'*32
            elif target=='root':b.root['inode']=12
            elif target=='document':b.document['sha256']='0'*64
            elif target=='fd':b.row['fdLifetimes']=[]
            elif target=='plan':b.plan['createdEpochMs']+=1
            else:
                b.retire_source();reader.require_retired();b.root['present']=True;b.row.update(retired=False,workersTerminated=False)
            with self.subTest(target=target),self.assertRaises(NativeUIError):reader.observe()
    def test_readonly_actor_needs_original_binding_and_cannot_arm_or_retire(self):
        b=Boundary()
        with self.assertRaises(NativeUIError):b.reader(True)
        primary=b.reader();primary.observe();actor=b.reader(True,primary.binding())
        for operation in ('arm','retire'):
            with self.subTest(operation=operation),self.assertRaises(NativeUIError):actor.control(operation)
        self.assertEqual([], [call for call in b.calls if call[0]=='control'])
    def test_os_observer_factory_preserves_current_share_scope_and_original_doc_binding_readonly(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        from appium_adapter import PhoneAppiumAdapter
        from artifact_identity import IdentityError
        b=Boundary();primary=b.reader();primary.observe();binding=primary.binding()
        adapter=PhoneAppiumAdapter.__new__(PhoneAppiumAdapter);adapter.candidate=object();scopes=[]
        share=dict(snapshotChooserResolutionVersion=1,component='android/com.android.internal.app.ChooserActivity')
        application=dict(processIdentity='31:1');authority=lambda:True
        def scope(*args):scopes.append(args);return SimpleNamespace(guard=authority)
        adapter._snapshot_system_context=scope
        adapter.target=lambda _selector:dict(appId='io.github.noah_be.overte.phone',capabilities={'appium:udid':'explicit-synthetic-only'})
        sdk=SimpleNamespace(epoch_milliseconds=lambda _device:b.epoch)
        with patch('appium_adapter.PhoneAdapter',return_value=SimpleNamespace(adb=sdk)),patch('overte_phone_snapshot_documents.SnapshotDocumentsTransport',return_value=b) as transport:
            observer=adapter._snapshot_system_documents('own',RUN,ARM,'d'*64,application,share,authority,binding=binding)
            observed=observer.observe();self.assertIs(scopes[0][2],share)
            self.assertEqual(binding['floor'],observer.floor);self.assertEqual(observed,observer.binding()['floor'])
            self.assertEqual({key:value for key,value in binding.items() if key!='floor'},{key:value for key,value in observer.binding().items() if key!='floor'})
            self.assertTrue(transport.call_args.kwargs['read_only'])
            for operation in ('arm','retire'):
                with self.subTest(operation=operation),self.assertRaises(NativeUIError):observer.control(operation)
            with self.assertRaises(IdentityError):adapter._snapshot_system_documents('own','f'*32,ARM,'d'*64,application,share,authority,binding=binding)
        self.assertFalse([call for call in b.calls if call[0]=='control'])
    def test_transient_reserved_fd_can_complete_but_permanent_failure_cannot_turn_green(self):
        b=Boundary()
        def pending(row):
            if b.seq==1:
                row['complete']=False;row['documents'][0].update(writerUid=0,writeOpenedEpochMs=0,writeClosedEpochMs=0,bytes=0,sha256='')
                row['fdLifetimes'][0].update(openedEpochMs=0,closedEpochMs=0,closed=False)
        b.fault=pending;self.assertTrue(b.reader().observe()['complete']);self.assertEqual(2,b.seq)
        b=Boundary();b.fault=lambda row:row.update(complete=False)
        with self.assertRaises(NativeUIError):b.reader().observe()
        self.assertLessEqual(b.clock,5.1)
    def test_total_binary_acquisition_budget_and_postread_provider_change_are_checked(self):
        for fault in ('slow','provider'):
            b=Boundary();original=b.binary
            def binary(*args):
                result=original(*args)
                if fault=='slow':b.clock+=5
                else:b.identity_value['processIdentity']='45:9999'
                return result
            b.binary=binary
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):b.reader().acquire(DOC,b.native,b.capture(),11000,UI().resolve())

    def test_docs_transport_uses_only_disjoint_evidence_routes_and_closed_control(self):
        b=Boundary();transport=SnapshotDocumentsTransport(object(),'synthetic','a'*64,lambda:True,read_only=False)
        calls=[];transport._execute=lambda *args,**kwargs:calls.append((args,kwargs)) or b'actual-route-boundary'
        transport._installed=lambda:('a'*64,12000)
        transport.control('arm',RUN,ARM);transport.read(RUN,'1'*32);transport.binary(RUN,DOC,'2'*32);transport.control('retire',RUN)
        self.assertIn('documents-arm',calls[0][0]);self.assertIn('/documents-observations/',calls[1][0][-1]);self.assertIn('/documents-originals/',calls[2][0][-1]);self.assertIn('documents-retire',calls[3][0])
        for operation in ('delete','remove-copy','cancel'):
            with self.subTest(operation=operation),self.assertRaises(NativeUIError):transport.control(operation,RUN)
        with self.assertRaises(NativeUIError):transport.binary(RUN,'../../foreign','3'*32)


if __name__=='__main__':unittest.main()
