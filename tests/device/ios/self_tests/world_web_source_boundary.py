"""Standalone typed native/Qt host boundary, without a feature owner.

Clocks and packets are produced at observation time. This boundary does not
import the unadvertised World Web orchestration or synthesize scenario effects.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
from feature_journeys.browser_fixture import BrowserResources
from ios.adapters import world_web_source
from ios.adapters.normal_input import NativeInput
from ios.self_tests.test_ios_world_web_marker_measurements import frames
from ios.self_tests.test_ios_create_files import BINDING
from self_tests.test_native_feature_observation import Boundary as NativeClock

RUN='a'*32
EPOCH=1700000000000
URL='http://controlled.invalid/feature-fixture/v1/runs/'+RUN+'/'


class SDK:
    def __init__(self):
        self.pid=42;self.run=RUN;self.binding=deepcopy(BINDING);self.base_epoch=EPOCH;self.time=1.;self.queries={};self.counts={};self.phase_sequence=0;self.ticket='1'*32;self.fail=None
        self.browser=BrowserResources(clock_ms=self.tick);self.browser.open(RUN);self.native=NativeClock()
        self.world=frames()[0];self.world['processId']=self.pid;self.world['source']['scriptOriginal']['processId']=self.pid
        self.world['source']['view']['aspectRatio']=1024/728
        self.widget=None;self.last_widget=None;self.widget_intents=[]
    def tick(self):self.time+=.001;return self.epoch()
    def epoch(self):return self.base_epoch+round(self.time*1000)
    def sleep(self,seconds):self.time+=seconds
    def activation_epoch(self):return getattr(self,'activated_epoch',self.base_epoch)
    def phase_epoch(self):self.tick();return getattr(self,'host_epoch',self.epoch)()
    def send(self,name,query):self.queries[name]=deepcopy(query)
    def clock_packet(self,value):value.update(processId=self.pid,requestedEpochMs=self.tick(),capturedEpochMs=self.epoch(),animation={},animationFence={})
    def phase(self,path,**kwargs):
        if path.endswith('/browser'):return self.browser.snapshot(self.run)
        self.phase_sequence+=1
        return dict(fixturePhaseVersion=1,instance='a'*32,sequence=self.phase_sequence,requestId=kwargs['phase_nonce'],runId=self.run,area='world-web',
            capturedEpochMs=self.phase_epoch(),active=getattr(self,'fixture_active',True),createdEpochMs=self.activation_epoch()-1,retiredEpochMs=getattr(self,'retired_epoch',None),activations=[dict(sequence=1,ticket=self.ticket,
                activatedEpochMs=self.activation_epoch(),stimulus=deepcopy(getattr(self,'stimulus',dict(verb='baseline',inputs={}))))])
    def original(self,name):
        if self.fail==name:raise OSError('modeled lost original native '+name)
        query=self.queries[name];self.counts[name]=self.counts.get(name,0)+1;before=self.tick()
        if name=='closures':
            return json.dumps(dict(iosWebClosureVersion=5,commandId=query['commandId'],runId=self.run,fixtureUrl=getattr(self,'fixture_url',URL),instance='d'*32,
                sequence=self.counts[name],processId=self.pid,capturedEpochMs=self.tick(),complete=True,contexts=[]),separators=(',',':'))
        a=dict(epochMs=before,monotonicMs=round(self.time*1000))
        if name=='world':
            value=deepcopy(self.world);script=value['source']['scriptOriginal']
            script.update(requestedEpochMs=self.tick(),capturedEpochMs=self.tick(),sequence=self.counts[name])
        elif name=='ledger':
            value=dict(iosWorldWebVersion=world_web_source.VERSION,commandId=query['commandId'],fixtureUrl=getattr(self,'fixture_url',URL),complete=True,eventSequence=0,events=[])
        elif name=='surfaces':
            value=dict(iosWorldWebSurfacesVersion=1,source=self.surface_cache.read())
        elif name=='geometry':
            view={key:deepcopy(self.world['source']['view'][key]) for key in ('position','rotation','fieldOfViewDegrees','aspectRatio','perspective')}
            view.update(uiWidth=1024,uiHeight=round(1024/view['aspectRatio']))
            value=dict(iosWorldWebGeometryVersion=1,source=dict(complete=True,tree=deepcopy(self.world['source']['tree']),entities=[],view=view))
        elif name=='work':value=dict(iosWorldWebWorkVersion=1,source=dict(complete=True,eventSequence=0,workers=[]))
        elif name=='keys':
            value=dict(iosWorldWebKeysVersion=2,source=dict(iosWorldWebKeySourceVersion=2,instance='e'*32,bornEpochMs=self.base_epoch-100,complete=True,
                startup=dict(observed=True,epochMs=self.base_epoch-90,monotonicMs=10,windowCount=0,modifiers=0),eventSequence=0,events=[],dispatches=[],
                pendingDispatches=0,down=[],ended=[],preedit=[],devices=[],targets=[],qtModifiers=0))
        elif name=='pointer':
            value=dict(iosPointerStateVersion=1,source=dict(iosPointerSourceVersion=1,instance='d'*32,bornEpochMs=self.base_epoch-100,complete=True,
                startup=dict(observed=True,epochMs=self.base_epoch-90,monotonicMs=10,windowCount=0,mouseButtons=0),eventSequence=0,events=[],dispatches=[],
                pendingDispatches=0,contacts=[],ends=[],devices=[],targets=[],qtMouseButtons=0,worldTapActive=False))
        elif name=='entities':
            value=dict(iosCreateEntitiesVersion=1,source=dict(calls=dict(createEntityCallsVersion=1,instance='d'*32,complete=True,events=[]),
                tree=dict(entityTreeLifetimesVersion=1,treeInstance=self.world['source']['tree']['treeInstance'],treeBornEpochMs=self.base_epoch-1000,complete=True,
                    eventSequence=0,observedEpochMs=self.tick(),observedMonotonicMs=round(self.time*1000),events=[],entities=[])))
        elif name=='uikit':
            stamp=self.tick();return json.dumps(dict(schemaVersion=1,commandId=query['commandId'],observation=dict(schemaVersion=1,
                sampleEpochMs=stamp,sampleSequence=self.counts[name],nativeUi=dict(valid=True,surfaceWidth=1024,surfaceHeight=768,
                    safeInsetLeft=0,safeInsetTop=20,safeInsetRight=0,safeInsetBottom=20,keyboardVisible=False,imeInsetBottom=0),window=dict(width=1024,height=728))))
        else:raise AssertionError(name)
        domain=dict(world='native-main-emote-world',ledger='native-main-ios-world-web',geometry='native-main-ios-world-web-geometry',
            work='native-main-ios-world-web-work',surfaces='native-main-ios-world-web-surfaces',keys='native-main-ios-world-web-keys',pointer='native-main-ios-pointer',entities='native-main-create-entities')[name]
        value.update(instance='c'*32,sequence=self.counts[name],processId=self.pid,runId=self.run,clockDomain=domain,
            clockBefore=a,clockAfter=dict(epochMs=self.tick(),monotonicMs=round(self.time*1000)))
        if name!='ledger':value['requestId']=query['commandId']
        return json.dumps(value,separators=(',',':'),ensure_ascii=False) if name in ('keys','work','geometry','ledger') else json.dumps(value)

    def native_widget(self,native):
        value=object.__new__(NativeInput)
        def capture(*,native_epoch_ms=None):
            query=dict(schemaVersion=1,commandId='ios-'+format(len(self.widget_intents)+1,'032x'),action='normal-ui-input',operation='observe')
            self.widget_intents.append(deepcopy(query));hook=getattr(value,'observe_intent',None)
            if hook is not None:hook(deepcopy(query))
            original=dict(schemaVersion=1,instance='00000000-0000-4000-8000-000000000001',frameSpace='qt-window-logical',processId=self.pid,sampleEpochMs=self.tick(),elapsedMs=round(self.time*1000),
                lastSequence=0,tabletShown=False,ready=True,controls=[])
            value.last_receipt=dict(schemaVersion=1,commandId=query['commandId'],observation=deepcopy(original))
            # Match the real NativeInput.capture: the independent actual native
            # clock is queried AFTER the original observational receipt.
            from ios.adapters.normal_input import observation
            epoch=(native_epoch_ms or (lambda:native.read(native.sequence)['capturedEpochMs']))()
            return observation(original,self.pid,epoch)
        value.capture=capture;return value

