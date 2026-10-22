"""Separate receiver original evidence and command boundaries; no Android run."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT/'tests/device'),str(ROOT/'tests/device/adapters/android-phone')]
from overte_phone_snapshot_consumer import PhoneSnapshotConsumer,SnapshotConsumerTransport,PACKAGE,COMPONENT,AUTHORITY
from adapters.normal_ui import NativeUIError
RUN='a'*32;ARM='b'*32;COPY='c'*32

class Boundary:
    def __init__(self):
        self.epoch=100000;self.time=0;self.raw=b'original independent receiver bytes';self.sent=[];self.reads=[]
        self.identity=dict(package=PACKAGE,apkSha256='d'*64,uid=10002,processId=42,processIdentity='42:1234')
        uri='content://io.github.noah_be.overte.phone.snapshot.files/snapshots/original.png'
        self.original=dict(id=COPY,request=ARM,path='/data/user/0/'+PACKAGE+'/files/overte-snapshot-e2e-'+'1'*32+'/'+COPY+'.bin',phase='complete',bytes=len(self.raw),sha256=hashlib.sha256(self.raw).hexdigest(),capturedEpochMs=self.epoch-10)
        identity=dict(uri=uri,providerPackage='io.github.noah_be.overte.phone',providerUid=10001,receiverUid=10002,receiverPid=42,receiverPackage=PACKAGE,component=COMPONENT,readFlag=True,clipUri=uri,permissionAtOpen=True)
        self.source=dict(snapshotConsumerVersion=1,runId=RUN,armId=ARM,observationId='',instance='e'*32,sequence=0,capturedEpochMs=self.epoch,complete=True,phase='complete',activityAlive=False,cancelled=False,identity=identity,original=deepcopy(self.original),startedEpochMs=self.epoch-20,completedEpochMs=self.epoch-9,grantPresent=True,originalClosed=True,files=[deepcopy(self.original)],removedCopies=[],retired=False,workersTerminated=False,processId=42,receiverUid=10002,receiverPackage=PACKAGE)
        self.native=dict(request='2'*32,uri=uri,ownerUid=10001,component=COMPONENT,receiverUid=10002,chooserComponent='android/com.android.internal.app.ChooserActivity',chooserUid=1000,revokeId='',revokeIssued=False,granted=True,chooserGranted=True,checkedEpochMs=self.epoch)
    def observe(self,run,id):
        self.reads.append((run,id));self.source.update(observationId=id,sequence=self.source['sequence']+1,capturedEpochMs=self.epoch)
        return json.dumps(self.source).encode()
    def binary(self,run,copy,id):
        assert run==RUN and copy==COPY;self.reads.append((run,copy,id));return self.raw
    def control(self,operation,run,id):self.sent.append((operation,run,id));return {'accepted':True}
    def reader(self,read_only=True,binding=None):
        return PhoneSnapshotConsumer(self.observe,self.binary,self.control,lambda:deepcopy(self.identity),lambda:self.epoch,lambda:True,RUN,ARM,read_only=read_only,binding=binding,monotonic=lambda:self.time,sleep=lambda seconds:None)
    def retired(self):self.source.update(retired=True,workersTerminated=True,grantPresent=False,files=[],removedCopies=[COPY])

class SnapshotConsumerSourceTests(unittest.TestCase):
    def test_actual_binary_and_native_uri_uid_component_are_all_joined(self):
        value=Boundary();reader=value.reader();metadata,raw=reader.acquire(value.native,value.original)
        self.assertEqual(value.raw,raw);self.assertEqual('snapshot-receiver-original',metadata['source']);self.assertEqual(value.native['request'],metadata['request'])
        self.assertEqual(3,len(value.reads));self.assertEqual(3,len({row[-1] for row in value.reads}));self.assertFalse(value.sent)
    def test_chooser_ack_without_consumption_never_qualifies(self):
        for fault in ('armed','no-original','no-identity','open','no-permission'):
            value=Boundary()
            if fault=='armed':value.source.update(phase='armed',original=None,identity=None,startedEpochMs=0,completedEpochMs=0,files=[])
            elif fault=='no-original':value.source['original']=None
            elif fault=='no-identity':value.source['identity']=None
            elif fault=='open':value.source['originalClosed']=False
            else:value.source['identity']['permissionAtOpen']=False
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):value.reader().acquire(value.native,value.original)
    def test_foreign_native_uri_uid_or_component_never_qualifies(self):
        for field,foreign in (('uri','content://foreign.provider/image'),('ownerUid',10003),('receiverUid',10004),('component','foreign.package/foreign.Activity')):
            value=Boundary();value.native[field]=foreign
            with self.subTest(field=field),self.assertRaises(NativeUIError):value.reader().acquire(value.native,value.original)
    def test_changed_binary_or_capture_digest_never_qualifies(self):
        value=Boundary();value.raw=b'changed'
        with self.assertRaises(NativeUIError):value.reader().acquire(value.native,value.original)
        value=Boundary();capture=dict(value.original,sha256='0'*64)
        with self.assertRaises(NativeUIError):value.reader().acquire(value.native,capture)
    def test_old_packet_wrong_nonce_and_duplicate_json_are_rejected(self):
        for fault in ('old','nonce','duplicate'):
            value=Boundary();original=value.observe
            def read(run,id):
                raw=original(run,id)
                if fault=='old':row=json.loads(raw);row['capturedEpochMs']-=2000;return json.dumps(row).encode()
                if fault=='nonce':row=json.loads(raw);row['observationId']='f'*32;return json.dumps(row).encode()
                return raw[:-1]+b',"complete":true}'
            value.observe=read
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):value.reader().observe()
    def test_fresh_pid_uid_and_source_instance_cannot_be_replaced(self):
        for fault in ('uid','processId','instance','sha'):
            value=Boundary();reader=value.reader();reader.observe()
            if fault=='instance':value.source['instance']='f'*32
            elif fault=='sha':value.identity['apkSha256']='f'*64
            else:value.identity[fault]+=1
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):reader.observe()
    def test_durable_owner_binding_survives_host_reader_reconstruction(self):
        value=Boundary();reader=value.reader();reader.observe();binding=reader.binding()
        value.reader(binding=binding).observe()
        value.source['instance']='f'*32
        with self.assertRaises(NativeUIError):value.reader(binding=binding).observe()
        value.source['instance']='e'*32;value.identity['processIdentity']='42:5678'
        with self.assertRaises(NativeUIError):value.reader(binding=binding).observe()

    def test_cleanup_ack_or_pending_worker_grant_or_copy_never_retires(self):
        value=Boundary();reader=value.reader(False);reader.control('retire')
        with self.assertRaises(NativeUIError):reader.require_retired()
        for fault in ('activityAlive','grantPresent','files','originalClosed','workersTerminated'):
            value=Boundary();value.retired()
            if fault=='files':value.source['files']=[deepcopy(value.original)]
            elif fault in ('originalClosed','workersTerminated'):value.source[fault]=False
            else:value.source[fault]=True
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):value.reader().require_retired()
        value=Boundary();value.retired();value.reader().require_retired()
    def test_readonly_actor_cannot_arm_cancel_remove_or_retire(self):
        value=Boundary();reader=value.reader()
        for operation in ('arm','cancel','remove-copy','retire'):
            with self.subTest(operation=operation),self.assertRaises(NativeUIError):reader.control(operation,COPY if operation=='remove-copy' else '')
        self.assertFalse(value.sent)
        reader=value.reader(False)
        for operation in ('arm','cancel','remove-copy','retire'):reader.control(operation,COPY if operation=='remove-copy' else '')
        self.assertEqual([('arm',RUN,ARM),('cancel',RUN,''),('remove-copy',RUN,COPY),('retire',RUN,'')],value.sent)
    def test_original_or_file_cannot_change_between_binary_and_second_source(self):
        value=Boundary();read=value.observe
        def mutate(run,id):
            if value.reads:value.source['identity']['uri']='content://io.github.noah_be.overte.phone.snapshot.files/snapshots/replaced.png'
            return read(run,id)
        value.observe=mutate
        with self.assertRaises(NativeUIError):value.reader().acquire(value.native,value.original)

class FakeADB:
    def __init__(self):self.calls=[];self.pin='d'*64;self.pid='42:1234';self.path='/data/app/~~opaque/fixture/base.apk'
    def execute(self,args,**kwargs):
        self.calls.append((args,kwargs));command=args[-1]
        if command.startswith('pm path '):return 'package:'+self.path+'\n'
        if command.startswith('sha256sum '):return self.pin+'  '+self.path+'\n'
        if command.startswith('run-as '):return '10002\n'
        return 'Bundle[{accepted=true}]'
    def execute_bytes(self,args,**kwargs):self.calls.append((args,kwargs));return b'actual provider bytes'
    def process_state(self,*args):return dict(running=True,identity=self.pid)

class SnapshotConsumerTransportTests(unittest.TestCase):
    def test_fixed_provider_and_actual_installed_digest_uid_and_pid_route(self):
        adb=FakeADB();transport=SnapshotConsumerTransport(adb,'private-selector','d'*64,lambda:True)
        self.assertEqual(10002,transport.identity()['uid']);self.assertEqual(b'actual provider bytes',transport.read(RUN,'f'*32))
        self.assertEqual(['exec-out','content read --uri content://'+AUTHORITY+'/observations/'+RUN+'/'+'f'*32],adb.calls[-1][0])
        adb.pin='e'*64
        with self.assertRaises(NativeUIError):transport.identity()
    def test_control_requires_explicit_writer_and_only_closed_existing_ids(self):
        adb=FakeADB();reader=SnapshotConsumerTransport(adb,'private-selector','d'*64,lambda:True)
        with self.assertRaises(NativeUIError):reader.control('arm',RUN,ARM)
        writer=SnapshotConsumerTransport(adb,'private-selector','d'*64,lambda:True,read_only=False);writer.control('arm',RUN,ARM)
        calls=[row for row in adb.calls if row[0][-1].startswith('content call ')];self.assertEqual(1,len(calls))
        self.assertIn('--extra runId:s:'+RUN,calls[0][0][-1]);self.assertIn('--extra armId:s:'+ARM,calls[0][0][-1])
        for operation,id in (('replace-uri','x'),('remove-copy','/foreign/path'),('retire',COPY)):
            with self.subTest(operation=operation),self.assertRaises(NativeUIError):writer.control(operation,RUN,id)
        self.assertEqual(7,len(adb.calls))

if __name__=='__main__':unittest.main()
