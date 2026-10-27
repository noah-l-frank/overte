"""Independent modeled domain delivery/loader, driven by actual product writes.

The primary's normal QML/API creates an Entity object. Its modeled domain store
publishes that actual creation message to a separate peer store before any
observation. Peer parsing reads current independent backend bytes at delivery,
never a primary observation, adapter result or expected entity/geometry verdict.
All native/domain/parser/render process boundaries are explicit SDK models.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
from pathlib import Path
import uuid
from adapters.native_feature_observation import NativeFeatureObservation
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_feature.lock import ScriptSourceLock
from ios.adapters import create_state,emote_world,assets_model_origin
from ios.adapters.assets_scene_sources import AssetsSceneSources
from ios.self_tests import assets_parsed_fixture as parsed,assets_model_fixture as model
from ios.self_tests.assets_scene_facts_fixture import instantiate_native
from ios.self_tests.test_ios_create_peer import domain_pair


class DomainEntities(dict):
    def __init__(self,publish):super().__init__();self.publish=publish
    def __setitem__(self,id_,entity):
        super().__setitem__(id_,entity);self.publish(id_,deepcopy(entity.properties))


class PeerWorld:
    state=model.Boundary.state
    observe_lifetime=model.Boundary.observe_lifetime
    origin=parsed.Boundary.origin
    consume=parsed.Boundary.consume
    def __init__(self,primary):
        self.primary=primary;self.entities={};self.models={};self.lifetimes={};self.entity_revision=0;self.model_sequence=0;self.model_work_sequence=0
        self.model_source_instance=uuid.uuid4().hex;self.model_work_instance=uuid.uuid4().hex;self.entity_tree_instance=uuid.uuid4().hex
        self.origin_rows={};self.origin_sequence=0;self.origin_instance=uuid.uuid4().hex;self.origin_history_instance=uuid.uuid4().hex;self.origin_fault=None
        self.model_resource_cache={};self.origin_weaks={};self.reads=primary.reads;self.host_state=dict(pageAlive=False)
        self.usage_ids=dict(clientNodeId=str(uuid.uuid4()));self.resolve_model=None;self.deliveries=[]
    def clock(self):return self.primary.clock()+500
    def tick(self,milliseconds=1):self.primary.tick(milliseconds);return self.clock()
    def receive(self,id_,properties):
        self.deliveries.append(dict(id=id_,properties=deepcopy(properties)));entity=model.Entity();entity.created=int(properties['createdEpochUs']);entity.properties=deepcopy(properties)
        self.entities[id_]=entity;self.models[id_]=model.Model();self.entity_revision+=1;self.consume(id_,entity)
        self.models[id_].loaded=True;self.models[id_].added=True


class Boundary(parsed.Boundary):
    def __init__(self,directory):
        super().__init__(directory);self.peer=PeerWorld(self);self.entities=DomainEntities(self.peer.receive)


class Fixture(parsed.Fixture):
    boundary_type=Boundary
    def __init__(self,directory):
        super().__init__(directory);self.boundary.peer.resolve_model=self.resolve_model
        # Existing narrow fixtures use assets.lock; this combined candidate
        # path uses the canonical lock before any child state/input is created.
        self.guard.__exit__(None,None,None);self.lock=ScriptSourceLock(Path(directory)/'script-feature-sources.lock')
        self.guard=self.lock.held();self.guard.__enter__()
        for owner in (self.files,self.picker,self.replies):owner.lock=self.lock
    def prepared_peer(self):
        m,b=self.prepared();owner=self.parsed(m,b);owner.reserve();owner.observe();return owner


class SceneEndpoint:
    def __init__(self,fixture,parsed_owner,root,role):
        self.fixture,self.boundary,self.role=fixture,fixture.boundary,role;self.world=self.boundary if role=='actor-primary' else self.boundary.peer
        self.root=Path(root);self.root.mkdir(mode=0o700,exist_ok=True);self.pid=42 if role=='actor-primary' else 43
        self.binding=deepcopy(parsed_owner.sources.binding)
        if role=='actor':self.binding.update(processIdentity='43',targetFingerprint='9'*64,sessionId='actual-peer-boundary')
        self.lock=fixture.lock if role=='actor-primary' else ScriptSourceLock(self.root/'script-feature-sources.lock');self.lock_context=None
        if role=='actor':self.lock_context=self.lock.held();self.lock_context.__enter__()
        self.store=PrivateFeatureState(self.root/('ios-assets-scene-'+parsed.RUN+'-'+role+'.json'));self.raw={};self.counts=dict(clock=0,state=0,domain=0,origin=0);self.queries=[];self.good=True
        self.instance=uuid.uuid4().hex;self.domain_instance=uuid.uuid4().hex;self.monotonic=self.boundary.monotonic;self.epoch_ms=lambda:1900000000000+self.boundary.elapsed
    def close(self):
        if self.lock_context is not None:self.lock_context.__exit__(None,None,None)
    def send(self,kind,query):
        self.queries.append((kind,deepcopy(query)));self.counts[kind]+=1;self.boundary.tick()
        if kind=='clock':packet=instantiate_native(self.world.clock(),self.pid,self.instance,self.counts[kind])
        elif kind=='state':packet=self.world.state(query['commandId']);packet['processId']=self.pid
        elif kind=='origin':packet=self.world.origin(query);packet['processId']=self.pid
        else:
            # A distinct actual getter reads this endpoint's domain/tree, not
            # the primary observation or its action/owner journal.
            state=self.world.state();state['processId']=self.pid
            packet=domain_pair(state,state)[0];packet.update(instance=self.domain_instance,sequence=self.counts[kind])
        packet['requestId']=query['commandId'];self.raw[kind]=json.dumps(packet)
    def owner(self):
        guard=lambda:self.good and self.boundary.live
        self.native=NativeFeatureObservation(lambda query:self.send('clock',query),lambda:self.raw.get('clock',''),self.world.clock,guard,self.pid,
            ios=True,native_clock_bound=True,monotonic=self.monotonic,sleep=self.boundary.sleep)
        def reader(cls,kind):return cls(lambda query:self.send(kind,query),lambda:self.raw.get(kind,''),self.world.clock,guard,self.pid,monotonic=self.monotonic,sleep=self.boundary.sleep)
        return AssetsSceneSources(self.store,self.binding,parsed.RUN,self.role,self.lock,guard,native=self.native,
            state=reader(create_state.IOSCreateState,'state'),domain=reader(emote_world.IOSEmoteWorld,'domain'),origin=reader(assets_model_origin.IOSAssetsModelOrigin,'origin'),
            epoch_ms=self.epoch_ms,monotonic=self.monotonic)
