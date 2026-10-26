"""Explicit entity-tree/renderer model driven by original QML API events.

This is not Qt, an actual model parser, renderer or device. Entity and Model
objects are explicit Python boundary objects; original API arguments determine
independent rows. No separate resource/weak-retirement verdict is produced.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
import uuid
import weakref
from adapters.script_feature.history import canonical
from ios.adapters import create_state,create_work
from ios.self_tests import assets_usage_fixture as usage

RUN=usage.RUN


class Entity:
    pass


class Model:
    def __init__(self):self.loaded=False;self.added=False;self.failed=False


class Boundary(usage.Boundary):
    def __init__(self,directory):
        self.entities={};self.models={};self.entity_events_seen=0;self.model_sequence=0;self.model_work_sequence=0;self.model_source_instance=uuid.uuid4().hex;self.model_work_instance=uuid.uuid4().hex;self.entity_tree_instance=uuid.uuid4().hex;self.entity_revision=0;self.lifetimes={}
        super().__init__(directory)

    def exchange(self,value):
        result=super().exchange(value);events=result.get('bundleInfo',{}).get('serviceEvents',[])
        for event in events[self.entity_events_seen:]:
            if event['kind']!='entity-returned' or event['id']=='00000000-0000-0000-0000-000000000000':continue
            args=event['args'];item=Entity();item.created=self.clock()*1000
            item.properties=dict(id=event['id'],hostType='domain',name=args[0],type=event['type'],shape='',dimensions=[1,1,1],modelURL=args[1],textures=args[2],
                position=[args[7][axis] for axis in ('x','y','z')],rotation=[0,0,0,1],sourceUrl='',userData='',collisionless=args[5],lastEditedBy=self.usage_ids['clientNodeId'],
                createdEpochUs=str(item.created),lastEditedEpochUs=str(item.created),locked=False,visible=True,voxels={})
            self.entities[event['id']]=item;self.models[event['id']]=Model();self.entity_revision+=1
        self.entity_events_seen=len(events);return result

    def observe_lifetime(self,id_,item,model):
        if id_ not in self.lifetimes:self.lifetimes[id_]=dict(weak=weakref.ref(item),born=self.clock(),destroyed=0,models=[])
        row=self.lifetimes[id_]
        if not any(entry['weak']() is model for entry in row['models']):row['models'].append(dict(weak=weakref.ref(model),instance=uuid.uuid4().hex,born=self.clock(),destroyed=0))

    def state(self,request_id=None):
        self.model_sequence+=1;before=self.tick();entities=[];tree=[]
        for id_,item in sorted(self.entities.items()):
            row=deepcopy(item.properties);model=self.models[id_];row['model']=dict(present=True,loaded=model.loaded,addedToScene=model.added,failed=model.failed,textures=[])
            self.observe_lifetime(id_,item,model)
            entities.append(row);raw=canonical(item.properties);tree.append(dict(id=id_,hostType=row['hostType'],ready=True,createdEpochUs=row['createdEpochUs'],lastEditedEpochUs=row['lastEditedEpochUs'],
                lastEditedAfterEpochUs=row['lastEditedEpochUs'],semanticBytes=len(raw),semanticSha256=hashlib.sha256(raw).hexdigest()))
        after=self.tick();return dict(iosCreateStateVersion=4,requestId=request_id or 'ios-'+uuid.uuid4().hex,runId=RUN,instance=self.model_source_instance,sequence=self.model_sequence,
            processId=42,clockDomain='native-main-create',clockBefore=dict(epochMs=before,monotonicMs=before-usage.picker.EPOCH),clockAfter=dict(epochMs=after,monotonicMs=after-usage.picker.EPOCH),
            source=dict(complete=True,tabletShown=self.host_state['pageAlive'],domainId=self.reads.binding['domainId'],localSessionId=self.usage_ids['clientNodeId'],canRez=True,canRezTmp=False,roots=[],entities=entities,
                tree=dict(entityInventoryVersion=1,profile='native-entity-edit-wire-v1',treeInstance=self.entity_tree_instance,revisionBefore=self.entity_revision,revisionAfter=self.entity_revision,totalEntities=len(tree),complete=True,entities=tree),
                view=dict(position=[0,1,0],rotation=[0,0,0,1],fieldOfViewDegrees=60,aspectRatio=1,perspective=True,uiWidth=768,uiHeight=768)))

    def work_source(self,query):
        create_work.command(query);self.model_work_sequence+=1;before=self.tick();rows=[]
        def lifetime(entry):
            destroyed=entry['weak']() is None
            if destroyed and not entry['destroyed']:entry['destroyed']=self.clock()
            return dict(bornEpochMs=entry['born'],destroyed=destroyed,destructionObservedEpochMs=entry['destroyed'])
        for id_,row in sorted(self.lifetimes.items()):
            models=[dict(instance=entry['instance'],**lifetime(entry)) for entry in row['models']]
            rows.append(dict(id=id_,models=models,**lifetime(row)))
        after=self.tick();return dict(iosCreateWorkVersion=1,requestId=query['commandId'],runId=query['runId'],instance=self.model_work_instance,sequence=self.model_work_sequence,processId=42,clockDomain='native-main-create-work',
            clockBefore=dict(epochMs=before,monotonicMs=before-usage.picker.EPOCH),clockAfter=dict(epochMs=after,monotonicMs=after-usage.picker.EPOCH),
            source=dict(complete=True,eventSequence=0,roles=[],entityLifetimes=dict(createLifetimesVersion=1,complete=True,entities=rows)))

    def model_readers(self,clock):
        def state_send(query):create_state.command(query);self.model_original=self.state(query['commandId'])
        def work_send(query):self.model_work_original=self.work_source(query)
        def epoch():return clock.read(clock.sequence)['capturedEpochMs']
        return (create_state.IOSCreateState(state_send,lambda:json.dumps(self.model_original),epoch,lambda:self.live,42,monotonic=self.monotonic,sleep=self.sleep),
            create_work.IOSCreateWork(work_send,lambda:json.dumps(self.model_work_original),epoch,lambda:self.live,42,monotonic=self.monotonic,sleep=self.sleep))


class Fixture(usage.Fixture):
    boundary_type=Boundary
    def accepted(self):
        owner=self.owned_existing_source();owner.select();owner.open_model();before=self.boundary.state();owner.accept_model();after=self.boundary.state();return owner,before,after

    def sources(self,owner,*,store=None):
        from adapters.normal_feature_state import PrivateFeatureState
        from ios.adapters.assets_model_sources import AssetsModelSources
        state,work=self.boundary.model_readers(owner.source.clock)
        return AssetsModelSources(owner,owner.source.clock,state,work,store or PrivateFeatureState(self.boundary.directory/'model-sources.json'),lock=self.lock,
            epoch_ms=lambda:self.boundary.clock()+5000,monotonic=self.boundary.monotonic)
