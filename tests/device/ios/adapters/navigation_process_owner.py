"""Durable fresh-source acquisition after an independently owned app restart.

This owner neither stops/launches the app nor reissues interrupted source reads.
The ordinary restart controller must already own its receipt and old originals.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import time

from adapters.native_clock_join import NativeClockAcquisition,digest,validate_join
from adapters.native_feature_observation import NativeFeatureObservation,exact,fresh,need,number
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_feature.history import pack,unpack,same
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.navigation_scene import validate_status as scene_status
from ios.adapters import navigation_process_context as process
from ios.adapters.navigation_admission_owner import SOURCES
from ios.adapters.navigation_fixture import NavigationFixtureReader
from ios.adapters.navigation_restart_proof import validate as restart_proof,OWNERS
from ios.adapters.navigation_scene_admission import validate as admission
from ios.adapters.graphics_history import follow_native

VERSION=1


class NavigationProcessOwner:
    def __init__(self,store,initial,before,receipt,owner_files,lock,guard,*,native=None,sources=None,fixture=None,
                 historical=False,epoch_ms=lambda:time.time()*1000,monotonic=time.monotonic):
        need(isinstance(store,PrivateFeatureState) and isinstance(lock,ScriptSourceLock) and callable(guard)
             and type(historical) is bool and callable(epoch_ms) and callable(monotonic))
        self.store,self.lock,self.historical=store,lock,historical
        self.initial=admission(initial);self.before=deepcopy(before)
        self.owner_files=[str(store.path.with_name(name)) for name in OWNERS]
        need(same(list(owner_files),self.owner_files) and store.path.name=='ios-navigation-process-context.json'
             and lock.path==store.path.with_name('script-feature-sources.lock'))
        self.receipt=restart_proof(receipt,self.owner_files);self.binding=deepcopy(self.receipt['input']['newBinding'])
        self.run=self.initial['runId'];self.guard=(lambda:True) if historical else guard
        self.native,self.sources,self.fixture=native,sources,fixture
        self.epoch_ms,self.monotonic=epoch_ms,monotonic
        need(same(self.initial['binding'],self.receipt['input']['oldBinding']))
        # The original pre-stop group is validated before any new-process read.
        from urllib.parse import urlsplit
        url=urlsplit(self.initial['providerInputs']['sceneUrl'])
        self.fixture_url=url.scheme+'://'+url.netloc+'/feature-fixture/v1/runs/'+self.run+'/'
        process.snapshot(self.initial,self.initial['binding'],self.before,self.fixture_url,floor=self.initial)
        follow_native(self.before['clockJoin']['nativeAfter'],self.receipt['oldNative'])
        if historical:need(native is sources is fixture is None)
        else:
            need(isinstance(native,NativeFeatureObservation) and native.ios and native.pid==int(self.binding['processIdentity'])
                 and isinstance(fixture,NavigationFixtureReader) and fixture.run==self.run
                 and fixture.instance==self.initial['providerInstance'] and same(fixture.inputs,self.initial['providerInputs'])
                 and fixture.fixture_url==self.fixture_url)
            exact(sources,SOURCES)
            for name,kind in SOURCES.items():
                need(isinstance(sources[name],kind))
                if name!='ui':need(sources[name].pid==native.pid)
            need(sources['replies'].ios)
        lock.assert_held();self.previous=store.read()
        self.state=None if self.previous is None else self.decode(self.previous);self.bound()

    def envelope(self,state):
        return dict(iosNavigationProcessOwnerVersion=VERSION,binding=self.binding,runId=self.run,
            initialAdmissionSha256=digest(self.initial),beforeSha256=digest(self.before),restartSha256=digest(self.receipt),
            ownerFiles=self.owner_files,payload=pack([state]))

    def decode(self,value):
        exact(value,{'iosNavigationProcessOwnerVersion','binding','runId','initialAdmissionSha256','beforeSha256','restartSha256','ownerFiles','payload'})
        rows=unpack(value['payload']);need(len(rows)==1 and same(value,self.envelope(rows[0])))
        state=rows[0];exact(state,{'phase','barrier','started','initialAdmission','before','restart','providerBefore','providerAfter','providerRead',
            'nativeStart','nativeEnd','originals','clockJoin','context'})
        need(state['phase'] in ('reading','transferred') and number(state['barrier'],1,1e15)
             and type(state['originals']) is dict and set(state['originals'])<=set(SOURCES))
        need(same(state['initialAdmission'],self.initial) and same(state['before'],self.before) and same(state['restart'],self.receipt))
        if state['phase']=='transferred':need(same(self.validate(state),state['context']))
        else:need(state['context'] is None)
        return state

    def bound(self):
        self.lock.assert_held();need(self.guard() is not False and same(self.store.read(),self.previous))

    def save(self):
        need(not self.historical);self.bound();value=self.envelope(self.state);self.decode(value)
        self.store.write(value,self.previous);need(same(self.store.read(),value));self.previous=deepcopy(value)

    def remember(self,key,value):
        need(self.state['phase']=='reading' and self.state[key] is None)
        self.state[key]=deepcopy(value);self.save()

    def validate(self,state):
        clock=validate_join(state['clockJoin'],state['originals'])
        need(same(state['nativeStart'],{key:clock[key] for key in
            ('clockJoinVersion','hostBeforeEpochMs','hostBeforeMonotonic','nativeBefore')})
            and same(state['nativeEnd'],{key:clock[key] for key in ('nativeAfter','hostAfterEpochMs','hostAfterMonotonic')}))
        before,after=state['providerBefore'],state['providerAfter'];read=state['providerRead'];start=state['started']
        exact(start,{'epoch','monotonic'});exact(read,{'epoch','monotonic'});epoch=read['epoch']
        scene_status(after,instance=self.initial['providerInstance'],run=self.run,scene_url=self.initial['providerInputs']['sceneUrl'],previous=before)
        need(same(before['ticket'],after['ticket']) and before['active'] and after['active']
             and number(epoch,clock['hostAfterEpochMs'],state['started']['epoch']+1500)
             and state['started']['epoch']>=state['barrier']
             and state['started']['monotonic']<=clock['hostBeforeMonotonic']
             and number(read['monotonic'],clock['hostAfterMonotonic'],start['monotonic']+1.5)
             and read['monotonic']-start['monotonic']<1.5
             and abs(epoch-start['epoch']-(read['monotonic']-start['monotonic'])*1000)<=250)
        fresh(before['capturedEpochMs'],int(state['started']['epoch']));fresh(after['capturedEpochMs'],int(epoch))
        after=dict(originals=state['originals'],clockJoin=clock,provider=after,missing=None)
        # Historical context-v1 originals keep their original version and shape.
        # Fresh acquisitions write v2; the owner envelope remains compatible.
        version=state['context']['iosNavigationProcessContextVersion'] if state['context'] is not None else process.VERSION
        return process.transfer(self.initial,self.before,self.receipt,after,self.owner_files,self.fixture_url,version=version)

    def acquire(self,host_barrier):
        need(not self.historical);self.bound();need(self.state is None and number(host_barrier,1,1e15))
        self.state=dict(phase='reading',barrier=host_barrier,started=dict(epoch=self.epoch_ms(),monotonic=self.monotonic()),
            initialAdmission=deepcopy(self.initial),before=deepcopy(self.before),restart=deepcopy(self.receipt),
            providerBefore=None,providerAfter=None,providerRead=None,nativeStart=None,nativeEnd=None,originals={},clockJoin=None,context=None)
        self.save();self.remember('providerBefore',self.fixture.scene())
        window=NativeClockAcquisition(self.native,epoch_ms=self.epoch_ms,monotonic=self.monotonic)
        window.begin(host_barrier);self.remember('nativeStart',window.started)
        follow_native(self.receipt['native'],window.started['nativeBefore'])
        for name,reader in self.sources.items():
            self.bound();value=reader.capture() if name=='ui' else reader.read(self.run)
            self.state['originals'][name]=deepcopy(value);self.save()
        ending=dict(nativeAfter=self.native.read(self.native.sequence),hostAfterEpochMs=self.epoch_ms(),hostAfterMonotonic=self.monotonic())
        self.remember('nativeEnd',ending)
        self.remember('clockJoin',dict(window.started,**ending,originalsSha256=digest(self.state['originals']),sourceTimes=[
            dict(source=name,field=field,epochMs=packet[field]) for name,packet in self.state['originals'].items()
            for field in ('capturedEpochMs','sampleEpochMs') if field in packet]))
        self.remember('providerAfter',self.fixture.scene())
        self.remember('providerRead',dict(epoch=self.epoch_ms(),monotonic=self.monotonic()))
        result=self.validate(self.state);self.state.update(phase='transferred',context=result);self.save()
        return self.for_input()

    def archive(self):
        self.bound();need(self.state is not None and self.state['phase']=='transferred')
        result=self.validate(self.state);need(same(result,self.state['context']));return deepcopy(result)

    def recover(self):
        """Adopt only a complete retained original group, without transport."""
        need(not self.historical);self.bound();need(self.state is not None and self.state['phase']=='reading')
        result=self.validate(self.state);self.state.update(phase='transferred',context=result);self.save()

    def for_input(self):
        need(not self.historical);value=self.archive();start=self.state['started'];clock=value['after']['clockJoin']
        basis=process.source_basis(value,self.owner_files)
        epoch,mono=self.epoch_ms(),self.monotonic()
        need(number(epoch,clock['hostAfterEpochMs'],start['epoch']+1500)
             and number(mono,clock['hostAfterMonotonic'],start['monotonic']+1.5)
             and epoch-start['epoch']<1500 and mono-start['monotonic']<1.5
             and abs(epoch-start['epoch']-(mono-start['monotonic'])*1000)<=250)
        self.bound();return basis
