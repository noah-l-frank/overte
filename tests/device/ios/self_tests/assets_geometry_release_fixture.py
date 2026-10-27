"""Fresh original normal Delete with actual weak Geometry/cache holders.

The source never clears the cache. Explicit external eviction is a declared
native-boundary event in tests, not an iOS user action or adapter success.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import gc
import json
import uuid
import weakref
from adapters.native_feature_observation import NativeFeatureObservation
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_feature.lock import ScriptSourceLock
from ios.adapters import assets_model_origin,create_state,emote_world
from ios.adapters.assets_scene_sources import AssetsSceneSources
from ios.self_tests import assets_model_removal_fixture as removal
from ios.self_tests.test_ios_assets_geometry_consumers import Geometry
from ios.self_tests.test_ios_create_peer import domain_pair
from ios.self_tests.assets_reply_fixture import EPOCH,RUN


class Boundary(removal.Boundary):
    def __init__(self,directory):
        self.geometry_rows=[]
        super().__init__(directory)
    def consume(self,id_,entity):
        super().consume(id_,entity)
        resource=self.model_resource_cache[id_];actual=self.models[id_]
        resource.geometry=Geometry(resource.hfm);actual.geometry=Geometry(resource.hfm)
        for kind,geometry in (('resource',resource.geometry),('copy',actual.geometry)):
            clock=dict(epochMs=self.tick(),monotonicMs=self.clock()-EPOCH)
            row=dict(id=uuid.uuid4().hex,readerId=self.origin_rows[id_]['id'],mappingIds=[],kind=kind,born=clock,destructionObserved=None)
            self.geometry_rows.append((weakref.ref(geometry.token),row))
    def origin(self,query):
        rows=[]
        for weak,original in self.geometry_rows:
            alive=weak() is not None
            if not alive and original['destructionObserved'] is None:
                original['destructionObserved']=dict(epochMs=self.tick(),monotonicMs=self.clock()-EPOCH)
            rows.append(dict(deepcopy(original),alive=alive))
        value=super().origin(query);history=value['source']['history']
        history.update(assetModelOriginHistoryVersion=3,geometries=rows);return value
    def external_cache_eviction(self,id_):
        # A separate native boundary event, never called by the source/adapter.
        self.model_resource_cache.pop(id_);gc.collect()


class DomainProducer:
    """Fresh native-style bracket, never a timestamp around a saved packet."""
    def __init__(self,boundary):self.b=boundary;self.instance=uuid.uuid4().hex;self.sequence=0
    def __call__(self,query):
        b=self.b;before=dict(epochMs=b.tick(),monotonicMs=b.elapsed)
        # The old domain helper is a single-sample content specification. Its
        # constant monotonic sample clock is not this producer's native clock.
        state=b.state();packet=domain_pair(state,state)[0];self.sequence+=1
        packet.update(requestId=query['commandId'],runId=RUN,instance=self.instance,sequence=self.sequence,
            clockBefore=before,clockAfter=dict(epochMs=b.tick(),monotonicMs=b.elapsed))
        return packet


class Fixture(removal.Fixture):
    boundary_type=Boundary
    def __init__(self,directory):
        super().__init__(directory)
        self.guard.__exit__(None,None,None);self.lock=ScriptSourceLock(directory/'script-feature-sources.lock')
        self.guard=self.lock.held();self.guard.__enter__()
        for owner in (self.files,self.picker,self.replies):owner.lock=self.lock
    def scene(self,parsed):
        b=self.boundary;raw={};domain=DomainProducer(b)
        def clock_send(query):b.tick();b.native_clock.send(query)
        native=NativeFeatureObservation(clock_send,b.native_clock.original,b.clock,lambda:b.live,42,ios=True,native_clock_bound=True,
            monotonic=b.monotonic,sleep=b.sleep)
        def reader(cls,kind,produce):
            def send(query):raw[kind]=json.dumps(produce(query))
            return cls(send,lambda:raw.get(kind,''),b.clock,lambda:b.live,42,monotonic=b.monotonic,sleep=b.sleep)
        return AssetsSceneSources(PrivateFeatureState(b.directory/('ios-assets-scene-'+RUN+'-primary.json')),
            parsed.sources.binding,RUN,'primary',self.lock,lambda:b.live,native=native,
            state=reader(create_state.IOSCreateState,'state',lambda q:b.state(q['commandId'])),
            domain=reader(emote_world.IOSEmoteWorld,'domain',domain),origin=reader(assets_model_origin.IOSAssetsModelOrigin,'origin',b.origin),
            epoch_ms=lambda:b.clock()+5000,monotonic=b.monotonic)
