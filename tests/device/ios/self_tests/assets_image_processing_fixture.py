"""Explicit native/Qt processing model with actual weak Python input owners.

No observer owns a product buffer. Only the test driver's separate external
holder table may keep a copy, selected before producer/original birth.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import gc,json,uuid,weakref
from adapters.native_feature_observation import NativeFeatureObservation
from adapters.normal_feature_state import PrivateFeatureState
from ios.adapters import assets_image_reader_processing as source
from ios.adapters.assets_image_processing_sources import AssetsImageReaderProcessingSources
from ios.self_tests import assets_image_reader_lifecycle_fixture as image
from ios.self_tests.assets_reply_fixture import EPOCH,RUN


class Buffer:
    def __init__(self,observer,row):self._observer,self._row=observer,row
    def __del__(self):self._observer.destroyed(self._row)


class Observer:
    def __init__(self,host):
        self.host=host;self.instance=uuid.uuid4().hex;self.sequence=0;self.raw='';self.queries=[];self.tasks=[];self.calls=[]
        self.task_markers={};self.devices={};self.failed=False;self.defer_destruction=False;self.delayed=[];self.mutate=None
    def phase(self,worker=True):
        value=dict(epochMs=self.host.tick(),monotonicMs=self.host.elapsed,threadContextId=('3' if worker else '1')*32)
        return value
    def prepare(self,task):
        self.task_markers[task.id]=weakref.ref(task.marker)
        self.tasks.append(dict(taskId=task.id,resourceId=task.resourceId,prepared=self.phase(False)))
    def process(self,task):
        row=dict(id=uuid.uuid4().hex,taskId=task.id,resourceId=task.resourceId,deviceId=uuid.uuid4().hex,
            **{key:None for key in source.PHASES})
        self.calls.append(row);row['bindingEntered']=self.phase();device=Buffer(self,row);self.devices[row['id']]=weakref.ref(device)
        row['processingEntered']=self.phase();row['rawEntered']=self.phase();row['rawReturned']=self.phase()
        row['contentResetEntered']=self.phase()
        # Actual independent reference belongs to the declared test driver,
        # never the Observer, adapter, native getter or normal product input.
        if self.host.hold_test_input:self.host.test_input_buffers[task.resourceId]=device
        del device
        row['contentResetReturned']=self.phase();row['processingReturned']=self.phase()
    def destroyed(self,row):
        original=self.phase()
        if self.defer_destruction:self.delayed.append((row,original))
        else:row['deviceDestroyedObserved']=original
    def publish_destruction(self):
        for row,original in self.delayed:row['deviceDestroyedObserved']=deepcopy(original)
        self.delayed=[]
    def snapshot(self):
        return dict(assetImageReaderProcessingHistoryVersion=1,instance=self.instance,source1Instance=self.host.images.parent.value['instance'],
            complete=not self.failed,clockDomain='native-assets-image-reader-processing',clock=dict(epochMs=self.host.tick(),monotonicMs=self.host.elapsed),
            tasks=[dict(deepcopy(row),derivedMarkerAlive=self.task_markers[row['taskId']]() is not None) for row in self.tasks],
            calls=[dict(deepcopy(row),deviceOwnersAlive=self.devices[row['id']]() is not None) for row in self.calls],
            **{key:False for key in source.UNAVAILABLE})
    def send(self,query):
        self.queries.append(deepcopy(query));self.sequence+=1
        before=dict(epochMs=self.host.tick(),monotonicMs=self.host.elapsed);history=self.snapshot();after=dict(epochMs=self.host.tick(),monotonicMs=self.host.elapsed)
        packet=dict(iosAssetsImageReaderProcessingVersion=1,requestId=query['commandId'],runId=query['runId'],instance='5'*32,
            sequence=self.sequence,processId=42,clockDomain='native-main-assets-image-reader-processing',clockBefore=before,clockAfter=after,source=history)
        if self.mutate:self.mutate(packet)
        self.raw=json.dumps(packet)
    def reader(self):
        b=self.host
        return source.IOSAssetsImageReaderProcessing(self.send,lambda:self.raw,b.clock,lambda:b.live,42,monotonic=b.monotonic,sleep=b.sleep)


class Parent(image.Parent):
    def create(self):
        task=super().create();self.host.processing.prepare(task)
        # Initial modeled constructor publication only; no saved original exists
        # yet. The actual native prepare hook precedes constructed(task).
        self.value['tasks'][-1]['constructorReturned']=self.stamp();return task
    def invoke(self,task,gpu,*,queued=True,accepted=True,before_return=False):
        cached=getattr(self.host,'cache_only',False)
        if not cached:self.host.processing.process(task)
        value=super().invoke(task,gpu,queued=queued,accepted=accepted,before_return=before_return)
        if cached:value['branch']='cache-reuse' # Actual declared producer branch before its first original.
        return value


class ImageBoundary(image.ImageBoundary):
    def __init__(self,host):
        super().__init__(host);self.parent=Parent(self,host);self.value['source1Instance']=self.parent.value['instance']


class Boundary(image.Boundary):
    def __init__(self,directory):
        self.hold_test_input=True;self.test_input_buffers={};self.cache_only=False
        super().__init__(directory);self.processing=Observer(self);self.images=ImageBoundary(self)
    def take_test_input(self,entity):
        # The real test caller receives an independent owner and then releases
        # only its own copy. No adapter or observer performs this action.
        actual=self.test_input_buffers.pop(self.image_resources[entity].id)
        self.test_input_buffers.clear();gc.collect();return actual


class Fixture(image.Fixture):
    boundary_type=Boundary
    def processing_sources(self,parsed):
        b=self.boundary
        def clock_send(query):b.tick();b.native_clock.send(query)
        native=NativeFeatureObservation(clock_send,b.native_clock.original,b.clock,lambda:b.live,42,ios=True,native_clock_bound=True,
            monotonic=b.monotonic,sleep=b.sleep)
        return AssetsImageReaderProcessingSources(PrivateFeatureState(b.directory/('ios-assets-image-processing-'+RUN+'.json')),
            parsed.sources.binding,RUN,self.lock,lambda:b.live,native=native,processing=b.processing.reader(),image_reader=b.images.parent.reader(),
            epoch_ms=lambda:b.clock()+5000,monotonic=b.monotonic)
