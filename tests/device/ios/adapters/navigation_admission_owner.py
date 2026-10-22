"""Durable original admission acquisition, without scene/input mutation.

An unfinished attempt owns its partial originals. Reopening it never resends
reads or replaces the original native clock window with a newer envelope.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import time

from adapters.native_clock_join import NativeClockAcquisition,digest,validate_join
from adapters.native_feature_observation import NativeFeatureObservation,exact,fresh,need,number
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.script_feature.history import pack,unpack,same
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.contract import identifier
from feature_journeys.navigation_base_scene import validate_status as base_status
from ios.adapters import navigation_scene_admission as admission
from ios.adapters.navigation_fixture import NavigationFixtureReader
from ios.adapters.navigation_observation_owner import SOURCES as FIELD_SOURCES
from ios.adapters.navigation_state import IOSNavigationState
from ios.adapters.scene_inventory import IOSSceneInventory

VERSION=1
SOURCES=dict(inventory=IOSSceneInventory,navigation=IOSNavigationState,**FIELD_SOURCES)


class NavigationAdmissionOwner:
    def __init__(self,store,binding,run,lock,guard,*,native=None,sources=None,fixture=None,
                 historical=False,epoch_ms=lambda:time.time()*1000,monotonic=time.monotonic):
        need(isinstance(store,PrivateFeatureState) and isinstance(lock,ScriptSourceLock)
             and callable(guard) and callable(epoch_ms) and callable(monotonic) and type(historical) is bool)
        context(binding);identifier(run)
        need(store.path.name=='ios-navigation-scene-admission.json'
             and lock.path==store.path.parent/'script-feature-sources.lock')
        self.store,self.binding,self.run,self.lock=store,deepcopy(binding),run,lock
        self.historical=historical;self.guard=(lambda:True) if historical else guard
        self.native,self.sources,self.fixture=native,sources,fixture
        self.epoch_ms,self.monotonic=epoch_ms,monotonic
        self.pid=int(binding['processIdentity']);need(self.pid>0 and str(self.pid)==binding['processIdentity'])
        if historical:need(native is sources is fixture is None)
        else:
            need(isinstance(native,NativeFeatureObservation) and native.ios and native.pid==self.pid
                 and isinstance(fixture,NavigationFixtureReader) and fixture.run==run and fixture.instance is not None
                 and fixture.inputs['sourceRevision']==binding['sourceRevision'])
            exact(sources,SOURCES)
            for name,kind in SOURCES.items():
                need(isinstance(sources[name],kind))
                if name!='ui':need(sources[name].pid==self.pid)
            need(sources['replies'].ios)
        lock.assert_held();self.previous=store.read()
        self.state=None if self.previous is None else self.decode(self.previous);self.bound()

    def envelope(self,state):
        return dict(iosNavigationAdmissionOwnerVersion=VERSION,binding=self.binding,runId=self.run,payload=pack([state]))

    def decode(self,value):
        exact(value,{'iosNavigationAdmissionOwnerVersion','binding','runId','payload'})
        rows=unpack(value['payload']);need(len(rows)==1 and type(value['iosNavigationAdmissionOwnerVersion']) is int
             and value['iosNavigationAdmissionOwnerVersion']==VERSION and same(value,self.envelope(rows[0])))
        state=rows[0];exact(state,{'phase','hostBarrier','providerInstance','providerInputs','baseRead','base',
            'nativeStart','nativeEnd','originals','clockJoin','admission'})
        need(state['phase'] in ('reading','admitted') and type(state['originals']) is dict
             and set(state['originals'])<=admission.ORIGINALS and number(state['hostBarrier'],1,1e15))
        identifier(state['providerInstance']);return state

    def bound(self):
        self.lock.assert_held();need(self.guard() is not False and same(self.store.read(),self.previous))
        if not self.historical and self.state is not None:
            need(self.fixture.instance==self.state['providerInstance']
                 and same(self.fixture.inputs,self.state['providerInputs']))

    def save(self):
        need(not self.historical);self.bound();value=self.envelope(self.state);self.decode(value)
        self.store.write(value,self.previous);need(same(self.store.read(),value));self.previous=deepcopy(value);self.bound()

    def remember(self,key,value):
        need(self.state['phase']=='reading' and self.state[key] is None)
        self.state[key]=deepcopy(value);self.save()

    def validate(self):
        state=self.state;need(state is not None)
        clock=validate_join(state['clockJoin'],state['originals'])
        need(same(state['nativeStart'],{key:clock[key] for key in
             ('clockJoinVersion','hostBeforeEpochMs','hostBeforeMonotonic','nativeBefore')})
             and same(state['nativeEnd'],{key:clock[key] for key in
             ('nativeAfter','hostAfterEpochMs','hostAfterMonotonic')}))
        read=state['baseRead'];exact(read,{'hostBeforeEpochMs','hostAfterEpochMs','hostBeforeMonotonic','hostAfterMonotonic'})
        before,after=read['hostBeforeEpochMs'],read['hostAfterEpochMs']
        start,end=read['hostBeforeMonotonic'],read['hostAfterMonotonic']
        need(number(before,state['hostBarrier'],1e15) and number(after,before,before+1500)
             and number(start,0,1e15) and number(end,start,start+1.5) and end-start<1.5 and after-before<1500
             and abs(after-before-(end-start)*1000)<=250
             and after<=clock['hostBeforeEpochMs'] and end<=clock['hostBeforeMonotonic']
             and clock['hostAfterEpochMs']-before<1500 and clock['hostAfterMonotonic']-start<1.5)
        base_status(state['base'],instance=state['providerInstance'],scene_url=state['providerInputs']['sceneUrl'],
            source_revision=state['providerInputs']['sourceRevision'])
        fresh(state['base']['capturedEpochMs'],int(after))
        need(state['base']['capturedEpochMs']>=before-1)
        return admission.admit(self.run,self.binding,state['originals'],clock,state['base'],
            provider_instance=state['providerInstance'],provider_inputs=state['providerInputs'])

    def acquire(self,host_barrier):
        need(not self.historical);self.bound();need(self.state is None and number(host_barrier,1,1e15))
        self.state=dict(phase='reading',hostBarrier=host_barrier,providerInstance=self.fixture.instance,
            providerInputs=deepcopy(self.fixture.inputs),baseRead=None,base=None,nativeStart=None,nativeEnd=None,
            originals={},clockJoin=None,admission=None)
        self.save()
        first=dict(hostBeforeEpochMs=self.epoch_ms(),hostBeforeMonotonic=self.monotonic())
        self.remember('base',self.fixture.base_scene())
        self.remember('baseRead',dict(first,hostAfterEpochMs=self.epoch_ms(),hostAfterMonotonic=self.monotonic()))
        window=NativeClockAcquisition(self.native,epoch_ms=self.epoch_ms,monotonic=self.monotonic)
        window.begin(host_barrier);self.remember('nativeStart',window.started)
        for name in SOURCES:
            self.bound();reader=self.sources[name]
            packet=reader.capture() if name=='ui' else reader.read(self.run)
            need(name not in self.state['originals']);self.state['originals'][name]=deepcopy(packet);self.save()
        # Retain the actual closing original before any join can fail.
        ending=dict(nativeAfter=self.native.read(self.native.sequence),hostAfterEpochMs=self.epoch_ms(),
                    hostAfterMonotonic=self.monotonic())
        self.remember('nativeEnd',ending)
        originals=self.state['originals']
        self.remember('clockJoin',dict(window.started,**ending,originalsSha256=digest(originals),sourceTimes=[
            dict(source=name,field=field,epochMs=packet[field]) for name,packet in originals.items()
            for field in ('capturedEpochMs','sampleEpochMs') if field in packet]))
        proof=self.validate();self.state.update(phase='admitted',admission=proof);self.save()
        return self.for_input()

    def archive(self):
        self.bound();need(self.state is not None and self.state['phase']=='admitted')
        value=self.validate();need(same(value,self.state['admission']));self.bound();return deepcopy(value)

    def recover(self):
        """Only a fully retained lost return; partial acquisition stays owned."""
        need(not self.historical);self.bound();need(self.state is not None and self.state['phase']=='reading')
        value=self.validate();self.state.update(phase='admitted',admission=value);self.save()

    def for_input(self):
        """Original freshness gate, never historical validation as a new read.

        The caller must still journal each normal input before delivery. This
        method sends nothing and does not discharge any cleanup obligation.
        """
        need(not self.historical);value=self.archive();clock=value['clockJoin']
        epoch,mono=self.epoch_ms(),self.monotonic();read=self.state['baseRead']
        need(number(epoch,clock['hostAfterEpochMs'],read['hostBeforeEpochMs']+1500)
             and number(mono,clock['hostAfterMonotonic'],read['hostBeforeMonotonic']+1.5)
             and epoch-read['hostBeforeEpochMs']<1500 and mono-read['hostBeforeMonotonic']<1.5
             and abs(epoch-read['hostBeforeEpochMs']-(mono-read['hostBeforeMonotonic'])*1000)<=250)
        self.bound();return value
