"""Untouched static Worlds originals and an independently acquired Vulkan PNG.

This owner runs before ordinary scene entry. Its immutable native/image window
does not refresh an admission deadline. A whole coordinator must acquire a new
actual admission cut immediately before its first ordinary Go To input.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import time

from adapters.native_clock_join import NativeClockAcquisition,digest,validate_join
from adapters.native_feature_observation import NativeFeatureObservation,exact,fresh,need,number
from adapters.native_vulkan_world_frame import absent
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.owned_vulkan_world_frame import VulkanWorldFrameOwner
from adapters.script_feature.history import pack,unpack,same
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.contract import identifier
from ios.adapters.navigation_admission_owner import SOURCES
from ios.adapters.navigation_fixture import NavigationFixtureReader
from ios.adapters import navigation_scene_admission as admission
from ios.adapters.navigation_world_measurements import compose as rendered,originals as image_originals
from navigation_observation import viewpoint_urls

VERSION=1
KEYS=('base','baseRead','nativeStart','navigationBefore','capture','retirement','frameOwner',*SOURCES,'nativeEnd')


class NavigationBaselineImage:
    def __init__(self,store,root,binding,run,role,request,lock,guard,*,native=None,sources=None,
                 fixture=None,frame_factory=None,historical=False,epoch_ms=lambda:time.time()*1000,
                 monotonic=time.monotonic,sleep=time.sleep):
        context(binding);identifier(run);need(role in ('primary','actor') and type(request) is str
            and request.startswith('ios-'));identifier(request[4:])
        need(isinstance(store,PrivateFeatureState) and isinstance(lock,ScriptSourceLock) and type(historical) is bool
            and all(callable(fn) for fn in (guard,epoch_ms,monotonic,sleep)))
        self.store,self.root,self.binding,self.run,self.role,self.request=store,Path(root),deepcopy(binding),run,role,request
        self.lock,self.guard,self.historical=lock,(lambda:True) if historical else guard,historical
        self.native,self.sources,self.fixture,self.factory=native,sources,fixture,frame_factory
        self.epoch_ms,self.monotonic,self.sleep=epoch_ms,monotonic,sleep
        self.pid=int(binding['processIdentity']);need(self.pid>0 and str(self.pid)==binding['processIdentity'])
        need(self.root.is_absolute() and self.root.resolve()==self.root and self.root.is_dir()
            and lock.path==store.path.with_name('script-feature-sources.lock')
            and store.path.name=='ios-navigation-baseline-'+role+'-'+request[4:]+'.json')
        PrivateFeatureState(self.root/'navigation-baseline-root-check')._parent()
        if historical:need(native is sources is fixture is frame_factory is None)
        else:
            need(isinstance(native,NativeFeatureObservation) and native.ios and native.pid==self.pid
                and isinstance(fixture,NavigationFixtureReader) and fixture.run==run and fixture.instance is not None
                and callable(frame_factory));exact(sources,SOURCES)
            for name,kind in SOURCES.items():
                need(isinstance(sources[name],kind))
                if name!='ui':need(sources[name].pid==self.pid)
        lock.assert_held();self.previous=store.read();self.state=None if self.previous is None else self.decode(self.previous)
        self.bound()

    def envelope(self,state):
        return dict(iosNavigationBaselineImageVersion=VERSION,binding=self.binding,runId=self.run,role=self.role,
            requestId=self.request,artifactRoot=str(self.root),payload=pack([state]))

    def component(self,key):
        need(key in KEYS)
        return PrivateFeatureState(self.root/('navigation-baseline-'+self.run+'-'+self.role+'-'+self.request[4:]+'-'+key+'.json'))

    def wrap(self,key,value):
        return dict(iosNavigationBaselineOriginalVersion=VERSION,binding=self.binding,runId=self.run,role=self.role,
            requestId=self.request,kind=key,original=value)

    def decode(self,value):
        exact(value,set(self.envelope({})));rows=unpack(value['payload'])
        need(type(value['iosNavigationBaselineImageVersion']) is int and value['iosNavigationBaselineImageVersion']==VERSION
            and len(rows)==1 and same(value,self.envelope(rows[0])))
        state=rows[0];exact(state,{'phase','hostBarrier','providerInstance','providerInputs','issued','records','resultSha256','drains'})
        need(state['phase'] in ('reading','observed') and number(state['hostBarrier'],1,1e15))
        identifier(state['providerInstance']);need(type(state['issued']) is list and len(set(state['issued']))==len(state['issued'])
            and set(state['issued'])<=set(KEYS) and type(state['records']) is list and type(state['drains']) is list
            and len(state['drains'])<=128)
        names=[]
        for ref in state['records']:
            exact(ref,{'kind','sha256'});need(ref['kind'] in state['issued'] and ref['kind'] not in names
                and type(ref['sha256']) is str and len(ref['sha256'])==64);names.append(ref['kind'])
        need((state['resultSha256'] is None) if state['phase']=='reading' else
            type(state['resultSha256']) is str and len(state['resultSha256'])==64 and set(names)==set(KEYS))
        for packet in state['drains']:need(absent(packet) and packet['processId']==self.pid and packet['requestId']==self.request)
        return deepcopy(state)

    def bound(self):
        self.lock.assert_held();need(self.guard() is not False and same(self.store.read(),self.previous))
        if not self.historical and self.state is not None:
            need(self.fixture.instance==self.state['providerInstance'] and same(self.fixture.inputs,self.state['providerInputs']))

    def save(self):
        need(not self.historical);self.bound();value=self.envelope(self.state);self.decode(value)
        self.store.write(value,self.previous);need(same(self.store.read(),value));self.previous=deepcopy(value);self.bound()

    def take(self,key,operation):
        need(self.state['phase']=='reading' and key not in self.state['issued'])
        target=self.component(key);need(target.read() is None)
        self.state['issued'].append(key);self.save();value=operation();original=self.wrap(key,deepcopy(value))
        target.write(original,None);need(same(target.read(),original))
        self.state['records'].append(dict(kind=key,sha256=digest(original)));self.save();return deepcopy(value)

    def originals(self):
        result={}
        for ref in self.state['records']:
            key=ref['kind'];value=self.component(key).read()
            need(value is not None and digest(value)==ref['sha256'] and same(value,self.wrap(key,value.get('original'))))
            result[key]=deepcopy(value['original'])
        return result

    def owner(self,original=None):
        path=self.store.path.with_name('navigation-baseline-world-frame-'+self.role+'-'+self.request[4:]+'.json')
        store=PrivateFeatureState(path)
        if original is not None:
            value=deepcopy(original)
            class Frozen(PrivateFeatureState):
                def read(self):return deepcopy(value)
                def write(self,*_args):need(False)
                def discard(self,*_args):need(False)
            store=Frozen(path)
        return VulkanWorldFrameOwner(store,self.root,self.binding,self.run,self.role,0,self.request,
            (lambda *_:need(False)) if self.historical or original is not None else self.factory,
            (lambda:True) if original is not None else self.guard,source_lock=self.lock,
            monotonic=self.monotonic,sleep=self.sleep)

    @staticmethod
    def join(parts,originals):
        return dict(parts['nativeStart'],**parts['nativeEnd'],originalsSha256=digest(originals),sourceTimes=[
            dict(source=name,field=field,epochMs=packet[field]) for name,packet in originals.items()
            for field in ('capturedEpochMs','sampleEpochMs') if field in packet])

    def qualify(self):
        self.bound();parts=self.originals();exact(parts,KEYS)
        original={key:parts[key] for key in SOURCES};clock=self.join(parts,original);validate_join(clock,original)
        before,after=parts['baseRead']['before'],parts['baseRead']['after']
        for packet in (before,after):exact(packet,{'epochMs','monotonic'})
        need(number(before['epochMs'],self.state['hostBarrier'],clock['hostBeforeEpochMs'])
            and number(after['epochMs'],before['epochMs'],clock['hostBeforeEpochMs'])
            and number(before['monotonic'],0,after['monotonic']) and after['monotonic']<=clock['hostBeforeMonotonic']
            and clock['hostAfterEpochMs']-before['epochMs']<1500
            and clock['hostAfterMonotonic']-before['monotonic']<1.5
            and abs(clock['hostAfterEpochMs']-before['epochMs']-(clock['hostAfterMonotonic']-before['monotonic'])*1000)<=250)
        fresh(parts['base']['capturedEpochMs'],int(after['epochMs']))
        need(parts['base']['capturedEpochMs']>=before['epochMs']-1)
        proof=admission.admit(self.run,self.binding,original,clock,parts['base'],
            provider_instance=self.state['providerInstance'],provider_inputs=self.state['providerInputs'])
        owner=self.owner(parts['frameOwner']);raw=owner.archive()
        need(owner.state['phase']=='released' and absent(owner.state['absence']) and same(owner.state['frame'],parts['capture'])
            and any(same(row['receipt'],parts['retirement']) for row in owner.events))
        frame={key:parts[key] for key in ('navigationBefore','capture','retirement')}
        frame['navigationAfter']=parts['navigation'];frame['clockJoin']=self.join(parts,image_originals(frame|dict(clockJoin=None)))
        query=dict(schemaVersion=1,action='feature-vulkan-world-frame',operation='read',
            commandId=parts['capture']['commandId'],requestId=self.request)
        pixels=rendered(self.run,self.binding,frame,raw,url=viewpoint_urls(proof['base']['url'])['A'],label='A',capture_query=query)
        result=dict(admissionSha256=digest(proof),rendered=pixels,originalsSha256=digest(parts))
        self.bound();return result,proof,raw

    def acquire(self,host_barrier):
        need(not self.historical);self.bound();need(self.state is None and number(host_barrier,1,1e15))
        self.state=dict(phase='reading',hostBarrier=host_barrier,providerInstance=self.fixture.instance,
            providerInputs=deepcopy(self.fixture.inputs),issued=[],records=[],resultSha256=None,drains=[]);self.save()
        first=dict(epochMs=self.epoch_ms(),monotonic=self.monotonic())
        self.take('base',self.fixture.base_scene)
        self.take('baseRead',lambda:dict(before=first,after=dict(epochMs=self.epoch_ms(),monotonic=self.monotonic())))
        window=NativeClockAcquisition(self.native,epoch_ms=self.epoch_ms,monotonic=self.monotonic)
        def begin():window.begin(host_barrier);return window.started
        self.take('nativeStart',begin);self.take('navigationBefore',lambda:self.sources['navigation'].read(self.run))
        owner=self.owner();need(owner.store.read() is None)
        try:self.take('capture',lambda:owner.capture(self.request[4:])[0])
        finally:
            owner._load()
            if owner.state is not None and any(row['command']['operation']=='read' for row in owner.events):
                self.take('retirement',owner.release);self.take('frameOwner',lambda:owner.store.read())
        for name in SOURCES:
            reader=self.sources[name]
            self.take(name,lambda reader=reader,name=name:reader.capture() if name=='ui' else reader.read(self.run))
        self.take('nativeEnd',lambda:dict(nativeAfter=self.native.read(self.native.sequence),
            hostAfterEpochMs=self.epoch_ms(),hostAfterMonotonic=self.monotonic()))
        result,_proof,_raw=self.qualify();self.state.update(phase='observed',resultSha256=digest(result));self.save()
        value=self.archive();self.fresh();return value

    def archive(self):
        self.bound();need(self.state is not None and self.state['phase']=='observed')
        result,proof,raw=self.qualify();need(digest(result)==self.state['resultSha256']);return result,proof,raw

    def recover(self):
        """Only complete retained originals; never another source or GPU read."""
        need(not self.historical);self.bound();need(self.state is not None and self.state['phase']=='reading')
        result,_proof,_raw=self.qualify();self.state.update(phase='observed',resultSha256=digest(result));self.save()

    def fresh(self):
        need(not self.historical);parts=self.originals();first=parts['baseRead']['before'];last=parts['nativeEnd']
        self.bound();epoch,mono=self.epoch_ms(),self.monotonic()
        need(number(epoch,last['hostAfterEpochMs'],first['epochMs']+1500)
            and number(mono,last['hostAfterMonotonic'],first['monotonic']+1.5)
            and epoch-first['epochMs']<1500 and mono-first['monotonic']<1.5
            and abs(epoch-first['epochMs']-(mono-first['monotonic'])*1000)<=250)

    def drain(self):
        """Actual native frame drainage preserves every retained original."""
        need(not self.historical);self.bound();need(self.state is not None and len(self.state['drains'])<128)
        owner=self.owner();owner._load();need(owner.state is not None
            and any(row['command']['operation']=='read' for row in owner.events))
        proof=owner.release();need(absent(proof));owner.verify_owned_artifact()
        self.state['drains'].append(deepcopy(proof));self.save();return proof
