"""Tiny actual durable-file owner over a declared native/event clock producer."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
from pathlib import Path
from adapters.native_feature_observation import NativeFeatureObservation
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_feature.lock import ScriptSourceLock
from ios.adapters.assets_image_pool_sources import AssetsImageReaderPoolSources
from ios.self_tests.assets_image_pool_fixture import Boundary
from ios.self_tests.assets_scene_facts_fixture import instantiate_native
from ios.self_tests.assets_reply_fixture import EPOCH,RUN,BINDING


class Fixture:
    def __init__(self,root):
        self.root=Path(root);self.boundary=Boundary();self.queries=[];self.raw='';self.count=0
        self.lock=ScriptSourceLock(self.root/'script-feature-sources.lock')
        self.held=self.lock.held();self.held.__enter__()
    def close(self):self.boundary.release_product();self.held.__exit__(None,None,None)
    def clock_send(self,query):
        self.queries.append(deepcopy(query));self.count+=1;b=self.boundary
        packet=instantiate_native(b.tick(),42,'6'*32,self.count);packet['requestId']=query['commandId']
        self.raw=json.dumps(packet)
    def owner(self):
        b=self.boundary
        native=NativeFeatureObservation(self.clock_send,lambda:self.raw,b.clock,lambda:b.live,42,
            ios=True,native_clock_bound=True,monotonic=b.monotonic,sleep=b.sleep)
        return AssetsImageReaderPoolSources(PrivateFeatureState(self.root/('ios-assets-image-pool-'+RUN+'.json')),
            BINDING,RUN,self.lock,lambda:b.live,native=native,pool=b.pool.reader(),storage=b.storage.reader(),image_reader=b.images.parent.reader(),
            epoch_ms=b.clock,monotonic=b.monotonic)
    def commands(self):return deepcopy([self.queries,self.boundary.pool.queries,self.boundary.storage.queries,self.boundary.images.parent.queries])
