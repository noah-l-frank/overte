"""Durable original primary/peer model-consumer join, without pixel/publication.

This observational child creates no entity or session and sends no normal
input. Failed cohorts and source prefixes stay owned; cached peer resources
remain separate from source collection and never become retired here.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_feature_observation import exact,integer,need,number
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_feature.history import pack,unpack,same
from adapters.script_feature.lock import ScriptSourceLock
from ios.adapters.assets_budget import operation
from ios.adapters.assets_parsed_owner import OwnedAssetsParsedInput
from ios.adapters.assets_scene_sources import AssetsSceneSources
from ios.adapters.assets_scene_facts import peer_model

VERSION=1


class OwnedAssetsPeer:
    def __init__(self,parsed,primary,peer,store,lock):
        need(isinstance(parsed,OwnedAssetsParsedInput) and isinstance(primary,AssetsSceneSources) and isinstance(peer,AssetsSceneSources)
            and isinstance(store,PrivateFeatureState) and isinstance(lock,ScriptSourceLock) and lock is peer.lock
            and parsed.lock is primary.lock and primary.role=='actor-primary' and peer.role=='actor'
            and primary.run==peer.run==parsed.sources.run and same(primary.binding,parsed.model.usage.source.binding)
            and primary.binding['targetFingerprint']!=peer.binding['targetFingerprint'] and primary.pid!=peer.pid
            and store.path.parent==peer.store.path.parent and parsed.store.path.parent==primary.store.path.parent
            and store.path.name=='ios-assets-peer-'+primary.run+'.json')
        self.parsed,self.primary,self.peer,self.store,self.lock=parsed,primary,peer,store,lock
        self.monotonic,self.epoch_ms=peer.monotonic,peer.epoch_ms;self.run=primary.run
        lock.assert_held();primary.lock.assert_held();self.previous=store.read();self.state=None
        if self.previous is not None:self.state=self.decode(self.previous)

    def guard(self):
        self.lock.assert_held();self.primary.lock.assert_held();self.parsed.guard();self.primary.guard();self.peer.guard()
        need(same(self.store.read(),self.previous));return True
    def lineage(self):
        need(self.parsed.state is not None and self.parsed.state['phase']=='observed');self.parsed.decode(self.parsed.previous)
        return self.parsed.state['result']
    def envelope(self):
        return dict(iosAssetsPeerOwnerVersion=VERSION,binding=self.peer.binding,primaryBinding=self.primary.binding,runId=self.run,
            primaryDirectory=str(self.primary.store.path.parent),primaryDirectoryIdentity=self.primary_identity(),
            fileOwnerToken=self.parsed.model.usage.source.files.state['token'],entityId=self.lineage()['entityId'],payload=pack([self.state]))
    def primary_identity(self):
        PrivateFeatureState(self.primary.store.path)._parent();info=self.primary.store.path.parent.stat()
        return dict(device=info.st_dev,inode=info.st_ino)
    def source_frame(self,source,reference):
        need(source.state is not None and reference in source.state['frames']);previous=None
        for item in source.state['frames']:
            frame=source.originals.read(source.originals.expand(item));source.frame(frame,previous)
            if same(item,reference):return frame['scene']
            previous=frame
        need(False)
    def attempt(self,value):
        exact(value,{'startedEpochMs','startedMonotonic','primaryIndex','peerIndex','primary','peer'})
        need(number(value['startedEpochMs'],1,1e15) and number(value['startedMonotonic'],0,1e15)
            and integer(value['primaryIndex'],1,40) and integer(value['peerIndex'],1,40))
        if value['primary'] is not None:
            need(value['primary']['index']==value['primaryIndex'])
            frame=self.source_frame(self.primary,value['primary']);window=frame['clockJoin']
            need(window['hostBeforeEpochMs']>=value['startedEpochMs'] and window['hostBeforeMonotonic']>=value['startedMonotonic'])
        if value['peer'] is not None:
            need(value['primary'] is not None and value['peer']['index']==value['peerIndex']);self.source_frame(self.peer,value['peer'])
        return value
    def derive(self,attempt):
        self.attempt(attempt);need(attempt['primary'] is not None and attempt['peer'] is not None)
        primary=self.source_frame(self.primary,attempt['primary']);peer=self.source_frame(self.peer,attempt['peer'])
        a,b=primary['clockJoin'],peer['clockJoin']
        need(b['hostBeforeMonotonic']>=a['hostAfterMonotonic'] and b['hostBeforeEpochMs']>=a['hostAfterEpochMs']
            and b['hostAfterMonotonic']-a['hostBeforeMonotonic']<1.5 and b['hostAfterEpochMs']-a['hostBeforeEpochMs']<1500
            and abs((b['hostAfterEpochMs']-a['hostBeforeEpochMs'])-(b['hostAfterMonotonic']-a['hostBeforeMonotonic'])*1000)<=250)
        lineage=self.lineage();creation=self.parsed.model.state['creation']['proof'];id_=lineage['entityId']
        for frame in (primary,peer):
            rows=[row for row in frame['originals']['createAfter']['source']['entities'] if row['id']==id_];need(len(rows)==1);row=rows[0]
            need(row['createdEpochUs']==creation['createdEpochUs'] and row['name']==creation['name'] and row['modelURL']==creation['url']
                and row['position']==creation['position'] and row['lastEditedBy']==creation['clientNodeId'] and row['hostType']=='domain'
                and row['visible'] and not row['locked'])
        return peer_model(primary,peer,lineage)
    def decode(self,value):
        exact(value,{'iosAssetsPeerOwnerVersion','binding','primaryBinding','runId','primaryDirectory','primaryDirectoryIdentity','fileOwnerToken','entityId','payload'})
        need(type(value['iosAssetsPeerOwnerVersion']) is int and value['iosAssetsPeerOwnerVersion']==VERSION and same(value['binding'],self.peer.binding)
            and same(value['primaryBinding'],self.primary.binding) and value['runId']==self.run
            and value['primaryDirectory']==str(self.primary.store.path.parent) and same(value['primaryDirectoryIdentity'],self.primary_identity())
            and value['fileOwnerToken']==self.parsed.model.usage.source.files.state['token'] and value['entityId']==self.lineage()['entityId'])
        rows=unpack(value['payload']);need(len(rows)==1);state=rows[0];exact(state,{'attempts','pending','result'})
        need(type(state['attempts']) is list and len(state['attempts'])<=8);primary=[];peer=[]
        for attempt in state['attempts']+([] if state['pending'] is None else [state['pending']]):
            self.attempt(attempt)
            for key,refs in (('primary',primary),('peer',peer)):
                if attempt[key] is not None:
                    need(not refs or attempt[key]['index']>refs[-1]['index']);refs.append(attempt[key])
        if state['result'] is not None:need(state['pending'] is not None and same(state['result'],self.derive(state['pending'])))
        return state
    def save(self):
        self.guard();value=self.envelope();self.decode(value);self.store.write(value,self.previous);self.previous=deepcopy(value)
    @operation
    def reserve(self):
        self.guard();need(self.state is None);self.lineage()
        self.state=dict(attempts=[],pending=None,result=None);self.save()
    def acquire(self,source,barrier,index):
        if source.state is None:source.reserve()
        completed=[reference for reference in source.state['frames'] if reference['index']==index]
        if completed:
            need(len(completed)==1);self.source_frame(source,completed[0]);return deepcopy(completed[0])
        need(source.state['nextIndex']==index)
        if source.state['pending'] is not None:source.recover_capture()
        else:source.capture(barrier)
        reference=source.state['frames'][-1];need(reference['index']==index);return deepcopy(reference)
    @operation
    def observe(self):
        self.guard();need(self.state is not None)
        if self.state['result'] is not None:self.decode(self.previous);return deepcopy(self.state['result'])
        if self.state['pending'] is None:
            need(len(self.state['attempts'])<8);self.state['pending']=dict(startedEpochMs=self.epoch_ms(),startedMonotonic=self.monotonic(),
                primaryIndex=1 if self.primary.state is None else self.primary.state['nextIndex'],
                peerIndex=1 if self.peer.state is None else self.peer.state['nextIndex'],primary=None,peer=None);self.save()
        attempt=self.state['pending']
        if attempt['primary'] is None:attempt['primary']=self.acquire(self.primary,attempt['startedEpochMs'],attempt['primaryIndex']);self.save()
        if attempt['peer'] is None:
            source=self.source_frame(self.primary,attempt['primary']);attempt['peer']=self.acquire(self.peer,source['clockJoin']['hostAfterEpochMs'],attempt['peerIndex']);self.save()
        result=self.derive(attempt);self.state['result']=result;self.save();return deepcopy(result)
    @operation
    def freeze_failed_attempt(self):
        self.guard();need(self.state is not None and self.state['pending'] is not None and self.state['result'] is None and len(self.state['attempts'])<8)
        for source in (self.primary,self.peer):
            if source.state is not None and source.state['pending'] is not None:source.freeze_interrupted()
        self.state['attempts'].append(deepcopy(self.state['pending']));self.state['pending']=None;self.save()
