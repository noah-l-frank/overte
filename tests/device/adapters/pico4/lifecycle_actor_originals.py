"""Passive historical V1/V2 Actor originals; never a live source owner."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy

from adapters.chat_journey import source_bundles
from adapters.chat_journey.source_chunks import ChatSourceChunks
from adapters.native_feature_observation import need,integer
from adapters.normal_feature_state import PrivateFeatureState
from adapters.observer_return import state
from adapters.pico4.lifecycle_actor_storage import STAGE,VERSION,decode_snapshot,snapshot_file

SCOPE=('picoLifecycleActorSourceVersion','runId','binding','role','stage','producerHostProcessIdentity',
    'parentHostProcessIdentity','fixtureUrl')


class ActorOriginals:
    def __init__(self,store):
        need(type(store) is PrivateFeatureState)
        self.store=store;self.root,self.raw,self.stamp=state(store)
        self.version=self.root['picoLifecycleActorSourceVersion']
        need(type(self.version) is int and self.version in (1,VERSION))
        self.history=ChatSourceChunks(store,{key:self.root[key] for key in SCOPE})
        self.history.load(self.root['chunks']);source_bundles.logical_bytes(self.root['bundles'])

    def original(self,index):
        self.guard();value=source_bundles.original(self.history,self.root['chunks'],self.root['bundles'],index)[0]
        self.guard();return value

    def guard(self):
        value,raw,stamp=state(self.store)
        need(value==self.root and raw==self.raw and stamp==self.stamp);self.history.verify()

    def group(self,index):
        need(integer(index,0,len(self.root['records'])-1));row=self.root['records'][index]
        if self.version==1:
            return dict(record=dict(phase=self.original(row['phase']),publication=deepcopy(row['publication'])),
                entries=[dict(key=key,value=self.original(value)) for key,value in row['originals'].items()
                    if value is not None],staging=None)
        return self.native(row['native'],record=index)

    def native(self,index,*,record):
        need(integer(record,0,127))
        value=self.original(index)
        need(type(value['lifecycleActorSourceGroupVersion']) is int
            and value['lifecycleActorSourceGroupVersion']==VERSION)
        root,entries=decode_snapshot(value['staging'])
        need(type(root['actorStagingVersion']) is int and root['actorStagingVersion']==1
            and root['sourceScopeSha256']==self.history.scope
            and type(root['record']) is int and root['record']==record)
        return dict(record=deepcopy(value['record']),entries=entries,staging=deepcopy(value['staging']))

    def pending(self):
        """Including a failed prevalidation request/response, without adoption."""
        self.guard()
        pending=self.root['pending']
        if pending is None:return []
        if self.version==1:
            return [dict(key=key,value=self.original(index)) for key,index in pending.items() if index is not None]
        if pending['native'] is not None:return self.native(pending['native'],record=pending['record'])['entries']
        store=PrivateFeatureState(self.store.path.with_name(STAGE))
        if store.read() is None:return []
        root,raw,stamp=state(store)
        need(type(root['actorStagingVersion']) is int and root['actorStagingVersion']==1
            and root['sourceScopeSha256']==self.history.scope
            and type(root['record']) is int and root['record']==pending['record'])
        history=ChatSourceChunks(store,{key:root[key] for key in ('actorStagingVersion','sourceScopeSha256','record')})
        history.load(root['chunks']);files=[]
        for index in range(len(root['chunks'])):
            _value,child,physical=state(history.store(index))
            files.append(snapshot_file(history.names[index],child,physical))
        result=decode_snapshot(dict(actorStagingSnapshotVersion=1,
            root=snapshot_file(STAGE,raw,stamp),files=files))[1]
        again,again_raw,again_stamp=state(store)
        need(again==root and again_raw==raw and again_stamp==stamp);self.guard();return result

    def last(self,key,*,record=None):
        entries=self.pending() if record is None else self.group(record)['entries']
        values=[entry['value'] for entry in entries if entry['key']==key]
        need(values);return deepcopy(values[-1])
