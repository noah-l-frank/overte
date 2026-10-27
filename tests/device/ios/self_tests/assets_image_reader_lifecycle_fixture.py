"""Fresh normal Model fixture with actual Python weak sharing-owner identities.

Qt/H5/parser/renderer/ResourceCache behavior is a declared SDK boundary model.
External cache/holder release is an explicit test stimulus, never adapter cleanup.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import gc,json,threading,uuid,weakref
from adapters.native_feature_observation import NativeFeatureObservation
from adapters.normal_feature_state import PrivateFeatureState
from ios.adapters import assets_image_reader as source1,assets_image_reader_queue as queue
from ios.adapters.assets_image_reader_lifecycle_sources import AssetsImageReaderLifecycleSources
from ios.self_tests import assets_texture_release_fixture as texture
from ios.self_tests import assets_image_reader_queue_fixture as image
from ios.self_tests.assets_reply_fixture import EPOCH,RUN


class Resource(image.Holder):
    def __init__(self,source):self.source=source;self.lease=image.Holder();self.id=uuid.uuid4().hex


class Parent(image.ParentBoundary):
    def __init__(self,owner,host):
        self.host=host;self.task_tokens={};self.receiver_tokens={}
        super().__init__(owner,EPOCH,host.elapsed)
    def stamp(self):
        epoch=self.host.tick();self.time=self.host.elapsed
        return dict(epochMs=epoch,monotonicMs=self.time)
    def create(self):
        resource=self.resource;task=super().create()
        # These are initial constructor observations before ANY original is
        # serialized, not changes to a previously acquired/saved packet.
        self.value['tasks'][-1]['resourceId']=resource.id
        task.resourceId=resource.id;task.resource=weakref.ref(resource)
        self.task_tokens[task.id]=resource.source._sharing_owner_token
        return task
    def invoke(self,task,gpu,*,queued=True,accepted=True,before_return=False):
        target=task.resource();self.resource=target;self.lease=target.lease
        return super().invoke(task,gpu,queued=queued,accepted=accepted,before_return=before_return)
    def receive(self,gpu):
        self.resource.source.gpu=gpu # Declared actual setImage product boundary.
        row=super().receive(gpu);row['resourceId']=self.resource.id
        self.receiver_tokens[row['id']]=self.resource.source._sharing_owner_token
        return row
    def reader(self):
        b=self.host
        return source1.IOSAssetsImageReader(self.send,lambda:self.raw,b.clock,lambda:b.live,42,
            monotonic=b.monotonic,sleep=b.sleep)


class ImageBoundary(image.Boundary):
    def __init__(self,host):
        self.host=host;self.parent=Parent(self,host);self.epoch=EPOCH
        self.sequence=self.event_sequence=0;self.raw='';self.queries=[];self.mutate=None;self.good=True
        self.local=threading.local();self.resource=weakref.ref(self.parent.resource)
        self.value=dict(assetImageReaderQueueHistoryVersion=2,instance=uuid.uuid4().hex,
            source1Instance=self.parent.value['instance'],complete=True,clockDomain='native-assets-image-reader-queue-observer',
            clock=self.stamp(),qtClockDomain='qtcore-metacall-steady-nanoseconds',entries=[],
            **{key:False for key in queue.UNAVAILABLE})
    def binding(self,task,dispatch):
        row=super().binding(task,dispatch);row['resourceId']=task.resourceId
        return row
    def qt_stamp(self):
        value=self.stamp();return dict(epochMs=value['epochMs'],steadyNs=str(800000000000000+self.host.elapsed*1000000))
    def snapshot(self):
        value=deepcopy(self.value)
        tasks={row['id']:row for row in self.parent.value['tasks']}
        for row in value['entries']:
            task=self.parent.weak_tasks[row['taskId']];row['receiverObjectAlive']=task[2]() is not None
            token=self.parent.receiver_tokens.get(row['receiverId'])
            row['receiverTextureSourceId']=self.host.source_owner_ids.get(token,'')
            row['receiverTextureSourceState']='not-observed' if row['receiverId'] is None else ('matched' if row['receiverTextureSourceId'] else 'empty' if token is None else 'unmatched')
        value['clock']=self.stamp()
        value['taskTextureSources']=[dict(taskId=row['id'],resourceId=row['resourceId'],
            textureSourceId=self.host.source_owner_ids.get(self.parent.task_tokens[row['id']],''),
            textureSourceState='matched' if self.parent.task_tokens[row['id']] in self.host.source_owner_ids else 'empty' if self.parent.task_tokens[row['id']] is None else 'unmatched')
            for row in self.parent.value['tasks']]
        value['receiverTextureSources']=[dict(receiverId=row['id'],resourceId=row['resourceId'],
            textureSourceId=self.host.source_owner_ids.get(self.parent.receiver_tokens[row['id']],''),
            textureSourceState='matched' if self.parent.receiver_tokens[row['id']] in self.host.source_owner_ids else 'empty' if self.parent.receiver_tokens[row['id']] is None else 'unmatched')
            for row in self.parent.value['receivers']]
        value['source1TextureReference']=dict(instance=self.parent.value['instance'],
            clockDomain='native-assets-image-reader-observer',clock=self.parent.stamp())
        value['originTextureReference']=dict(instance=self.host.origin_history_instance,
            clockDomain='native-assets-model-origin',revision=self.host.texture_revision,clock=self.host.texture_stamp())
        return value
    def reader(self):
        b=self.host
        return queue.IOSAssetsImageReaderQueue(self.send,lambda:self.raw,b.clock,lambda:b.live,42,
            monotonic=b.monotonic,sleep=b.sleep)


class Boundary(texture.Boundary):
    def __init__(self,directory):
        self.source_owner_ids={};self.image_resources={};self.image_gpus={};self.defer_arguments=False
        super().__init__(directory);self.images=ImageBoundary(self)
    def consume(self,id_,entity):
        super().consume(id_,entity)
        actual=self.models[id_].geometry.material.map.source
        # A metadata token models a C++ shared control block, not a product
        # strong reference. Both weak registries retain this identity after expiry.
        actual._sharing_owner_token=object()
        matches=[row['id'] for weak,row in self.texture_nodes if row['kind']=='source' and weak() is actual]
        assert len(matches)==1;self.source_owner_ids[actual._sharing_owner_token]=matches[0]
        resource=Resource(actual);self.image_resources[id_]=resource
        parent=self.images.parent;parent.resource=resource;parent.lease=resource.lease
        task=parent.create();parent.phase(task,'runEntered');parent.phase(task,'readEntered');gpu=image.Holder()
        self.images.invoke(task,gpu);self.images.finish(task)
        event=parent.queue.pop()
        # The actual event's weak target, never payload equality/FIFO, selects
        # the receiving object in this declared Qt boundary.
        target=event.resource();previous=parent.resource;parent.resource=target
        try:event.deliver(destroy=not self.defer_arguments)
        finally:parent.resource=previous
        if self.defer_arguments:self.held_image_event=event
        self.image_gpus[id_]=weakref.ref(gpu)
    def external_image_cache_eviction(self,id_):
        resource=self.image_resources.pop(id_)
        if self.images.parent.resource is resource:
            self.images.parent.resource=None;self.images.parent.lease=None
        del resource;gc.collect()
    def external_gpu_consumer(self,id_):return self.image_gpus[id_]()
    def create_undispatched_task(self,id_):
        resource=self.image_resources[id_];parent=self.images.parent
        parent.resource=resource;parent.lease=resource.lease
        return parent.create()


class Fixture(texture.Fixture):
    boundary_type=Boundary
    def image_sources(self,parsed):
        b=self.boundary
        def clock_send(query):b.tick();b.native_clock.send(query)
        native=NativeFeatureObservation(clock_send,b.native_clock.original,b.clock,lambda:b.live,42,ios=True,native_clock_bound=True,
            monotonic=b.monotonic,sleep=b.sleep)
        return AssetsImageReaderLifecycleSources(PrivateFeatureState(b.directory/('ios-assets-image-reader-lifecycle-'+RUN+'.json')),
            parsed.sources.binding,RUN,self.lock,lambda:b.live,native=native,queue=b.images.reader(),image_reader=b.images.parent.reader(),
            epoch_ms=lambda:b.clock()+5000,monotonic=b.monotonic)
