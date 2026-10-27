"""Typed in-memory SDK dispatch with actual raw/logical private-file owners.

Every reply is emitted for its actual fresh query by a declared producer. The
clock progression is synthetic; no retained original is changed or reused as
a new read, and no target/device/service or native renderer executes.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
from pathlib import Path
from adapters.native_feature_observation import NativeFeatureObservation
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_feature.lock import ScriptSourceLock
from ios.adapters import create_state,emote_world,assets_model_origin
from ios.adapters.assets_scene_sources import AssetsSceneSources
from ios.self_tests.assets_scene_facts_fixture import pair,instantiate_native
from ios.self_tests.test_ios_create_state import EPOCH,RUN


class Fixture:
    def __init__(self,root,*,role='actor-primary'):
        primary,actor,self.lineage=pair();self.template=primary if role=='actor-primary' else actor;self.role=role;self.binding=self.template['binding']
        self.root=Path(root);self.lock=ScriptSourceLock(self.root/'script-feature-sources.lock');self.lock_context=self.lock.held();self.lock_context.__enter__()
        self.store=PrivateFeatureState(self.root/('ios-assets-scene-'+RUN+'-'+role+'.json'))
        self.now=0;self.round=0;self.good=True;self.queries=[];self.counts=dict(clock=0,state=0,domain=0,origin=0);self.raw={}
    def readers(self):
        self.native=NativeFeatureObservation(lambda query:self.send('clock',query),lambda:self.raw.get('clock',''),lambda:EPOCH+self.now,lambda:self.good,int(self.binding['processIdentity']),
            ios=True,native_clock_bound=True,monotonic=self.monotonic,sleep=self.sleep)
        def reader(type_,kind):return type_(lambda query:self.send(kind,query),lambda:self.raw.get(kind,''),lambda:EPOCH+self.now,lambda:self.good,
            int(self.binding['processIdentity']),monotonic=self.monotonic,sleep=self.sleep)
        self.state=reader(create_state.IOSCreateState,'state');self.domain=reader(emote_world.IOSEmoteWorld,'domain');self.origin=reader(assets_model_origin.IOSAssetsModelOrigin,'origin')
    def close(self):self.lock_context.__exit__(None,None,None)
    def monotonic(self):return 10+self.now/1000
    def epoch(self):return 1900000000000+self.now
    def sleep(self,seconds):self.now+=round(seconds*1000)
    def next_round(self):self.round+=1;self.now=self.round*200
    def send(self,kind,query):
        self.queries.append((kind,deepcopy(query)));self.counts[kind]+=1;count=self.counts[kind];offset=self.round*200
        if kind=='clock':
            endpoint=0 if count%2 else 100;self.now=offset+endpoint
            packet=instantiate_native(EPOCH+self.now,int(self.binding['processIdentity']),self.template['clockJoin']['nativeBefore']['instance'],count)
        else:
            key=('createBefore' if count%2 else 'createAfter') if kind=='state' else kind
            packet=deepcopy(self.template['originals'][key]);packet['sequence']=count
            for field in ('clockBefore','clockAfter'):
                packet[field]['epochMs']+=offset;packet[field]['monotonicMs']+=offset
            if kind=='domain':
                def move(value):
                    if type(value) is dict:
                        for name,child in value.items():
                            if name.endswith('EpochMs') and type(child) is int and child>0:value[name]+=offset
                            else:move(child)
                    elif type(value) is list:
                        for child in value:move(child)
                move(packet['source']['scriptOriginal'])
            elif kind=='origin':
                packet['source']['history']['clock']['epochMs']+=offset;packet['source']['history']['clock']['monotonicMs']+=offset
            self.now=packet['clockAfter']['epochMs']-EPOCH
        packet['requestId']=query['commandId'];self.raw[kind]=json.dumps(packet)
    def owner(self):
        self.readers()
        return AssetsSceneSources(self.store,self.binding,RUN,self.role,self.lock,lambda:self.good,native=self.native,state=self.state,domain=self.domain,origin=self.origin,
            epoch_ms=self.epoch,monotonic=self.monotonic)
