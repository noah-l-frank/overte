"""Declared C++ allocation/deletion model with actual independent host blocks.

A private Slot models an allocator address, never an exported identity. Weak
Python markers and held bytearray-containing Blocks are real host objects; this
does not execute native new/delete, Qt destruction, a pool or a physical device.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import gc,json,uuid,weakref
from unittest.mock import patch
from ios.adapters import assets_image_reader_storage as source
from ios.self_tests import assets_image_processing_fixture as processing
from ios.self_tests import assets_image_reader_fixture as source1_fixture
from ios.self_tests.assets_image_reader_queue_fixture import Holder
from ios.self_tests.assets_image_reader_lifecycle_fixture import Resource
from ios.self_tests.assets_reply_fixture import EPOCH,RUN


class Slot:pass
class Block:
    def __init__(self,bytes_):self.bytes=bytearray(bytes_)


class Observer:
    def __init__(self,host):
        self.host=host;self.instance=uuid.uuid4().hex;self.rows=[];self.addresses={};self.markers={}
        self.sequence=0;self.queries=[];self.raw='';self.mutate=None;self.failed=False;self.armed=True;self.buffered=[]
    def phase(self,worker=False):
        return dict(epochMs=self.host.tick(),monotonicMs=self.host.elapsed,threadContextId=('3' if worker else '1')*32)
    def entering(self,bytes_):
        if not self.armed or self.failed:return None
        row=dict(id=uuid.uuid4().hex,storageBytes=bytes_,taskId='',resourceId='',sizedDelete=None,
            **{key:None for key in source.PHASES});row['allocationEntered']=self.phase();self.rows.append(row)
        return len(self.rows)-1
    def returned(self,index,slot):
        if index is None:return
        if slot in self.addresses:self.failed=True;return
        self.rows[index]['allocationReturned']=self.phase();self.addresses[slot]=index
    def threw(self,index):
        if index is not None:self.rows[index]['allocationThrew']=self.phase()
    def attach(self,slot,task):
        index=self.addresses[slot];row=self.rows[index]
        row.update(taskId=task.id,resourceId=task.resourceId,sourceAttached=self.phase());self.markers[row['id']]=weakref.ref(task.marker)
    def destructor(self,slot):
        if not self.armed:return
        self.rows[self.addresses[slot]]['destructorBodyEntered']=self.phase(True)
    def deleting(self,slot):
        if not self.armed:return None
        index=self.addresses.pop(slot,None)
        if index is None:self.failed=True;return None
        self.rows[index].update(deleteEntered=self.phase(True),sizedDelete=True)
        return index # Captured generation, no Slot/address lookup after release.
    def deleted(self,index,original=None,publish=True):
        if index is None or not self.armed:return
        original=self.phase(True) if original is None else deepcopy(original)
        if not publish:self.buffered.append((index,original));return
        if self.rows[index]['deleteReturned'] is not None:self.failed=True;return
        self.rows[index]['deleteReturned']=original
    def publish_returns(self):
        rows,self.buffered=self.buffered,[]
        for index,original in rows:self.deleted(index,original)
    def disarm(self):self.failed=True;self.armed=False
    def snapshot(self):
        return dict(assetImageReaderStorageHistoryVersion=1,instance=self.instance,source1Instance=self.host.images.parent.value['instance'],
            complete=self.armed and not self.failed,clockDomain='native-assets-image-reader-storage',
            clock=dict(epochMs=self.host.tick(),monotonicMs=self.host.elapsed),
            allocations=[dict(deepcopy(row),derivedMarkerAlive=self.markers[row['id']]() is not None if row['id'] in self.markers else False) for row in self.rows],
            **{key:False for key in source.UNAVAILABLE})
    def send(self,query):
        self.queries.append(deepcopy(query));self.sequence+=1;before=dict(epochMs=self.host.tick(),monotonicMs=self.host.elapsed)
        history=self.snapshot();after=dict(epochMs=self.host.tick(),monotonicMs=self.host.elapsed)
        packet=dict(iosAssetsImageReaderStorageVersion=1,requestId=query['commandId'],runId=query['runId'],instance='6'*32,
            sequence=self.sequence,processId=42,clockDomain='native-main-assets-image-reader-storage',clockBefore=before,clockAfter=after,source=history)
        if self.mutate:self.mutate(packet)
        self.raw=json.dumps(packet)
    def reader(self):
        h=self.host
        return source.IOSAssetsImageReaderStorage(self.send,lambda:self.raw,h.clock,lambda:h.live,42,monotonic=h.monotonic,sleep=h.sleep)


class Allocator:
    def __init__(self,observer):self.observer=observer;self.blocks={};self.paused=False;self.pending=[];self.buffer_returns=False
    def allocate(self,slot=None):
        slot=Slot() if slot is None else slot;index=self.observer.entering(256);self.blocks[slot]=Block(256)
        self.observer.returned(index,slot);return slot
    def failed_allocation(self):
        index=self.observer.entering(256)
        try:raise MemoryError('Declared failed native allocation; no block created')
        except MemoryError:self.observer.threw(index)
    def delete(self,slot):
        index=self.observer.deleting(slot)
        if self.paused:self.pending.append((slot,index));return
        self.finish(slot,index)
    def finish(self,slot,index):
        del self.blocks[slot];gc.collect();self.observer.deleted(index,publish=not self.buffer_returns)
    def release_pending(self):
        rows,self.pending=self.pending,[]
        for slot,index in rows:self.finish(slot,index)


_BaseTask=source1_fixture.DerivedTask
class Task(_BaseTask):
    def __init__(self,observer,allocator):
        self._storage_observer,self._storage_allocator=observer,allocator;self._storage_slot=allocator.allocate()
        super().__init__()
    def __del__(self):
        # This is an explicit model of ordinary virtual deletion, not a
        # statement about Python finalizer order or an actual Qt base body.
        self._storage_observer.destructor(self._storage_slot)
        super().__del__();self.base=None
        self._storage_allocator.delete(self._storage_slot)


class Parent(processing.Parent):
    def create(self):
        # Only this fresh declared SDK constructor is specialized. No old
        # original exists yet, and the patch ends before returning a task.
        with patch.object(source1_fixture,'DerivedTask',lambda:Task(self.host.storage,self.host.allocator)):
            task=super().create()
        self.host.storage.attach(task._storage_slot,task)
        self.value['tasks'][-1]['constructorReturned']=self.stamp()
        return task


class ImageBoundary(processing.ImageBoundary):
    def __init__(self,host):
        super().__init__(host);self.parent=Parent(self,host);self.value['source1Instance']=self.parent.value['instance']


class Boundary:
    def __init__(self,epoch=EPOCH):
        self.epoch=epoch;self.elapsed=100;self.live=True;self.hold_test_input=False;self.test_input_buffers={};self.cache_only=False
        self.source_owner_ids={};self.texture_revision=2;self.origin_history_instance='2'*32
        self.processing=processing.Observer(self);self.storage=Observer(self);self.allocator=Allocator(self.storage);self.images=ImageBoundary(self)
        sharing=Holder();sharing._sharing_owner_token=object();self.source_owner_ids[sharing._sharing_owner_token]='9'*32
        self.resources=[Resource(sharing)];self.images.parent.resource=self.resources[0];self.images.parent.lease=self.resources[0].lease
        self.task=self.images.create();self.task_id=self.task.id;self.slot=self.task._storage_slot;self.gpu=Holder()
        self.images.invoke(self.task,self.gpu);self.images.finish(self.task);self.images.parent.deliver()
        self.reader=self.storage.reader();self.parent=self.images.parent.reader()
    def tick(self):self.elapsed+=1;return self.clock()
    def clock(self):return self.epoch+self.elapsed
    def monotonic(self):return self.elapsed/1000
    def sleep(self,seconds):self.elapsed+=round(seconds*1000)
    def texture_stamp(self):return dict(epochMs=self.tick(),monotonicMs=self.elapsed)
    def release_product(self):
        self.resources=[];self.images.parent.resource=None;self.images.parent.lease=None;self.task=None;self.gpu=None;gc.collect()
    def read(self):
        packet=self.reader.read(RUN,source1=self.parent);return packet,self.reader.parent_original
