"""One durable original Worlds image attempt; no input retry or whole verdict.

Each request gets a distinct private owner. A failed acquisition remains owned
until explicit native drainage; reconstruction cannot issue its capture again.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import time

from adapters.native_clock_join import NativeClockAcquisition
from adapters.native_feature_observation import NativeFeatureObservation,exact,need,number
from adapters.native_vulkan_world_frame import absent
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.normal_ui import NativeUIError
from adapters.owned_vulkan_world_frame import VulkanWorldFrameOwner
from adapters.script_feature.history import pack,unpack,same
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.contract import identifier
from feature_journeys.evidence import MarkerNotReady
from ios.adapters.navigation_challenge import evaluate as challenge
from ios.adapters.navigation_fixture import NavigationFixtureReader,NavigationPhasePending
from ios.adapters.navigation_state import IOSNavigationState,pose_ready
from navigation_observation import viewpoint_urls,same_viewpoint
from ios.adapters.navigation_world_measurements import originals

VERSION=1


class NavigationMarkerPending(NativeUIError):
    """A fully retained original image has not rendered the current marker."""


class NavigationSampleOwner:
    def __init__(self,store,root,binding,run,role,stage,request_id,lock,guard,*,native=None,navigation=None,
                 fixture=None,frame_factory=None,historical=False,epoch_ms=lambda:time.time()*1000,
                 monotonic=time.monotonic,sleep=time.sleep):
        need(isinstance(store,PrivateFeatureState) and isinstance(lock,ScriptSourceLock)
             and role in ('primary','actor') and type(stage) is int and stage in (0,1)
             and type(historical) is bool and callable(guard) and callable(epoch_ms) and callable(monotonic) and callable(sleep))
        identifier(run);need(type(request_id) is str and request_id.startswith('ios-'));identifier(request_id[4:])
        self.store,self.root,self.binding=store,Path(root),deepcopy(context(binding))
        self.run,self.role,self.stage,self.request=run,role,stage,request_id
        self.lock,self.guard,self.historical=lock,(lambda:True) if historical else guard,historical
        self.native,self.navigation,self.fixture,self.factory=native,navigation,fixture,frame_factory
        self.epoch_ms,self.monotonic,self.sleep=epoch_ms,monotonic,sleep
        need(self.root.is_absolute() and self.root.resolve()==self.root and self.root.is_dir())
        PrivateFeatureState(self.root/'navigation-artifact-root-check')._parent()
        need(store.path.name=='ios-navigation-'+role+'-'+str(stage)+'-'+request_id[4:]+'-sample.json'
             and lock.path==store.path.with_name('script-feature-sources.lock'))
        self.pid=int(binding['processIdentity']);need(str(self.pid)==binding['processIdentity'] and self.pid>0)
        if not historical:
            need(isinstance(native,NativeFeatureObservation) and native.ios and native.pid==self.pid
                 and isinstance(navigation,IOSNavigationState) and navigation.pid==self.pid
                 and isinstance(fixture,NavigationFixtureReader) and fixture.run==run and fixture.instance is not None and callable(frame_factory))
        else:need(native is navigation is fixture is frame_factory is None)
        lock.assert_held();self.previous=store.read();self.state=None if self.previous is None else self.decode(self.previous)
        self.bound()

    def envelope(self,state):
        return dict(iosNavigationSampleOwnerVersion=VERSION,binding=self.binding,runId=self.run,role=self.role,
            stage=self.stage,requestId=self.request,artifactRoot=str(self.root),payload=pack([state]))

    def decode(self,value):
        exact(value,{'iosNavigationSampleOwnerVersion','binding','runId','role','stage','requestId','artifactRoot','payload'})
        rows=unpack(value['payload']);need(len(rows)==1 and type(value['iosNavigationSampleOwnerVersion']) is int
            and value['iosNavigationSampleOwnerVersion']==VERSION and same(value,self.envelope(rows[0])))
        state=rows[0];exact(state,{'phase','ticket','partial','record','frameOwner','result','drains'})
        identifier(state['ticket']);need(state['phase'] in ('reading','observed','marker-pending','abandoned')
            and type(state['partial']) is dict and type(state['drains']) is list and len(state['drains'])<=128)
        for packet in state['drains']:need(absent(packet) and packet['processId']==self.pid and packet['requestId']==self.request)
        if state['phase'] in ('observed','marker-pending'):
            need(type(state['record']) is dict and state['frameOwner'] is not None)
            need((state['result'] is None) if state['phase']=='marker-pending' else type(state['result']) is dict)
        else:need(state['record'] is None and state['result'] is None)
        return state

    def bound(self):
        self.lock.assert_held();need(self.guard() is not False and same(self.store.read(),self.previous))

    def save(self):
        need(not self.historical);self.bound();value=self.envelope(self.state);self.decode(value)
        self.store.write(value,self.previous);need(same(self.store.read(),value));self.previous=deepcopy(value);self.bound()

    def remember(self,key,value):
        need(self.state['phase']=='reading' and key not in self.state['partial'])
        self.state['partial'][key]=deepcopy(value);self.save()

    def owner(self,original=None):
        path=self.store.path.with_name('navigation-world-frame-'+self.role+'-'+str(self.stage)+'-'+self.request[4:]+'.json')
        store=PrivateFeatureState(path)
        if original is not None:
            value=deepcopy(original)
            class Frozen(PrivateFeatureState):
                def read(self):return deepcopy(value)
                def write(self,*_args):need(False)
                def discard(self,*_args):need(False)
            store=Frozen(path)
        return VulkanWorldFrameOwner(store,self.root,self.binding,self.run,self.role,self.stage,self.request,
            (lambda *_:need(False)) if original is not None or self.historical else self.factory,
            (lambda:True) if original is not None else self.guard,source_lock=self.lock,
            monotonic=self.monotonic,sleep=self.sleep)

    def owns_read(self,owner):
        # A read intent is only written after this request's original inspect
        # proved an empty native slot. An occupied pre-existing slot grants no
        # authority to release another owner's resource, even on failure.
        owner._load()
        return owner.state is not None and any(event['command']['operation']=='read' for event in owner.events)

    def capture(self,ticket,url,label,host_barrier):
        need(not self.historical);identifier(ticket);self.bound();need(self.state is None)
        need(type(label) is str and label in ('A','B','C') and same_viewpoint(url,viewpoint_urls(self.fixture.inputs['sceneUrl'])[label])
             and number(host_barrier,1,1e15))
        self.state=dict(phase='reading',ticket=ticket,partial={},record=None,frameOwner=None,result=None,drains=[]);self.save()
        phase=self.fixture.read();need(phase['ticket']==ticket);self.remember('phaseBefore',phase)
        owner=self.owner();need(owner.store.read() is None)
        window=NativeClockAcquisition(self.native,epoch_ms=self.epoch_ms,monotonic=self.monotonic);window.begin(host_barrier)
        frame={}
        before=self.navigation.read(self.run);frame['navigationBefore']=before;self.remember('navigationBefore',before)
        need(before['iosNavigationStateVersion']==2);pose_ready(before,url,label)
        self.remember('frameOwnerStarted',True)
        try:
            frame['capture'],raw=owner.capture(ticket);self.remember('capture',frame['capture'])
        finally:
            if owner.store.read() is not None and self.owns_read(owner):
                frame['retirement']=owner.release();self.remember('retirement',frame['retirement'])
        after=self.navigation.read(self.run);frame['navigationAfter']=after;self.remember('navigationAfter',after)
        packets=originals(frame);fields=[(name,'capturedEpochMs') for name,packet in packets.items() if 'capturedEpochMs' in packet]
        frame['clockJoin']=window.finish(packets,fields);self.remember('clockJoin',frame['clockJoin'])
        current=self.fixture.read();self.remember('phaseAfter',current)
        if current['ticket']!=ticket or current['originals']['phaseAfter']['activations']!=phase['originals']['phaseAfter']['activations']:
            raise NavigationPhasePending('Navigation input phase changed; original capture ownership remains')
        sample=dict(frame=frame,captureQuery=dict(schemaVersion=1,action='feature-vulkan-world-frame',operation='read',
            commandId=frame['capture']['commandId'],requestId=self.request),url=url,label=label,ticket=ticket,
            provider=current['originals']['scene'],providerInstance=self.fixture.instance,fixtureUrl=self.fixture.fixture_url)
        pending=False
        try:result,_subject=challenge(self.run,self.binding,sample|dict(raw=raw))
        except MarkerNotReady:pending=True;result=None
        self.state.update(phase='marker-pending' if pending else 'observed',record=sample,frameOwner=deepcopy(owner.state),result=result)
        self.save();need(owner.archive()==raw);self.bound()
        need(number(self.monotonic(),frame['clockJoin']['hostBeforeMonotonic'],frame['clockJoin']['hostBeforeMonotonic']+1.5))
        if pending:raise NavigationMarkerPending('Original navigation marker is not yet rendered')
        return deepcopy(result)

    def archive(self):
        """Original file/history validation only; never a current observation."""
        self.bound();need(self.state is not None and self.state['phase'] in ('observed','marker-pending'))
        owner=self.owner(self.state['frameOwner']);raw=owner.archive()
        need(owner.state['phase']=='released' and absent(owner.state['absence'])
             and same(owner.state['frame'],self.state['record']['frame']['capture'])
             and any(same(event['receipt'],self.state['record']['frame']['retirement']) for event in owner.events))
        sample=deepcopy(self.state['record'])|dict(raw=raw)
        try:result,_=challenge(self.run,self.binding,sample)
        except MarkerNotReady:need(self.state['phase']=='marker-pending');result=None
        else:need(self.state['phase']=='observed' and same(result,self.state['result']))
        self.bound();return sample,deepcopy(result)

    def drain(self):
        """Fresh original GPU absence; leaves all PNG/metadata responsibility."""
        need(not self.historical);self.bound();need(self.state is not None and len(self.state['drains'])<128)
        owner=self.owner()
        if owner.store.read() is None:
            need(self.state['phase'] in ('reading','abandoned') and self.state['frameOwner'] is None
                 and 'frameOwnerStarted' not in self.state['partial'])
            try:(self.root/owner.name).lstat()
            except FileNotFoundError:pass
            else:need(False)
            proof=None
        else:
            need(self.owns_read(owner))
            proof=owner.release();need(absent(proof));owner.verify_owned_artifact()
            self.state['drains'].append(deepcopy(proof))
        if self.state['phase']=='reading':
            self.state['phase']='abandoned';self.state['frameOwner']=deepcopy(owner.store.read())
        self.save();return deepcopy(proof)
