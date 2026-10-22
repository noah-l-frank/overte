"""Durable fresh original Navigation stereo publication after normal UI close.

This passive source owns one acquisition identity at a time. It performs no UI
input and accepts no image policy, desired location or expected feature state.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
from pathlib import Path
import time
import uuid
from adapters.native_feature_observation import exact,integer,need,number
from adapters.navigation_arrival import stereo_frame,advance as pose_advance
from adapters.navigation_stereo import NavigationStereo
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.pico4.navigation_close import NavigationTabletClose
from adapters.script_journey.history import pack,unpack
from feature_journeys.contract import identifier,json_document
from feature_journeys.evidence import read_private_artifact
from feature_journeys.stereo_navigation_evidence import original_name,source_identity,advance_sources,clocks

VERSION=1
LIMIT=128


class NavigationFrames:
    def __init__(self,closed,factory,path,artifact_root,role,clock_ms,guard,*,monotonic=time.monotonic):
        need(isinstance(closed,NavigationTabletClose) and closed.state is not None and closed.state['phase']=='closed'
             and role in ('primary','actor') and all(callable(f) for f in (factory,clock_ms,guard,monotonic)))
        self.closed,self.factory,self.role,self.clock_ms,self.guard=closed,factory,role,clock_ms,guard
        self.run,self.binding=closed.run,deepcopy(closed.binding);self.root=Path(artifact_root)
        PrivateFeatureState(self.root/'navigation-artifact-boundary.json')._parent()
        self.monotonic,self.clock,self.deadline=monotonic,None,None
        self.store=PrivateFeatureState(path);self.disk=self.store.read();self.state=dict(sequence=0,records=[],pending=None)
        if self.disk is not None:
            exact(self.disk,{'navigationFramesVersion','runId','binding','role','artifactRoot','payload'})
            need(type(self.disk['navigationFramesVersion']) is int and self.disk['navigationFramesVersion']==VERSION
                 and self.disk['runId']==self.run and self.disk['binding']==self.binding and self.disk['role']==role
                 and self.disk['artifactRoot']==str(self.root))
            rows=unpack(self.disk['payload']);need(len(rows)==1);self.state=rows[0]
        self.deadline=self.now()+20
        try:self.validate(self.state);self.now()
        finally:self.deadline=None
    def now(self):
        need(self.guard() is not False);now=self.monotonic()
        need(number(now,0,1e15) and (self.clock is None or now>=self.clock) and (self.deadline is None or now<=self.deadline))
        self.clock=now;return now
    def owner(self,journal):
        identifier(journal);owner=self.factory(journal)
        need(isinstance(owner,NavigationStereo) and owner.journal_id==journal and owner.run==self.run
             and owner.role==self.role and owner.binding==self.binding and owner.images.root==self.root
             and owner.store.path==self.root/original_name(self.run,self.role,journal))
        return owner
    def original(self,record):
        self.now()
        exact(record,{'journalId','sequence','ticket','metadataSha256','closeOriginalSha256'})
        identifier(record['journalId']);identifier(record['ticket']);need(integer(record['sequence'],1,LIMIT))
        need(all(type(record[k]) is str and len(record[k])==64 and all(c in '0123456789abcdef' for c in record[k])
                 for k in ('metadataSha256','closeOriginalSha256')))
        owner=self.owner(record['journalId']);need(owner.state is not None and owner.state['phase']=='complete')
        raw=read_private_artifact(self.root,owner.store.path.name)
        need(len(raw)<=65536 and hashlib.sha256(raw).hexdigest()==record['metadataSha256']
             and json_document(raw)==owner.disk and owner.state['ticket']==record['ticket'])
        frame=owner.state['frame'];need(frame['navigationStereoSourceVersion']==2)
        facts=stereo_frame(frame,owner.image_bytes(),self.run,self.binding,self.closed.transit.scene_url)
        identity=source_identity(frame);self.now();return owner,facts,identity
    def validate(self,value):
        exact(value,{'sequence','records','pending'});need(integer(value['sequence'],0,LIMIT)
            and type(value['records']) is list and len(value['records'])==value['sequence'])
        journals=set();frames=set();queries=set();previous=None
        for index,record in enumerate(value['records'],1):
            owner,_facts,identity=self.original(record)
            need(record['sequence']==index and record['journalId'] not in journals and identity['frameId'] not in frames)
            request=list(identity['requests'].values());need(len(set(request))==len(request) and not queries.intersection(request))
            if previous is not None:advance_sources(previous,identity)
            journals.add(record['journalId']);frames.add(identity['frameId']);queries.update(request);previous=identity
        pending=value['pending']
        if pending is not None:
            exact(pending,{'journalId','sequence','ticket','closeOriginalSha256','before'})
            identifier(pending['journalId']);identifier(pending['ticket']);self.closed.archive(pending['before'])
            self.closed.closed(pending['before'],self.closed.state['before'])
            need(pending['journalId'] not in journals and pending['sequence']==value['sequence']+1<=LIMIT
                 and type(pending['sequence']) is int and pending['ticket']==self.closed.state['ticket']
                 and pending['closeOriginalSha256']==self.closed.origin)
    def save(self,value):
        self.now();self.validate(value)
        disk=dict(navigationFramesVersion=VERSION,runId=self.run,binding=self.binding,role=self.role,artifactRoot=str(self.root),payload=pack([value]))
        self.store.write(disk,self.disk);self.disk=deepcopy(disk);self.state=deepcopy(value)
    def current(self):
        value=self.closed.sample();self.closed.closed(value,self.closed.state['before']);self.now();return value
    def result(self,record,after):
        owner,facts,_identity=self.original(record);frame=owner.state['frame'];start,end=clocks(frame)
        need(frame['nativeAfter']['capturedEpochMs']<=after['transit']['ui']['observedEpochMs'])
        pose_advance(frame['after'],after['transit']['pose']);self.now();epoch=self.clock_ms()
        need(integer(epoch,1) and 0<=epoch-start<=1500 and end<=epoch and self.guard() is not False)
        return dict(navigationFrameVersion=VERSION,sequence=record['sequence'],capturedEpochMs=start,location=facts['location'],
            lifecycle=deepcopy(frame['nativeBefore']['lifecycle']),artifacts=owner.artifacts(record['sequence']),
            journalId=record['journalId'],observation=deepcopy(after))
    def read(self,ticket,after_sequence):
        identifier(ticket);need(integer(after_sequence,0,LIMIT) and ticket==self.closed.state['ticket'] and self.deadline is None)
        self.deadline=self.now()+20
        try:return self.execute(ticket,after_sequence)
        except NativeUIError:raise
        except Exception:raise NativeUIError('Original Navigation frame publication remains unresolved') from None
        finally:self.deadline=None
    def execute(self,ticket,after_sequence):
        need(self.store.read()==self.disk)
        if self.state['pending'] is None and self.state['sequence']>0 and after_sequence==self.state['sequence']-1:
            record=self.state['records'][-1];need(record['ticket']==ticket and record['closeOriginalSha256']==self.closed.origin)
            # A lost publication may return the same still-fresh original frame;
            # neither its sequence nor any source epoch is changed.
            return self.result(record,self.current())
        need(after_sequence==self.state['sequence'])
        if self.state['pending'] is None:
            need(self.state['sequence']<LIMIT);before=self.current();journal=uuid.uuid4().hex
            current=deepcopy(self.state);current['pending']=dict(journalId=journal,sequence=current['sequence']+1,
                ticket=ticket,closeOriginalSha256=self.closed.origin,before=before);self.save(current)
        pending=self.state['pending'];need(pending['ticket']==ticket and pending['closeOriginalSha256']==self.closed.origin)
        owner=self.owner(pending['journalId']);owner.acquire(ticket);self.now();frame=owner.state['frame']
        need(frame['navigationStereoSourceVersion']==2
             and pending['before']['graphics']['capturedEpochMs']<=frame['nativeBefore']['requestedEpochMs'])
        pose_advance(pending['before']['transit']['pose'],frame['before'])
        after=self.current();raw=read_private_artifact(self.root,owner.store.path.name)
        record={k:pending[k] for k in ('journalId','sequence','ticket','closeOriginalSha256')}
        record['metadataSha256']=hashlib.sha256(raw).hexdigest();result=self.result(record,after)
        current=deepcopy(self.state);current['records'].append(record);current['sequence']=record['sequence'];current['pending']=None;self.save(current)
        # Slow persistence cannot refresh an old image's original clock.
        need(0<=self.clock_ms()-result['capturedEpochMs']<=1500);self.now();return result
