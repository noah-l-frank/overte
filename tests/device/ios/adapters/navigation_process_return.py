"""One-send ordinary static return from an independently proven new process.

Current source floors and the original static admission remain separate. A
delivery result establishes no restored scene, rendered effect or final cleanup.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import time
from urllib.parse import quote

from adapters.native_clock_join import NativeClockAcquisition,digest,validate_join
from adapters.native_feature_observation import exact,fresh,need,number
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUI
from adapters.script_feature.history import pack,unpack,same
from ios.adapters.navigation_address_inputs import NavigationAddressInputs,transfer_original
from ios.adapters.navigation_process_scope import NavigationProcessScope
from ios.adapters.navigation_scene_scope import owned
from ios.adapters.normal_input import NativeInput
from ios.adapters.normal_navigation import PROFILE
from navigation_observation import viewpoint_urls

VERSION=1


class NavigationProcessReturn:
    def __init__(self,store,scope,ui,native,*,epoch_ms=lambda:time.time()*1000,monotonic=time.monotonic):
        need(isinstance(scope,NavigationProcessScope) and isinstance(store,PrivateFeatureState)
            and isinstance(ui,NativeUI) and isinstance(native,NativeInput)
            and all(callable(fn) for fn in (epoch_ms,monotonic)))
        scope.bound();self.store,self.scope,self.ui,self.native=store,scope,ui,native
        self.binding,self.run,self.lock=scope.binding,scope.run,scope.lock
        need(store.path==scope.store.path.with_name('ios-navigation-process-return-'+self.binding['processIdentity']+'.json')
            and native.session==self.binding['sessionId'] and ui.base=='/session/'+quote(self.binding['sessionId'],safe=''))
        self.epoch_ms,self.monotonic=epoch_ms,monotonic
        self.previous=store.read();self.state=None if self.previous is None else self.decode(self.previous)

    def envelope(self,state):
        return dict(iosNavigationProcessReturnVersion=VERSION,binding=self.binding,runId=self.run,
            processOwnerSha256=digest(self.scope.owner.store.read()),
            originalAdmissionSha256=digest(self.scope.original_admission()),payload=pack([state]))

    def gate(self,value):
        exact(value,{'provider','providerRead','nativeStart','nativeEnd','originals','clockJoin','result'})
        clock=validate_join(value['clockJoin'],value['originals'])
        need(same(value['nativeStart'],{key:clock[key] for key in
            ('clockJoinVersion','hostBeforeEpochMs','hostBeforeMonotonic','nativeBefore')})
            and same(value['nativeEnd'],{key:clock[key] for key in
            ('nativeAfter','hostAfterEpochMs','hostAfterMonotonic')}))
        read=value['providerRead'];exact(read,{'epoch','monotonic'})
        need(number(read['epoch'],1,clock['hostBeforeEpochMs']) and number(read['monotonic'],0,clock['hostBeforeMonotonic'])
            and clock['hostAfterEpochMs']-read['epoch']<1500 and clock['hostAfterMonotonic']-read['monotonic']<1.5)
        fresh(value['provider']['capturedEpochMs'],int(read['epoch']))
        self.scope.ui_original(value['originals']['ui'])
        # This explicit typed basis belongs to the proven current process.
        # It is never sent through the static-admission validator.
        basis=self.scope.archive();old=basis['originals']['navigation']['source'];current=value['originals']['navigation']['source']
        need(current['view']['mode']==old['view']['mode'] and abs(current['avatar']['modelScale']-old['avatar']['modelScale'])<.00001)
        return owned(basis,value['originals'],clock,value['provider'],self.scope.fixture.fixture_url)

    def address(self):
        return PrivateFeatureState(self.store.path.with_name('ios-navigation-address-'+self.binding['processIdentity']+'-inputs.json'))

    def delivery(self,state):
        original=state['addressOwner'];need(original is not None and state['returnedUi'] is not None and state['beforeUi'] is not None)
        transfer_original(original,self.binding,self.run,state['returnedUi'])
        rows=unpack(original['payload'])[0]['rows'];need(rows[-1]['key']=='return'
            and rows[-1]['url']==viewpoint_urls(self.scope.original_admission()['base']['url'])['A'])
        before,after=state['beforeUi'],state['returnedUi'];self.scope.ui_original(before);self.scope.ui_original(after)
        need(after['lastSequence']==before['lastSequence']+1 and after['sampleEpochMs']>=before['sampleEpochMs'])

    def decode(self,value):
        exact(value,{'iosNavigationProcessReturnVersion','binding','runId','processOwnerSha256','originalAdmissionSha256','payload'})
        rows=unpack(value['payload']);need(type(value['iosNavigationProcessReturnVersion']) is int
            and value['iosNavigationProcessReturnVersion']==VERSION and len(rows)==1 and same(value,self.envelope(rows[0])))
        state=rows[0];exact(state,{'phase','gate','beforeUi','returnedUi','addressOwner'})
        need(state['phase'] in ('checking','issued','delivered'))
        exact(state['gate'],{'provider','providerRead','nativeStart','nativeEnd','originals','clockJoin','result'})
        need(type(state['gate']['originals']) is dict and set(state['gate']['originals'])<={'inventory','navigation','ui'})
        if state['gate']['result'] is not None:need(same(state['gate']['result'],self.gate(state['gate'])))
        if state['phase']!='checking':need(state['gate']['result'] is not None and state['beforeUi'] is not None)
        if state['beforeUi'] is not None:
            self.scope.ui_original(state['beforeUi'])
            floor=state['gate']['originals'].get('ui');need(floor is not None
                and state['beforeUi']['lastSequence']>=floor['lastSequence']
                and state['beforeUi']['sampleEpochMs']>=floor['sampleEpochMs'])
        if state['phase']=='delivered':self.delivery(state)
        else:need(state['returnedUi'] is state['addressOwner'] is None)
        return deepcopy(state)

    def bound(self):self.scope.bound();need(same(self.store.read(),self.previous))

    def save(self):
        self.bound();value=self.envelope(self.state);self.decode(value)
        self.store.write(value,self.previous);need(same(self.store.read(),value));self.previous=deepcopy(value)

    def return_to_original(self):
        self.bound()
        if self.state is not None:
            need(self.state['phase']=='delivered');return {'performed':True}
        self.state=dict(phase='checking',beforeUi=None,returnedUi=None,addressOwner=None,
            gate=dict(provider=None,providerRead=None,nativeStart=None,nativeEnd=None,originals={},clockJoin=None,result=None))
        self.save();gate=self.state['gate'];gate['provider']=self.scope.fixture.scene();self.save()
        gate['providerRead']=dict(epoch=self.epoch_ms(),monotonic=self.monotonic());self.save()
        window=NativeClockAcquisition(self.scope.native,epoch_ms=self.epoch_ms,monotonic=self.monotonic)
        window.begin(gate['providerRead']['epoch']);gate['nativeStart']=deepcopy(window.started);self.save()
        for name in ('inventory','navigation','ui'):
            self.bound();reader=self.scope.sources[name]
            gate['originals'][name]=reader.capture() if name=='ui' else reader.read(self.run);self.save()
        gate['nativeEnd']=dict(nativeAfter=self.scope.native.read(self.scope.native.sequence),
            hostAfterEpochMs=self.epoch_ms(),hostAfterMonotonic=self.monotonic());self.save()
        gate['clockJoin']=dict(window.started,**gate['nativeEnd'],originalsSha256=digest(gate['originals']),sourceTimes=[
            dict(source=name,field=field,epochMs=packet[field]) for name,packet in gate['originals'].items()
            for field in ('capturedEpochMs','sampleEpochMs') if field in packet]);self.save()
        gate['result']=self.gate(gate);self.save()
        self.state['beforeUi']=self.native.capture();self.save()
        self.state['phase']='issued';self.save();self.fresh_gate()
        profile=dict(contractVersion=1,profile=PROFILE,sceneUrl=self.scope.archive()['providerInputs']['sceneUrl'])
        initial=self.scope.original_admission();url=viewpoint_urls(initial['base']['url'])['A']
        allowed=set(viewpoint_urls(profile['sceneUrl']).values())|set(viewpoint_urls(initial['base']['url']).values())
        def input_guard():
            self.bound();self.fresh_gate()
        child=NavigationAddressInputs(self.address(),self.binding,self.run,self.lock,input_guard,self.ui,self.native,
            epoch_ms=self.epoch_ms,monotonic=self.monotonic)
        result=child.goto('return',url,profile,allowed)
        self.state.update(phase='delivered',returnedUi=deepcopy(result['original']),addressOwner=deepcopy(child.store.read()))
        self.save();return {'performed':True}

    def fresh_gate(self):
        read=self.state['gate']['providerRead'];clock=self.state['gate']['clockJoin'];epoch,mono=self.epoch_ms(),self.monotonic()
        need(number(epoch,clock['hostAfterEpochMs'],read['epoch']+1500)
            and number(mono,clock['hostAfterMonotonic'],read['monotonic']+1.5)
            and epoch-read['epoch']<1500 and mono-read['monotonic']<1.5)

    def recover_return(self):
        """Adopt an actual complete child original without an SDK read or input."""
        self.bound();need(self.state is not None and self.state['phase']=='issued')
        original=self.address().read();need(original is not None)
        checker=object.__new__(NavigationAddressInputs);checker.binding=self.binding;checker.run=self.run
        child=checker.decode(original);need(child['rows'] and child['rows'][-1]['key']=='return'
            and child['rows'][-1]['phase']=='acknowledged')
        state=deepcopy(self.state);state.update(phase='delivered',addressOwner=original,
            returnedUi=deepcopy(child['rows'][-1]['closed']['original']))
        self.delivery(state);self.state=state;self.save();return {'performed':True}
