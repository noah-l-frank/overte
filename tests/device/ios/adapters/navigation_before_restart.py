"""Retain fresh actual owned-scene originals before an ordinary restart.

This owner observes only. It cannot stop or launch an app, publish a result,
erase an interrupted acquisition or retire any input/image responsibility.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import time
from urllib.parse import urlsplit

from adapters.native_clock_join import NativeClockAcquisition,digest,validate_join
from adapters.native_feature_observation import exact,fresh,need,number
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_feature.history import pack,unpack,same
from feature_journeys.navigation_scene import validate_status as scene_status
from ios.adapters.navigation_admission_owner import NavigationAdmissionOwner,SOURCES
from ios.adapters.navigation_process_context import snapshot
from ios.adapters.navigation_scene_admission import validate as admission_original

VERSION=2
READS=(1,2)


class NavigationBeforeRestart:
    @classmethod
    def archive(cls,value,initial):
        """Original-only reconstruction after the old process has ended."""
        need(type(value) is dict)
        result=object.__new__(cls);result.initial=admission_original(initial)
        result.binding,result.run=result.initial['binding'],result.initial['runId']
        source=urlsplit(result.initial['providerInputs']['sceneUrl'])
        result.fixture_url=source.scheme+'://'+source.netloc+'/feature-fixture/v1/runs/'+result.run+'/'
        result.missing=deepcopy(value.get('missing'));result.state=result.decode(value)
        need(result.state['phase']=='observed');return result.group(result.state)

    def __init__(self,store,admission,*,missing=None,epoch_ms=lambda:time.time()*1000,monotonic=time.monotonic):
        need(isinstance(store,PrivateFeatureState) and isinstance(admission,NavigationAdmissionOwner)
            and not admission.historical and callable(epoch_ms) and callable(monotonic))
        admission.bound();self.store,self.admission=store,admission
        self.binding,self.run,self.lock=deepcopy(admission.binding),admission.run,admission.lock
        need(store.path==admission.store.path.with_name('ios-navigation-before-restart.json'))
        self.missing,self.epoch_ms,self.monotonic=deepcopy(missing),epoch_ms,monotonic
        self.initial=admission.archive();self._initial_sha=digest(self.initial)
        self.fixture_url=admission.fixture.fixture_url;self._admission_carrier=deepcopy(admission.previous)
        self.previous=store.read()
        self.state=None if self.previous is None else self.decode(self.previous)

    def envelope(self,state,version=VERSION):
        return dict(iosNavigationBeforeRestartVersion=version,binding=self.binding,runId=self.run,
            initialAdmissionSha256=digest(self.initial),fixtureUrl=self.fixture_url,missing=deepcopy(self.missing),payload=pack([state]))

    def group(self,state):
        value=dict(originals=deepcopy(state['originals']),clockJoin=deepcopy(state['clockJoin']),
            provider=deepcopy(state['providerAfter']),missing=deepcopy(self.missing))
        if state['addressOwner'] is not None:value['addressOwner']=deepcopy(state['addressOwner'])
        if state.get('surfaceOwner') is not None:value['surfaceOwner']=deepcopy(state['surfaceOwner'])
        return value

    def validate(self,state):
        need(set(state['originals'])==set(SOURCES) and all(state[key] is not None for key in
            ('clockJoin','nativeStart','nativeEnd','providerBefore','providerAfter','providerRead')))
        exact(state['providerRead'],{'epoch','monotonic'})
        clock=validate_join(state['clockJoin'],state['originals'])
        need(same(state['nativeStart'],{key:clock[key] for key in
            ('clockJoinVersion','hostBeforeEpochMs','hostBeforeMonotonic','nativeBefore')})
            and same(state['nativeEnd'],{key:clock[key] for key in
            ('nativeAfter','hostAfterEpochMs','hostAfterMonotonic')}))
        first,last=state['providerBefore'],state['providerAfter']
        for value,previous in ((first,None),(last,first)):
            scene_status(value,instance=self.initial['providerInstance'],run=self.run,
                scene_url=self.initial['providerInputs']['sceneUrl'],previous=previous)
        need(first['active'] and last['active'] and first['ticket']==last['ticket'])
        read=state['started'];exact(read,{'epoch','monotonic'})
        fresh(first['capturedEpochMs'],int(read['epoch']));fresh(last['capturedEpochMs'],int(state['providerRead']['epoch']))
        need(number(read['epoch'],1,clock['hostBeforeEpochMs']) and number(read['monotonic'],0,clock['hostBeforeMonotonic'])
            and number(state['providerRead']['epoch'],clock['hostAfterEpochMs'],read['epoch']+1500)
            and number(state['providerRead']['monotonic'],clock['hostAfterMonotonic'],read['monotonic']+1.5)
            and state['providerRead']['epoch']-read['epoch']<1500 and state['providerRead']['monotonic']-read['monotonic']<1.5)
        return snapshot(self.initial,self.binding,self.group(state),self.fixture_url,floor=self.initial)

    def decode(self,value):
        exact(value,{'iosNavigationBeforeRestartVersion','binding','runId','initialAdmissionSha256','fixtureUrl','missing','payload'})
        version=value['iosNavigationBeforeRestartVersion']
        rows=unpack(value['payload']);need(type(version) is int
            and version in READS and len(rows)==1 and same(value,self.envelope(rows[0],version)))
        state=rows[0];exact(state,{'phase','started','providerBefore','providerAfter','providerRead','nativeStart','nativeEnd',
            'originals','clockJoin','addressOwner','result'}|({'surfaceOwner'} if version>=2 else set()))
        need(state['phase'] in ('reading','observed') and type(state['originals']) is dict and set(state['originals'])<=set(SOURCES))
        if state['phase']=='observed':need(same(state['result'],self.validate(state)))
        else:need(state['result'] is None)
        if version==1:state=dict(state,surfaceOwner=None)
        return deepcopy(state)

    def bound(self):
        self.admission.bound();need(same(self.store.read(),self.previous)
            and same(self.admission.binding,self.binding) and self.admission.run==self.run
            and self.admission.fixture.fixture_url==self.fixture_url and digest(self.initial)==self._initial_sha
            and same(self.admission.previous,self._admission_carrier)
            and same(self.admission.envelope(self.admission.state),self._admission_carrier))

    def save(self):
        self.bound();value=self.envelope(self.state);self.decode(value)
        self.store.write(value,self.previous);need(same(self.store.read(),value));self.previous=deepcopy(value)

    def acquire(self):
        self.bound();need(self.state is None)
        self.state=dict(phase='reading',started=dict(epoch=self.epoch_ms(),monotonic=self.monotonic()),
            providerBefore=None,providerAfter=None,providerRead=None,nativeStart=None,nativeEnd=None,
            originals={},clockJoin=None,addressOwner=None,surfaceOwner=None,result=None);self.save()
        state=self.state;state['providerBefore']=self.admission.fixture.scene();self.save()
        window=NativeClockAcquisition(self.admission.native,epoch_ms=self.epoch_ms,monotonic=self.monotonic)
        window.begin(state['started']['epoch']);state['nativeStart']=deepcopy(window.started);self.save()
        for name in SOURCES:
            self.bound();reader=self.admission.sources[name]
            state['originals'][name]=reader.capture() if name=='ui' else reader.read(self.run);self.save()
        state['nativeEnd']=dict(nativeAfter=self.admission.native.read(self.admission.native.sequence),
            hostAfterEpochMs=self.epoch_ms(),hostAfterMonotonic=self.monotonic());self.save()
        state['clockJoin']=dict(window.started,**state['nativeEnd'],originalsSha256=digest(state['originals']),sourceTimes=[
            dict(source=name,field=field,epochMs=packet[field]) for name,packet in state['originals'].items()
            for field in ('capturedEpochMs','sampleEpochMs') if field in packet]);self.save()
        address=PrivateFeatureState(self.store.path.with_name('ios-navigation-address-'+self.binding['processIdentity']+'-inputs.json'))
        state['addressOwner']=deepcopy(address.read());self.save()
        surface=PrivateFeatureState(self.store.path.with_name('ios-navigation-surface-actions.json'))
        state['surfaceOwner']=deepcopy(surface.read());self.save()
        state['providerAfter']=self.admission.fixture.scene()
        state['providerRead']=dict(epoch=self.epoch_ms(),monotonic=self.monotonic());self.save()
        return self.recover()

    def recover(self):
        """Validate a fully retained group; incomplete reads remain owned."""
        self.bound();need(self.state is not None)
        if self.state['phase']=='reading':
            result=self.validate(self.state);self.state.update(phase='observed',result=result);self.save()
        return self.group(self.state)

    def for_input(self):
        self.bound();need(self.state is not None and self.state['phase']=='observed')
        self.validate(self.state);start=self.state['started'];epoch,mono=self.epoch_ms(),self.monotonic()
        need(number(epoch,self.state['providerRead']['epoch'],start['epoch']+1500)
            and number(mono,self.state['providerRead']['monotonic'],start['monotonic']+1.5)
            and epoch-start['epoch']<1500 and mono-start['monotonic']<1.5)
        return self.group(self.state)
