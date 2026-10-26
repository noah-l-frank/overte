"""Declared QObject/HTTP boundary with real private body FDs and weak stacks."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
from io import BytesIO
import os
from pathlib import Path
import stat
import tempfile
import time
import uuid
import weakref
from ios.adapters import snapshot_uploads as source

RUN='d'*32


class Lifetime:pass


def fact(value):
    return dict(device=str(value.st_dev),inode=str(value.st_ino),bytes=value.st_size,links=value.st_nlink,regular=stat.S_ISREG(value.st_mode),
        mtimeSeconds=str(value.st_mtime_ns//10**9),mtimeNanoseconds=value.st_mtime_ns%10**9,
        ctimeSeconds=str(value.st_ctime_ns//10**9),ctimeNanoseconds=value.st_ctime_ns%10**9)


class UploadDomain:
    def __init__(self,case):
        self.tmp=tempfile.TemporaryDirectory();case.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.root.chmod(0o700)
        self.path=self.root/('parity-'+RUN[:16]+'-still-png-snap_'+str(self.now())+'_1.png');self.path.write_bytes(b'Original body read through actual private FD');self.path.chmod(0o600)
        self.fd=os.open(self.path,os.O_RDONLY|os.O_NOFOLLOW);self.open_fds={self.fd};case.addCleanup(self.close)
        self.instance=uuid.uuid4().hex;self.sequence=0;self.mono=time.monotonic_ns()//10**6
        self.owner=uuid.uuid4().hex;self.events=[];self.resources={};self.live={};self.requests={};self.callbacks={};self.stacks={};self.weak_stacks={}
        self.received=BytesIO();self.send_count=0;self.health=True;self.current_generation=1;self.finished=False
        self.upload=dict(instance=self.owner,bornEpochMs=self.now(),privateName=True,fileName=self.path.name,fileNameSha256=hashlib.sha256(self.path.name.encode()).hexdigest(),
            requests=[],scopeGeneration='1',scopeActive=True)
        self.uploader=self.resource('uploader');self.event('begin');self.file=self.resource('file')
        row=self.resources[self.file];row.update(openObserved=True,opened=True,descriptor=self.fd,firstFile=fact(os.fstat(self.fd)))
        self.event('file-opened',resource=self.file,opened=True);self.multipart=self.resource('multipart')
    @staticmethod
    def now():return time.time_ns()//10**6
    def clock(self):return dict(epochMs=self.now(),monotonicMs=time.monotonic_ns()//10**6-self.mono)
    def event(self,kind,**detail):self.events.append(dict(sequence=len(self.events)+1,upload=self.owner,kind=kind,capturedEpochMs=self.now(),detail=detail))
    def scope_event(self,kind,error=False):self.event(kind,scopeGeneration=str(self.current_generation),scopeActive=self.upload['scopeActive'],finished=self.finished,error=error)
    def resource(self,kind):
        identifier=uuid.uuid4().hex;obj=Lifetime();self.live[identifier]=obj
        row=dict(instance=identifier,upload=self.owner,kind=kind,bornEpochMs=self.now(),destroyedEpochMs=None,alive=True,
            openObserved=False,opened=False,descriptor=-1,firstFile={},fdBefore=dict(state='unobserved',file={}),fdAfter=dict(state='unobserved',file={}))
        def gone(_weak):row.update(alive=False,destroyedEpochMs=self.now());self.event('resource-destroyed',resource=identifier)
        self.resources[identifier]=row;row['_weak']=weakref.ref(obj,gone);self.event('resource-created',resource=identifier);return identifier
    def request(self,stage,observer_failure=False):
        self.current_generation+=1;self.upload.update(scopeGeneration=str(self.current_generation),scopeActive=True)
        for row in self.requests.values():row['active']=False
        identifier=uuid.uuid4().hex;row=dict(instance=identifier,upload=self.owner,stage=stage,issuedEpochMs=self.now(),generation=str(self.current_generation),active=True,diagnosticsComplete=True,reply='')
        self.requests[identifier]=row;self.upload['requests'].append(identifier);self.event('ticket-issued',request=identifier)
        reply=self.resource('reply');self.resource('reply-timer');row['reply']=reply
        self.event('reply-created',request=identifier,reply=reply,endpoint='/api/v1/snapshots' if stage=='upload' else '/api/v1/user_stories',scheme='https',
            hostSha256=hashlib.sha256(b'controlled.invalid').hexdigest(),port=443,authorizationPresent=True,operation=4)
        try:
            if observer_failure:raise RuntimeError('Declared passive observer failure')
        except RuntimeError:self.health=False;row['diagnosticsComplete']=False
        self.send_count+=1
        if stage=='upload':
            while True:
                part=os.read(self.fd,65536)
                if not part:break
                self.received.write(part)
        self.event('reply-finished',request=identifier,reply=reply,status=200,networkError=0,ticketActive=True);return identifier
    def callback(self,request,*,leave=True):
        sent=self.requests[request];identifier=uuid.uuid4().hex;marker=Lifetime();self.stacks[identifier]=marker;self.weak_stacks[identifier]=weakref.ref(marker)
        row=dict(instance=identifier,upload=self.owner,method=sent['stage']+'-success',reply=sent['reply'],enteredEpochMs=self.now(),leftEpochMs=None,
            finishedAtEntry=False,scopeGeneration=sent['generation'],scopeActiveAtEntry=True,request=request,requestGeneration=sent['generation'],requestActiveAtEntry=True,stackAlive=True)
        self.callbacks[identifier]=row;self.event('callback-enter',callback=identifier)
        response=BytesIO(b'{"actual":"'+sent['stage'].encode()+b' response"}');original=response.read()
        self.event('response-original',reply=sent['reply'],byteCount=len(original),sha256=hashlib.sha256(original).hexdigest())
        if leave:row['leftEpochMs']=self.now();self.event('callback-left',callback=identifier)
        self.stacks.pop(identifier);del marker
    def complete(self,*,close_fd=True,leave=True,observer_failure=False):
        first=self.request('upload',observer_failure=observer_failure);self.callback(first,leave=leave)
        second=self.request('story');self.callback(second)
        self.scope_event('completion-entry');self.finished=True;self.scope_event('completion-issued')
        self.upload['scopeActive']=False
        for row in self.requests.values():row['active']=False
        if close_fd:self.close_fd(self.fd)
        for identifier in tuple(self.live):self.live.pop(identifier)
    def close_fd(self,descriptor):
        if descriptor in self.open_fds:os.close(descriptor);self.open_fds.remove(descriptor)
    def close(self):
        for descriptor in tuple(self.open_fds):self.close_fd(descriptor)
    def fd_fact(self,row):
        if row['kind']!='file':return dict(state='unobserved',file={})
        try:value=fact(os.fstat(row['descriptor']))
        except OSError as error:return dict(state='absent' if error.errno==9 else 'unknown',file={})
        return dict(state='present' if value==row['firstFile'] else 'changed',file=value)
    def observe(self):
        self.sequence+=1;before=self.clock();resources=[]
        for value in self.resources.values():
            row=deepcopy({key:item for key,item in value.items() if key!='_weak'});row.update(fdBefore=self.fd_fact(row),fdAfter=self.fd_fact(row));resources.append(row)
        callbacks=[]
        for identifier,value in self.callbacks.items():row=deepcopy(value);row['stackAlive']=self.weak_stacks[identifier]() is not None;callbacks.append(row)
        after=self.clock();nonce='ios-'+uuid.uuid4().hex
        return dict(iosSnapshotUploadsVersion=1,requestId=nonce,runId=RUN,instance=self.instance,sequence=self.sequence,processId=42,clockDomain='native-main-snapshot-uploads',clockBefore=before,clockAfter=after,
            source=dict(complete=self.health,uploads=[deepcopy(self.upload)],resources=resources,requests=deepcopy(list(self.requests.values())),callbacks=callbacks,
                events=deepcopy(self.events),activity=dict(slots=int(self.uploader in self.live),alive=int(self.uploader in self.live)),transportFDObservationRequired=True))
