"""Tiny fresh actual weak-holder processing producer, explicitly not native Qt."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import gc,weakref
from ios.self_tests.assets_image_processing_fixture import Observer,ImageBoundary
from ios.self_tests.assets_image_reader_lifecycle_fixture import Resource
from ios.self_tests.assets_image_reader_queue_fixture import Holder,RUN
from ios.self_tests.assets_reply_fixture import EPOCH


class Boundary:
    def __init__(self,*,held=False,cached=False,epoch=EPOCH):
        self.epoch=epoch;self.elapsed=100;self.live=True;self.hold_test_input=held;self.cache_only=cached;self.test_input_buffers={}
        self.source_owner_ids={};self.texture_revision=2;self.origin_history_instance='2'*32
        self.processing=Observer(self);self.images=ImageBoundary(self)
        source=Holder();source._sharing_owner_token=object();self.source_owner_ids[source._sharing_owner_token]='9'*32
        self.resources=[Resource(source)];self.images.parent.resource=self.resources[0];self.images.parent.lease=self.resources[0].lease
        self.task=self.images.create();self.task_id=self.task.id;self.gpu=Holder()
        self.images.invoke(self.task,self.gpu);self.images.finish(self.task);self.images.parent.deliver()
        self.reader=self.processing.reader();self.parent=self.images.parent.reader()
    def tick(self):self.elapsed+=1;return self.clock()
    def clock(self):return self.epoch+self.elapsed
    def monotonic(self):return self.elapsed/1000
    def sleep(self,seconds):self.elapsed+=round(seconds*1000)
    def texture_stamp(self):return dict(epochMs=self.tick(),monotonicMs=self.elapsed)
    def read(self):
        packet=self.reader.read(RUN,source1=self.parent);return packet,self.reader.parent_original
    def release_product(self):
        self.resources=[];self.images.parent.resource=None;self.images.parent.lease=None;self.task=None;self.gpu=None;gc.collect()
    def release_test_buffers(self):self.test_input_buffers.clear();gc.collect()
