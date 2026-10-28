"""Explicit SDK pool protocol model, real host weak markers/allocator blocks.

Private Slot identity models allocator reuse. Nothing here executes Qt threads,
C++ deleting destructors, the SDK patch or any physical device.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import gc,json,uuid
from ios.adapters import assets_image_reader_pool as source
from ios.self_tests import assets_image_storage_fixture as storage
from ios.self_tests.assets_image_reader_queue_fixture import Holder
from ios.self_tests.assets_image_reader_lifecycle_fixture import Resource
from ios.self_tests.assets_reply_fixture import EPOCH,RUN
from ios.self_tests import assets_image_processing_fixture as processing


class Observer:
    def __init__(self,host):
        self.host=host;self.instance=uuid.uuid4().hex;self.registrations=[];self.bindings=[];self.admissions=[];self.events=[]
        self.live_slots={};self.healthy=True;self.hold_iteration=True;self.pending_iterations=[];self.hidden=set();self.cut_complete=True
        self.sequence=0;self.queries=[];self.raw='';self.mutate=None;self.operations=0;self.slot_counter=0
        self.event(1,pool=1)
    def phase(self):return dict(epochMs=self.host.tick(),monotonicMs=self.host.elapsed)
    def steady(self):return str(900000000000000+self.host.elapsed*1000000)
    def event(self,kind,*,pool=0,reg=0,admission=0,slot=0,operation=0,flags=0,thread=1):
        original=self.phase();row=dict(sequence=len(self.events)+1,kind=kind,poolId=pool,registrationId=reg,admissionId=admission,
            slotId=slot,threadSlotId=thread,operationId=operation,epochMs=original['epochMs'],steadyNs=self.steady(),flags=flags)
        self.events.append(row);return row
    def register(self,slot,row,task):
        if slot in self.live_slots:self.healthy=False;return
        rid=len(self.registrations)+1;self.live_slots[slot]=rid
        self.registrations.append(dict(id=rid,allocationId=row['id'],live=True));self.event(3,reg=rid)
        self.bindings.append(dict(registrationId=rid,allocationId=row['id'],taskId=task.id,resourceId=task.resourceId,attached=self.phase()))
    def admitted(self,slot,mode='worker'):
        rid=self.live_slots[slot];aid=len(self.admissions)+1;kind=8 if mode=='declined' else 5
        self.admissions.append(dict(id=aid,poolId=1,registrationId=rid,operation=kind));self.event(kind,pool=1,reg=rid,admission=aid)
        if mode in ('clear','take','steal','promote'):
            self.enqueue(aid)
        if mode in ('worker','promote'):
            if mode=='promote':
                # A private promotion can enqueue a new physical queue slot
                # before removing the old slot. Both retain the same admission.
                self.enqueue(aid);self.remove(aid,1,4);self.remove(aid,2,1)
            self.event(16,pool=1,reg=rid,admission=aid);self.event(17,pool=1,reg=rid,admission=aid,flags=3,thread=2)
        if mode in ('take','steal'):
            self.take(slot,aid,1)
            if mode=='steal':self.event(17,pool=1,reg=rid,admission=aid,flags=5,thread=1)
        self.event(kind+1,pool=1,reg=rid,admission=aid,flags=0 if mode=='declined' else 1)
    def enqueue(self,aid):
        row=self.admissions[aid-1];self.slot_counter+=1
        self.event(14,pool=1,reg=row['registrationId'],admission=aid,slot=self.slot_counter)
    def remove(self,aid,sid,reason,thread=1):
        row=self.admissions[aid-1];self.event(15,pool=1,reg=row['registrationId'],admission=aid,slot=sid,flags=reason,thread=thread)
    def take(self,slot,aid=0,sid=0):
        self.operations+=1;oid=self.operations;rid=self.live_slots.get(slot,0)
        if not rid:return
        self.event(28,pool=1,reg=rid,operation=oid)
        if aid:
            actual=self.admissions[aid-1]
            if actual['registrationId']!=rid:self.healthy=False
            self.remove(aid,sid,3);self.event(31,pool=1,reg=actual['registrationId'],admission=aid,slot=sid,operation=oid)
        self.event(29,pool=1,reg=rid,admission=aid,operation=oid,flags=bool(aid)*1)
    def before_destructor(self,slot):
        rid=self.live_slots.get(slot);mode=self.host.pool_mode
        if not rid:return
        aid=next(row['id'] for row in self.admissions if row['registrationId']==rid)
        thread=1 if mode in ('take','steal','declined') else 2
        if mode in ('worker','promote','steal'):
            self.event(18,pool=1,reg=rid,admission=aid,thread=thread);self.event(20,pool=1,reg=rid,admission=aid,thread=thread)
        elif mode=='clear':
            self.remove(aid,self.slot_counter,2,thread=2);self.event(24,pool=1,reg=rid,admission=aid,thread=thread)
    def retire(self,slot):
        rid=self.live_slots.pop(slot);self.registrations[rid-1]['live']=False;self.event(4,reg=rid,thread=1 if self.host.pool_mode in ('take','steal','declined') else 2)
    def delete_returned(self,allocation):
        rid=next(row['id'] for row in self.registrations if row['allocationId']==allocation)
        aid=next(row['id'] for row in self.admissions if row['registrationId']==rid);mode=self.host.pool_mode
        if mode in ('take','declined'):return
        kind=25 if mode=='clear' else 21;thread=1 if mode=='steal' else 2
        self.event(kind,pool=1,reg=rid,admission=aid,thread=thread)
        tail=(26 if mode=='clear' else 22,rid,aid,thread)
        if self.hold_iteration:self.pending_iterations.append(tail)
        else:self.publish_iteration(tail)
    def publish_iteration(self,tail):
        kind,rid,aid,thread=tail;self.event(kind,pool=1,reg=rid,admission=aid,thread=thread)
    def release_iterations(self):
        pending,self.pending_iterations=self.pending_iterations,[]
        for row in pending:self.publish_iteration(row)
    def snapshot(self):
        original=self.phase()
        qt=dict(qtRunnablePoolProtocolVersion=1,instance=self.instance,clockDomain='qtcore-runnable-pool-steady-nanoseconds',
            epochMs=original['epochMs'],steadyNs=self.steady(),healthy=self.healthy,cutComplete=self.cut_complete and not self.hidden,
            mutationSerial=len(self.events)*2,inFlight=0,poolCount=1,reservedRegistrations=len(self.registrations),
            reservedAdmissions=len(self.admissions),reservedEvents=len(self.events),registrations=deepcopy(self.registrations),
            admissions=deepcopy(self.admissions),events=[deepcopy(row) for row in self.events if row['sequence'] not in self.hidden])
        return dict(assetImageReaderPoolHistoryVersion=1,instance=self.instance,source1Instance=self.host.images.parent.value['instance'],
            complete=True,clockDomain='native-assets-image-reader-pool',clock=self.phase(),bindings=deepcopy(self.bindings),qt=qt,
            **{key:False for key in source.UNAVAILABLE})
    def send(self,query):
        self.queries.append(deepcopy(query));self.sequence+=1;before=self.phase();history=self.snapshot();after=self.phase()
        packet=dict(iosAssetsImageReaderPoolVersion=1,requestId=query['commandId'],runId=query['runId'],instance='7'*32,sequence=self.sequence,
            processId=42,clockDomain='native-main-assets-image-reader-pool',clockBefore=before,clockAfter=after,source=history)
        if self.mutate:self.mutate(packet)
        self.raw=json.dumps(packet)
    def reader(self):
        h=self.host;return source.IOSAssetsImageReaderPool(self.send,lambda:self.raw,h.clock,lambda:h.live,42,monotonic=h.monotonic,sleep=h.sleep)


class StorageObserver(storage.Observer):
    def attach(self,slot,task):
        super().attach(slot,task)
        self.host.pool.register(slot,self.rows[self.addresses[slot]],task)
    def destructor(self,slot):self.host.pool.before_destructor(slot);super().destructor(slot)
    def deleting(self,slot):
        index=super().deleting(slot)
        if index is not None:self.host.pool.retire(slot)
        return index
    def deleted(self,index,original=None,publish=True):
        super().deleted(index,original,publish)
        if index is not None and publish:self.host.pool.delete_returned(self.rows[index]['id'])


class Parent(storage.Parent):
    def create(self):
        task=super().create();self.host.pool.admitted(task._storage_slot,self.host.pool_mode);return task


class ImageBoundary(storage.ImageBoundary):
    def __init__(self,host):
        super().__init__(host);self.parent=Parent(self,host);self.value['source1Instance']=self.parent.value['instance']


class Boundary(storage.Boundary):
    def __init__(self,epoch=EPOCH,mode='worker'):
        self.epoch=epoch;self.elapsed=100;self.live=True;self.hold_test_input=False;self.test_input_buffers={};self.cache_only=False
        self.source_owner_ids={};self.texture_revision=2;self.origin_history_instance='2'*32;self.pool_mode=mode
        self.processing=processing.Observer(self);self.pool=Observer(self);self.storage=StorageObserver(self);self.allocator=storage.Allocator(self.storage)
        self.images=ImageBoundary(self);sharing=Holder();sharing._sharing_owner_token=object();self.source_owner_ids[sharing._sharing_owner_token]='9'*32
        self.resources=[Resource(sharing)];self.images.parent.resource=self.resources[0];self.images.parent.lease=self.resources[0].lease
        self.task=self.images.create();self.task_id=self.task.id;self.slot=self.task._storage_slot;self.gpu=Holder()
        self.images.invoke(self.task,self.gpu);self.images.finish(self.task);self.images.parent.deliver()
        self.reader=self.pool.reader();self.storage_reader=self.storage.reader();self.parent=self.images.parent.reader()
    def read(self):
        packet=self.reader.read(RUN,storage=self.storage_reader,source1=self.parent)
        return packet,self.reader.storage_original,self.reader.parent_original
