"""Declared allocator pause only; no observer/product cleanup or native pool."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters.native_feature_observation import NativeFeatureObservation
from adapters.normal_feature_state import PrivateFeatureState
from ios.adapters.assets_image_storage_sources import AssetsImageReaderStorageSources
from ios.self_tests import assets_image_processing_fixture as processing
from ios.self_tests.assets_image_storage_fixture import Observer,Allocator,ImageBoundary
from ios.self_tests.assets_reply_fixture import RUN


class Boundary(processing.Boundary):
    def __init__(self,directory):
        super().__init__(directory);self.hold_test_input=False
        self.storage=Observer(self);self.allocator=Allocator(self.storage);self.allocator.paused=True
        self.images=ImageBoundary(self)


class Fixture(processing.Fixture):
    boundary_type=Boundary
    def storage_sources(self,parsed):
        b=self.boundary
        def clock_send(query):b.tick();b.native_clock.send(query)
        native=NativeFeatureObservation(clock_send,b.native_clock.original,b.clock,lambda:b.live,42,ios=True,native_clock_bound=True,
            monotonic=b.monotonic,sleep=b.sleep)
        return AssetsImageReaderStorageSources(PrivateFeatureState(b.directory/('ios-assets-image-storage-'+RUN+'.json')),
            parsed.sources.binding,RUN,self.lock,lambda:b.live,native=native,storage=b.storage.reader(),image_reader=b.images.parent.reader(),
            epoch_ms=lambda:b.clock()+5000,monotonic=b.monotonic)
