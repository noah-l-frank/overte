"""Declared pool-tail pause after actual host allocation block release."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters.native_feature_observation import NativeFeatureObservation
from adapters.normal_feature_state import PrivateFeatureState
from ios.adapters.assets_image_pool_sources import AssetsImageReaderPoolSources
from ios.self_tests import assets_image_storage_flow_fixture as storage_flow
from ios.self_tests.assets_image_pool_fixture import Observer,StorageObserver,ImageBoundary
from ios.self_tests import assets_image_storage_fixture as storage
from ios.self_tests.assets_reply_fixture import RUN


class Boundary(storage_flow.Boundary):
    def __init__(self,directory):
        super().__init__(directory);self.pool_mode='worker';self.pool=Observer(self)
        self.storage=StorageObserver(self);self.allocator=storage.Allocator(self.storage)
        self.images=ImageBoundary(self)


class Fixture(storage_flow.Fixture):
    boundary_type=Boundary
    def pool_sources(self,parsed):
        b=self.boundary
        def clock_send(query):b.tick();b.native_clock.send(query)
        native=NativeFeatureObservation(clock_send,b.native_clock.original,b.clock,lambda:b.live,42,ios=True,native_clock_bound=True,
            monotonic=b.monotonic,sleep=b.sleep)
        return AssetsImageReaderPoolSources(PrivateFeatureState(b.directory/('ios-assets-image-pool-'+RUN+'.json')),
            parsed.sources.binding,RUN,self.lock,lambda:b.live,native=native,pool=b.pool.reader(),storage=b.storage.reader(),image_reader=b.images.parent.reader(),
            epoch_ms=lambda:b.clock()+5000,monotonic=b.monotonic)
