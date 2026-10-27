"""Tiny declared Qt/H5 boundary with actual weak Python product holders.

No native parser, C++, compiler, SDK, GPU or device executes. Sharing tokens
model immutable weak control-block identity; they never own the Source object.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import gc,weakref
from ios.self_tests.assets_image_reader_lifecycle_fixture import ImageBoundary,Resource
from ios.self_tests.assets_image_reader_queue_fixture import Holder,RUN
from ios.self_tests.test_ios_assets_texture_consumers import AssetsTextureConsumersTests
from ios.self_tests.assets_reply_fixture import EPOCH


class Boundary:
    def __init__(self):
        self.elapsed=100;self.live=True;self.model=AssetsTextureConsumersTests().prepare(EPOCH)
        self.origin_history_instance=self.model.state['history']['instance'];self.texture_revision=2
        self.source_owner_ids={};self.resources=[]
        self.images=ImageBoundary(self)
        source=Holder();source._sharing_owner_token=object()
        self.source=weakref.ref(source);self.source_owner_ids[source._sharing_owner_token]='9'*32
        resource=Resource(source);self.resources.append(resource)
        self.images.parent.resource=resource;self.images.parent.lease=resource.lease
        self.task=self.images.create();self.gpu=Holder();self.images.invoke(self.task,self.gpu);self.images.finish(self.task)
        self.event=self.images.parent.queue.pop();self.event.deliver();self.event=None
        self.reader=self.images.reader();self.parent=self.images.parent.reader();self.origin=self.model.reader()
        self._death=None
        def observe(packet):
            row=packet['source']['history']['textureOwnership']['nodes'][1]
            row['strongOwnersAlive']=self.source() is not None
            if not row['strongOwnersAlive']:
                if self._death is None:self._death=deepcopy(packet['source']['history']['clock'])
                row['ownershipExpiryObserved']=deepcopy(self._death)
        self.model.mutate=observe
    def tick(self):self.elapsed+=1;return EPOCH+self.elapsed
    def clock(self):return EPOCH+self.elapsed
    def monotonic(self):return self.elapsed/1000
    def sleep(self,seconds):self.elapsed+=round(seconds*1000)
    def texture_stamp(self):return dict(epochMs=self.tick(),monotonicMs=self.elapsed)
    def read(self):
        packet=self.reader.read(RUN,source1=self.parent)
        self.model.time=self.elapsed;origin=self.origin.read(RUN);self.elapsed=self.model.time
        return packet,deepcopy(self.reader.parent_original),origin
    def close_owned(self,*,keep_gpu=False):
        self.resources=[];self.images.parent.resource=None;self.images.parent.lease=None;self.task=None
        if not keep_gpu:self.gpu=None
        gc.collect()
    def add_task(self,*,selected=False,unknown=False):
        source=self.source() if selected else Holder()
        if not selected:source._sharing_owner_token=None if unknown else object()
        resource=Resource(source);self.resources.append(resource)
        self.images.parent.resource=resource;self.images.parent.lease=resource.lease
        return self.images.parent.create()
