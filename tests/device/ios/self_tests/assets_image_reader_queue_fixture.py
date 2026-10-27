"""Explicit two-source/Qt-event SDK model; no native Qt/C++ or device executes."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import weakref
from ios.adapters import assets_image_reader_queue as source
from ios.self_tests.assets_image_reader_fixture import Boundary as Source1Boundary,Holder,RUN


class ParentBoundary(Source1Boundary):
    """Fresh Source1 model producer with explicit observer callout points."""
    def __init__(self,owner,epoch,initial_monotonic):
        self.owner=owner
        super().__init__(epoch=epoch,initial_monotonic=initial_monotonic)

    def invoke(self,task,gpu,*,queued=True,accepted=True,before_return=False):
        row=dict(id=self.nonce(),taskId=task.id,branch='final-output',width=8,height=8,
            gpuKnown=gpu is not None,entered=self.stamp(),invokeReturned=None,invokeAccepted=None)
        self.value['dispatches'].append(row)
        self.weak_events[row['id']]=(weakref.ref(gpu) if gpu is not None else lambda:None,lambda:None)
        actual=self.owner.binding(task,row)
        prior=getattr(self.local,'dispatch',None);self.local.dispatch=row['id']
        try:
            if accepted:
                if queued:
                    event=Event(self.owner,actual,gpu)
                    self.queue.append(event)
                    if before_return:
                        self.queue.remove(event);event.deliver()
                else:self.receive(gpu)
            row.update(invokeReturned=self.stamp(),invokeAccepted=accepted)
            actual.update(invokeReturned=self.owner.stamp(),invokeAccepted=accepted)
        finally:self.local.dispatch=prior
        return row

    def receive(self,gpu):
        dispatch=getattr(self.local,'dispatch',None)
        row=dict(id=self.nonce(),resourceId='2'*32,width=8,height=8,gpuKnown=gpu is not None,sourceKnown=True,
            entered=self.stamp(),returned=None,unwound=None,dispatchId=dispatch,
            attribution='synchronous-invoke-scope' if dispatch else 'unavailable-queued-or-other-producer')
        self.value['receivers'].append(row)
        self.weak_events[row['id']]=(weakref.ref(gpu) if gpu is not None else lambda:None,weakref.ref(self.resource.source))
        actual=getattr(self.owner.local,'event',None)
        if actual is not None:
            actual['receiverId']=row['id'];actual['receiverEntered']=self.owner.stamp()
        row['returned']=self.stamp()
        if actual is not None:actual['receiverReturned']=self.owner.stamp()
        return row

    def deliver(self):
        pending,self.queue=self.queue,[]
        for event in pending:event.deliver()


class Event:
    def __init__(self,owner,row,gpu):
        self.owner,self.row,self.gpu=owner,row,gpu
        self.resource=weakref.ref(owner.parent.resource)
        owner.event_sequence+=1
        row['eventId']=owner.event_sequence;row['created']=owner.qt_stamp()

    def deliver(self,*,destroy=True):
        if self.resource() is None:
            self.destroy_arguments();return
        self.row['deliveryEntered']=self.owner.qt_stamp()
        previous=getattr(self.owner.local,'event',None);self.owner.local.event=self.row
        previous_dispatch=getattr(self.owner.parent.local,'dispatch',None)
        # A separate delivery thread has no producer-thread Source1 Dispatch TLS.
        self.owner.parent.local.dispatch=None
        try:self.owner.parent.receive(self.gpu)
        finally:
            self.owner.local.event=previous
            self.owner.parent.local.dispatch=previous_dispatch
        self.row['deliveryReturned']=self.owner.qt_stamp()
        if destroy:self.destroy_arguments()

    def destroy_arguments(self,*,publish=True):
        self.gpu=None
        self.original_destruction_clock=self.owner.qt_stamp()
        if publish:self.publish_destruction()

    def publish_destruction(self):
        if self.row['argumentValuesDestroyed'] is not None:raise RuntimeError('duplicate original destructor receipt')
        self.row['argumentValuesDestroyed']=deepcopy(self.original_destruction_clock)


class Boundary:
    def __init__(self,epoch=20000,initial_monotonic=0):
        import threading
        self.parent=ParentBoundary(self,epoch,initial_monotonic)
        self.epoch=epoch;self.sequence=0;self.event_sequence=0;self.raw='';self.queries=[];self.mutate=None;self.good=True
        self.local=threading.local();self.resource=weakref.ref(self.parent.resource)
        self.value=dict(assetImageReaderQueueHistoryVersion=1,instance='d'*32,source1Instance=self.parent.value['instance'],
            complete=True,clockDomain='native-assets-image-reader-queue-observer',clock=self.stamp(),
            qtClockDomain='qtcore-metacall-steady-nanoseconds',entries=[],**{key:False for key in source.UNAVAILABLE})

    @property
    def time(self):return self.parent.time
    @time.setter
    def time(self,value):self.parent.time=value
    def stamp(self):return self.parent.stamp()
    def qt_stamp(self):
        value=self.stamp()
        return dict(epochMs=value['epochMs'],steadyNs=str(800000000000000+self.time*1000000))

    def create(self):
        task=self.parent.create();self.parent.phase(task,'runEntered');self.parent.phase(task,'readEntered');return task

    def binding(self,task,dispatch):
        row=dict(dispatchId=dispatch['id'],taskId=task.id,resourceId='2'*32,methodIndex=37,
            **{key:None for key in source.PHASES+source.QT_PHASES})
        row.update(bindingEntered=self.stamp(),invokeAccepted=None,eventId=None,receiverId=None,receiverObjectAlive=True)
        self.value['entries'].append(row);return row

    def invoke(self,task,gpu,*,queued=True,accepted=True,before_return=False):
        return self.parent.invoke(task,gpu,queued=queued,accepted=accepted,before_return=before_return)

    def finish(self,task):
        self.parent.phase(task,'readReturned');self.parent.phase(task,'runReturned')

    def snapshot(self):
        value=deepcopy(self.value)
        for row in value['entries']:row['receiverObjectAlive']=self.resource() is not None
        value['clock']=self.stamp();return value

    def send(self,query):
        self.queries.append(deepcopy(query));self.sequence+=1;before=self.stamp();table=self.snapshot();after=self.stamp()
        value=dict(iosAssetsImageReaderQueueVersion=1,requestId=query['commandId'],runId=query['runId'],instance='c'*32,
            sequence=self.sequence,processId=42,clockDomain='native-main-assets-image-reader-queue',
            clockBefore=before,clockAfter=after,source=table)
        if self.mutate:self.mutate(value)
        self.raw=json.dumps(value)

    def reader(self):
        return source.IOSAssetsImageReaderQueue(self.send,lambda:self.raw,lambda:self.epoch+self.time,lambda:self.good,42,
            monotonic=lambda:self.time/1000,sleep=lambda seconds:setattr(self,'time',self.time+round(seconds*1000)))
