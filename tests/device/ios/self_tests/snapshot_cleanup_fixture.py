"""Actual private capture IO and weak jobs; native/SDK boundary modeled."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import base64
import hashlib
import json
import os
import stat as stat_mode
import uuid
import weakref
from adapters.native_clock_join import NativeClockAcquisition
from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState
from ios.adapters import feature_observation,snapshot_owned_files as owned_source,snapshot_file_work as work_source
from ios.adapters.snapshot_manifest import SnapshotManifest,FILE as MANIFEST_FILE
from ios.adapters.snapshot_owned_packet import SnapshotOwnedPacket
from ios.adapters.snapshot_file_work_packet import SnapshotFileWorkPacket
from ios.adapters.snapshot_remove_owner import SnapshotRemoveOwner,RECEIPT
from ios.self_tests.test_ios_snapshot_owned_packet import SnapshotOwnedPackets
from ios.self_tests.test_ios_snapshot_owned_files import RUN,PREFIX
from ios.self_tests.test_ios_snapshot_file_work import Jobs,Token
from unittest.mock import patch


class CleanupDomain:
    def __init__(self,case):
        self.f=SnapshotOwnedPackets();self.f.setUp();case.addCleanup(self.f.doCleanups)
        self.f.model.prefixes=[];self.jobs=Jobs();self.jobs.tick=self.f.model.tick;self.jobs.clock=self.f.model.clock
        self.reads=[];self.remove_callbacks=[];self.raws={};self.manifest_index=self.work_index=self.owned_index=0;self.removals=[]
        self.commands=[];self.hold_reads=False;self.ignore_list=False;self.adopted=set()
        actual=patch.object(feature_observation,'post_request',self.post);actual.start();case.addCleanup(actual.stop)
        self.f.transport.execute=self.execute
    def file_rows(self,prefix):
        result=[]
        for path in sorted(self.f.root.glob(prefix+'-snap_*')):
            stat=path.lstat();need(stat_mode.S_ISREG(stat.st_mode) and stat.st_nlink==1)
            fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
            try:
                with os.fdopen(fd,'rb',closefd=False) as stream:raw=stream.read()
                need(os.fstat(fd)==stat and path.lstat()==stat)
            finally:os.close(fd)
            revision=hashlib.sha256(str((stat.st_dev,stat.st_ino,stat.st_size,stat.st_mtime_ns,stat.st_ctime_ns,stat.st_nlink)).encode()).hexdigest()
            result.append(dict(name=path.name,size=len(raw),revision=revision,sha256=hashlib.sha256(raw).hexdigest()))
        return result
    def list_body(self,q):
        token=Token();row=dict(id=uuid.uuid4().hex,query=deepcopy(q),queuedEpochMs=self.f.model.tick(),enteredEpochMs=None,
            returnedEpochMs=None,finallyEpochMs=None,expiredEpochMs=None,publication=None,publishedEpochMs=None,alive=True)
        self.jobs.jobs[row['id']]=(weakref.ref(token),row)
        def body():
            held=token;row['enteredEpochMs']=self.f.model.tick()
            try:
                if not self.ignore_list:
                    packet=dict(schemaVersion=1,commandId=q['commandId'],operation='list',prefix=q['prefix'],processId=42,
                        sampleEpochMs=self.f.model.tick(),ok=True,files=self.file_rows(q['prefix']))
                    if not self.f.model.prefixes:
                        self.f.model.prefixes=[dict(prefix=q['prefix'],query=deepcopy(q),sampleEpochMs=packet['sampleEpochMs'],initiallyEmpty=not packet['files'])]
                    for value in packet['files']:
                        for file in self.f.model.files.values():
                            if file['file']['name']==value['name'] and file['id'] not in self.adopted:
                                file.update(file=deepcopy(value),manifestQuery=deepcopy(q),observedEpochMs=packet['sampleEpochMs']);self.adopted.add(file['id'])
                    self.raws[MANIFEST_FILE]=json.dumps(packet)
                row.update(publication=True,publishedEpochMs=self.f.model.tick(),returnedEpochMs=self.f.model.tick())
            finally:row['finallyEpochMs']=self.f.model.tick();assert held is token
        body();self.reads.append(body)
    def post(self,request,timeout):
        q=self.f.transport.fixture.set_client_command(json.loads(request.data));self.commands.append(q);self.f.transport.echo=json.dumps(q).encode()
        if q['action']=='snapshot-files':self.list_body(q)
        elif q['action']==work_source.ACTION:self.raws[work_source.FILE]=json.dumps(self.jobs.read(q),separators=(',',':'))
        elif q['action']==owned_source.ACTION:self.raws[owned_source.FILE]=json.dumps(self.f.model.read(q),separators=(',',':'))
        elif q['action']==owned_source.REMOVE:
            file=self.f.model.files[q['fileId']];created,body=self.f.model.queued(file);old=created['commandId'];weak,row=self.f.model.jobs.pop(old)
            row['query']=deepcopy(q);file['removeCommandId']=q['commandId'];self.f.model.jobs[q['commandId']]=(weak,row)
            body();self.remove_callbacks.append(body)
            self.raws[RECEIPT]=json.dumps(dict(iosSnapshotFileRemoveReceiptVersion=1,requestId=q['commandId'],accepted=True))
        else:raise AssertionError('Unexpected fixture operation')
        return self.f.transport
    def execute(self,session,operation,args):
        assert operation=='mobile: pullFile';name=args['remotePath'].rsplit('/',1)[-1]
        return base64.b64encode(self.raws.get(name,'').encode()).decode()
    def clock(self):
        f=self.f
        return NativeClockAcquisition(f.native(),epoch_ms=lambda:f.model.now,monotonic=lambda:(f.model.now-10000)/1000)
    def manifest(self):
        self.manifest_index+=1;f=self.f
        owner=SnapshotManifest(PrivateFeatureState(f.root/('ios-snapshot-primary-manifest-'+format(self.manifest_index,'04d')+'.json')),
            f.lock,f.binding,RUN,'primary',self.manifest_index,f.feature,self.clock(),lambda:True)
        owner.reserve('still-png');owner.send(f.model.now);owner.recover();return owner
    def owned(self):
        self.owned_index+=1;owner=self.f.owner(self.owned_index);owner.reserve();owner.send();owner.retain();return owner
    def work(self):
        self.work_index+=1;f=self.f
        owner=SnapshotFileWorkPacket(PrivateFeatureState(f.root/('ios-snapshot-primary-native-filework-'+format(self.work_index,'04d')+'.json')),
            f.lock,f.binding,RUN,'primary',self.work_index,f.feature,f.native(),lambda:True,
            epoch_ms=lambda:f.model.now,monotonic=lambda:(f.model.now-10000)/1000)
        owner.reserve();owner.send();owner.retain();return owner
    def prepare(self,capture=True):
        self.manifest();self.reads.clear()
        if capture:
            file=self.f.model.capture();self.manifest();self.reads.clear();admission=self.owned();f=self.f
            remove=SnapshotRemoveOwner(PrivateFeatureState(f.root/'ios-snapshot-primary-remove-0001.json'),f.lock,f.binding,RUN,'primary',1,
                f.feature,f.native(),lambda:True,epoch_ms=lambda:f.model.now,monotonic=lambda:(f.model.now-10000)/1000)
            remove.reserve(admission,file['id']);remove.send();remove.acknowledge();self.remove_callbacks.clear()
            remove.observe(self.owned());self.removals=[remove]
    def group(self):
        manifest=self.manifest()
        if not self.hold_reads:self.reads.clear()
        work=self.work();owned=self.owned();return ([manifest],work,owned,self.removals)
