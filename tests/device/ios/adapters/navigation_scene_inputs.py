"""One-send normal Go To scene entry/return; acknowledgments are not effects."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
import time
from urllib.parse import quote

from adapters.native_clock_join import NativeClockAcquisition,digest,validate_join
from adapters.native_feature_observation import exact,fresh,need,number
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUI
from adapters.script_feature.history import pack,unpack,same
from ios.adapters.navigation_admission_owner import NavigationAdmissionOwner
from ios.adapters import navigation_state,scene_inventory,navigation_ui
from ios.adapters.navigation_challenge import marker
from ios.adapters.normal_input import NativeInput,observation as ui_packet
from ios.adapters.normal_navigation import IOSNavigation,PROFILE
from ios.adapters.graphics_history import follow_native
from feature_journeys.navigation_scene import scene,marker_id
from navigation_observation import viewpoint_urls,same_viewpoint

VERSION=1


def return_gate(proof,originals,clock,provider,fixture_url):
    """Necessary ownership before replacing a scene, not restored-world proof."""
    from ios.adapters.navigation_scene_admission import validate
    validate(proof);exact(originals,{'inventory','navigation','ui'});validate_join(clock,originals)
    binding,run=proof['binding'],proof['runId'];process=int(binding['processIdentity'])
    first,last=clock['nativeBefore'],clock['nativeAfter'];follow_native(proof['clockJoin']['nativeAfter'],first)
    need(first['processId']==last['processId']==process and same(first['lifecycle'],last['lifecycle']))
    inventory,navigation,ui=(originals[name] for name in ('inventory','navigation','ui'))
    for name,module in (('inventory',scene_inventory),('navigation',navigation_state)):
        packet=originals[name]
        module.validate(packet,dict(schemaVersion=1,commandId=packet['requestId'],action=module.ACTION,runId=run),
            process,last['capturedEpochMs'],proof['originals'][name])
        need(first['capturedEpochMs']<=packet['clockBefore']['epochMs']<=packet['clockAfter']['epochMs']<=last['capturedEpochMs'])
    need(ui['processId']==process and ui['instance']==proof['originals']['ui']['instance']
         and ui['lastSequence']>=proof['originals']['ui']['lastSequence']
         and first['capturedEpochMs']<=ui['sampleEpochMs']<=last['capturedEpochMs']
         and not ui['tabletShown'] and not navigation_ui.project(ui)['addressDialog']
         and not any(row['id'].startswith('navigation.error.') for row in ui['controls']))
    source=navigation['source'];url=source['sceneUrl'];urls=viewpoint_urls(proof['providerInputs']['sceneUrl'])
    labels=[label for label,wanted in urls.items() if same_viewpoint(url,wanted)];need(len(labels)==1)
    navigation_state.pose_ready(navigation,url,labels[0])
    actual,scene_ticket=marker(dict(frame=dict(navigationAfter=navigation),fixtureUrl=fixture_url,url=url,
        provider=provider,providerInstance=proof['providerInstance'],ticket=provider['ticket']),run)
    anchor=scene_inventory.unchanged_since_commit(inventory,url)
    raw=json.dumps(scene(run,scene_ticket,fixture_url),separators=(',',':'),ensure_ascii=False).encode()
    need(anchor['bodyBytes']==len(raw) and anchor['bodySha256']==hashlib.sha256(raw).hexdigest()
         and set(scene_inventory.semantics(inventory))==set(navigation_state.MARKER_IDS)|{marker_id(run)}
         and inventory['clockAfter']['epochMs']<=navigation['clockBefore']['epochMs'])
    before,after=inventory['source']['sceneLoads'],source['sceneLoads']
    need(all(same(before[key],after[key]) for key in
         ('instance','processId','runId','currentGeneration','pendingLeases','complete','requests'))
         and before['sequence']<after['sequence'] and before['capturedEpochMs']<=after['capturedEpochMs'])
    return dict(originalsSha256=digest(originals),commit=anchor,sceneTicket=scene_ticket,marker=actual)


class NavigationSceneInputs:
    def __init__(self,store,admission,ui,native,*,epoch_ms=lambda:time.time()*1000,monotonic=time.monotonic):
        need(isinstance(store,PrivateFeatureState) and isinstance(admission,NavigationAdmissionOwner)
             and not admission.historical and isinstance(ui,NativeUI) and isinstance(native,NativeInput)
             and callable(epoch_ms) and callable(monotonic))
        need(store.path.name=='ios-navigation-scene-inputs.json' and store.path.parent==admission.store.path.parent)
        self.store,self.admission,self.ui,self.native=store,admission,ui,native
        self.binding,self.run,self.lock=admission.binding,admission.run,admission.lock
        need(native.session==self.binding['sessionId'] and ui.base=='/session/'+quote(self.binding['sessionId'],safe=''))
        self.epoch_ms,self.monotonic=epoch_ms,monotonic
        self.lock.assert_held();self.previous=store.read()
        self.state=None if self.previous is None else self.decode(self.previous);self.bound()

    def envelope(self,state):
        return dict(iosNavigationSceneInputsVersion=VERSION,binding=self.binding,runId=self.run,payload=pack([state]))

    def decode(self,value):
        exact(value,{'iosNavigationSceneInputsVersion','binding','runId','payload'})
        rows=unpack(value['payload']);need(len(rows)==1 and type(value['iosNavigationSceneInputsVersion']) is int
            and value['iosNavigationSceneInputsVersion']==VERSION and same(value,self.envelope(rows[0])))
        state=rows[0];exact(state,{'admissionSha256','phase','component','enterUi','enteredUi','returnedUi','gate'})
        need(state['phase'] in ('enter-issued','entered','return-checking','return-issued','return-delivered')
             and type(state['component']) is dict and set(state['component'])<= {'iosNormalNavigation'})
        need(state['admissionSha256']==digest(self.admission.store.read()))
        original=self.admission.archive()['originals']['ui']
        for key in ('enterUi','enteredUi','returnedUi'):
            packet=state[key]
            if packet is None:continue
            ui_packet(packet,int(self.binding['processIdentity']),packet.get('sampleEpochMs'))
            need(packet['instance']==original['instance'] and packet['lastSequence']>=original['lastSequence'])
        if state['phase']!='enter-issued':
            need(state['enterUi'] is not None and state['enteredUi'] is not None
                 and state['enteredUi']['lastSequence']==state['enterUi']['lastSequence']+1
                 and state['enteredUi']['sampleEpochMs']>=state['enterUi']['sampleEpochMs'])
        if state['phase'].startswith('return-'):need(type(state['gate']) is dict)
        else:need(state['gate'] is None)
        if state['phase']=='return-delivered':need(state['returnedUi'] is not None
            and state['returnedUi']['lastSequence']>state['enteredUi']['lastSequence'])
        else:need(state['returnedUi'] is None)
        return state

    def bound(self):
        self.admission.bound();need(same(self.store.read(),self.previous))
        if self.state is not None:need(self.state['admissionSha256']==digest(self.admission.store.read()))

    def save(self):
        self.bound();value=self.envelope(self.state);self.decode(value)
        self.store.write(value,self.previous);need(same(self.store.read(),value));self.previous=deepcopy(value);self.bound()

    def normal(self,url):
        proof=self.admission.archive();profile=dict(contractVersion=1,profile=PROFILE,sceneUrl=proof['providerInputs']['sceneUrl'])
        started=self.monotonic();need(number(started,0,1e15))
        def check():
            self.bound();self.ui._check();now=self.monotonic()
            need(number(now,started,started+30) and now-started<30)
        check();packet=self.native.capture();check()
        need(packet['instance']==proof['originals']['ui']['instance'] and packet['processId']==int(self.binding['processIdentity'])
             and packet['lastSequence']>=proof['originals']['ui']['lastSequence'])
        if self.state['phase']=='enter-issued' and self.state['enterUi'] is None:
            self.state['enterUi']=deepcopy(packet);self.save();self.admission.for_input()
        ui=NativeUI(self.ui.client,self.binding['sessionId'],check,timeout=self.ui.timeout,
            monotonic=self.ui.monotonic,sleep=self.ui.sleep)
        flow=IOSNavigation(ui,self.native,profile,self.state['component'],self.save)
        # Both routes are closed inputs on the same admitted provider. Preserve
        # the existing component's original context while allowing the static
        # return route; no arbitrary URL or product setter enters this scope.
        flow.urls=set(viewpoint_urls(profile['sceneUrl']).values())|set(viewpoint_urls(proof['base']['url']).values())
        need(url in flow.urls);flow.invoke('places.goto',dict(url=url));check()
        last=self.native.capture();check()
        need(last['instance']==packet['instance'] and last['lastSequence']==packet['lastSequence']+1
             and last['sampleEpochMs']>=packet['sampleEpochMs'])
        return last

    def enter(self):
        self.bound();proof=self.admission.archive()
        if self.state is not None:
            need(self.state['phase']=='entered');return {'performed':True}
        self.admission.for_input()
        self.state=dict(admissionSha256=digest(self.admission.store.read()),phase='enter-issued',component={},
            enterUi=None,enteredUi=None,returnedUi=None,gate=None)
        self.save();self.admission.for_input()
        url=viewpoint_urls(proof['providerInputs']['sceneUrl'])['A'];self.state['enteredUi']=self.normal(url)
        self.state['phase']='entered';self.save();return {'performed':True}

    def validate_gate(self):
        gate=self.state['gate'];exact(gate,{'provider','providerRead','nativeStart','nativeEnd','originals','clockJoin','result'})
        clock=gate['clockJoin'];validate_join(clock,gate['originals'])
        need(same(gate['nativeStart'],{key:clock[key] for key in
             ('clockJoinVersion','hostBeforeEpochMs','hostBeforeMonotonic','nativeBefore')})
             and same(gate['nativeEnd'],{key:clock[key] for key in
             ('nativeAfter','hostAfterEpochMs','hostAfterMonotonic')}))
        read=gate['providerRead'];exact(read,{'epoch','monotonic'})
        need(number(read['epoch'],1,clock['hostBeforeEpochMs']) and number(read['monotonic'],0,clock['hostBeforeMonotonic'])
             and clock['hostAfterEpochMs']-read['epoch']<1500 and clock['hostAfterMonotonic']-read['monotonic']<1.5)
        fresh(gate['provider']['capturedEpochMs'],int(read['epoch']))
        before,after=self.state['enteredUi'],gate['originals']['ui'];need(before is not None
            and before['instance']==after['instance'] and before['processId']==after['processId']
            and before['lastSequence']<=after['lastSequence'] and before['sampleEpochMs']<=after['sampleEpochMs'])
        return return_gate(self.admission.archive(),gate['originals'],clock,gate['provider'],self.admission.fixture.fixture_url)

    def return_to_original(self):
        self.bound();need(self.state is not None)
        if self.state['phase']=='return-delivered':return {'performed':True}
        need(self.state['phase']=='entered')
        self.state.update(phase='return-checking',gate=dict(provider=None,providerRead=None,nativeStart=None,
            nativeEnd=None,originals={},clockJoin=None,result=None));self.save();gate=self.state['gate']
        gate['provider']=self.admission.fixture.scene();self.save()
        gate['providerRead']=dict(epoch=self.epoch_ms(),monotonic=self.monotonic());self.save()
        window=NativeClockAcquisition(self.admission.native,epoch_ms=self.epoch_ms,monotonic=self.monotonic)
        window.begin(gate['providerRead']['epoch']);gate['nativeStart']=deepcopy(window.started);self.save()
        for name in ('inventory','navigation','ui'):
            self.bound();reader=self.admission.sources[name]
            gate['originals'][name]=reader.capture() if name=='ui' else reader.read(self.run);self.save()
        gate['nativeEnd']=dict(nativeAfter=self.admission.native.read(self.admission.native.sequence),
            hostAfterEpochMs=self.epoch_ms(),hostAfterMonotonic=self.monotonic());self.save()
        gate['clockJoin']=dict(window.started,**gate['nativeEnd'],originalsSha256=digest(gate['originals']),sourceTimes=[
            dict(source=name,field=field,epochMs=packet[field]) for name,packet in gate['originals'].items()
            for field in ('capturedEpochMs','sampleEpochMs') if field in packet]);self.save()
        gate['result']=self.validate_gate();self.save()
        read=gate['providerRead'];epoch,mono=self.epoch_ms(),self.monotonic()
        need(number(epoch,gate['clockJoin']['hostAfterEpochMs'],read['epoch']+1500)
             and number(mono,gate['clockJoin']['hostAfterMonotonic'],read['monotonic']+1.5)
             and epoch-read['epoch']<1500 and mono-read['monotonic']<1.5)
        self.state['phase']='return-issued';self.save()
        need(self.epoch_ms()-read['epoch']<1500 and self.monotonic()-read['monotonic']<1.5)
        self.state['returnedUi']=self.normal(viewpoint_urls(self.admission.archive()['base']['url'])['A'])
        self.state['phase']='return-delivered';self.save();return {'performed':True}
