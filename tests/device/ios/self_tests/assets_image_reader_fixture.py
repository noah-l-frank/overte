"""Explicit ImageReader/Qt boundary model, not native C++ or Qt execution."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
import threading
import weakref
from ios.adapters import assets_image_reader as source

RUN='a'*32


class Holder:pass


class DerivedTask:
    def __init__(self):
        self.marker=Holder();self.buffer=Holder();self.buffer.data=b'original input';self.base=Holder()
    def __del__(self):
        # Model only: original derived fields release before its marker. Base
        # and independently retained input storage are separate live objects.
        self.buffer=None;self.marker=None


class Boundary:
    def __init__(self,epoch=20000,initial_monotonic=0):
        self.epoch=epoch;self.time=initial_monotonic;self.sequence=0;self.identities=0;self.raw='';self.queries=[];self.mutate=None;self.good=True
        self.resource=Holder();self.resource.source=Holder();self.lease=Holder();self.local=threading.local();self.queue=[];self.weak_tasks={};self.weak_events={}
        self.value=dict(assetImageReaderHistoryVersion=1,instance='f'*32,complete=True,clockDomain='native-assets-image-reader-observer',
            clock=self.stamp(),tasks=[],dispatches=[],receivers=[],**{key:False for key in source.UNAVAILABLE})
    def nonce(self):self.identities+=1;return format(self.identities,'032x')
    def stamp(self):self.time+=1;return dict(epochMs=self.epoch+self.time,monotonicMs=self.time)
    def create(self):
        task=DerivedTask();url=b'https://user:fixture-secret@example.invalid/image.png?token=fixture-token'
        row=dict(id=self.nonce(),resourceId='2'*32,resourceUrlFullyEncodedBytes=len(url),
            resourceUrlFullyEncodedSha256=hashlib.sha256(url).hexdigest(),constructorContentBytes=len(task.buffer.data),
            **{key:None for key in source.PHASES})
        row.update(constructorEntered=self.stamp(),constructorReturned=self.stamp())
        self.value['tasks'].append(row)
        self.weak_tasks[row['id']]=(weakref.ref(task.marker),weakref.ref(self.lease),weakref.ref(self.resource),weakref.ref(self.resource.source))
        task.id=row['id'];return task
    def phase(self,task,name):
        row=next(row for row in self.value['tasks'] if row['id']==task.id);row[name]=self.stamp()
    def invoke(self,task,gpu,*,queued=True,accepted=True):
        row=dict(id=self.nonce(),taskId=task.id,branch='final-output',width=8,height=8,gpuKnown=gpu is not None,
            entered=self.stamp(),invokeReturned=None,invokeAccepted=None)
        self.value['dispatches'].append(row);self.weak_events[row['id']]=(weakref.ref(gpu) if gpu is not None else lambda:None,lambda:None)
        prior=getattr(self.local,'dispatch',None);self.local.dispatch=row['id']
        try:
            if accepted:
                if queued:self.queue.append(lambda:self.receive(gpu))
                else:self.receive(gpu)
            row.update(invokeReturned=self.stamp(),invokeAccepted=accepted)
        finally:self.local.dispatch=prior
        return row
    def receive(self,gpu):
        dispatch=getattr(self.local,'dispatch',None)
        row=dict(id=self.nonce(),resourceId='2'*32,width=8,height=8,gpuKnown=gpu is not None,sourceKnown=True,
            entered=self.stamp(),returned=None,unwound=None,dispatchId=dispatch,
            attribution='synchronous-invoke-scope' if dispatch else 'unavailable-queued-or-other-producer')
        row['returned']=self.stamp();self.value['receivers'].append(row)
        self.weak_events[row['id']]=(weakref.ref(gpu) if gpu is not None else lambda:None,weakref.ref(self.resource.source))
        return row
    def deliver(self):
        pending,self.queue=self.queue,[]
        for call in pending:call()
    def snapshot(self):
        value=deepcopy(self.value)
        for row in value['tasks']:
            for key,ref in zip(('derivedMarkerAlive','originalLeaseAlive','resourceObjectAlive','sourceOwnersAlive'),self.weak_tasks[row['id']]):row[key]=ref() is not None
        for name in ('dispatches','receivers'):
            for row in value[name]:
                gpu,current=self.weak_events[row['id']];row['gpuOwnersAlive']=gpu() is not None
                if name=='receivers':row['sourceOwnersAlive']=current() is not None
        value['clock']=self.stamp();return value
    def send(self,query):
        self.queries.append(deepcopy(query));self.sequence+=1;before=self.stamp();table=self.snapshot();after=self.stamp()
        value=dict(iosAssetsImageReaderVersion=1,requestId=query['commandId'],runId=query['runId'],instance='e'*32,
            sequence=self.sequence,processId=42,clockDomain='native-main-assets-image-reader',clockBefore=before,clockAfter=after,source=table)
        if self.mutate:self.mutate(value)
        self.raw=json.dumps(value)
    def reader(self):
        return source.IOSAssetsImageReader(self.send,lambda:self.raw,lambda:self.epoch+self.time,lambda:self.good,42,
            monotonic=lambda:self.time/1000,sleep=lambda seconds:setattr(self,'time',self.time+round(seconds*1000)))
