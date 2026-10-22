"""Explicit native/Qt/DOM models; real controlled HTTP resource bytes/receipts."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import secrets
from feature_journeys.browser_fixture import BrowserResources
from ios.adapters import world_web_source as source,world_web_dom as dom

RUN='a'*32
TICKET='b'*32
URL='http://127.0.0.1:43210/feature-fixture/v1/runs/'+RUN+'/'


class OriginalSources:
    def __init__(self,resource='reference.html',status_origin='primary',*,dom_version=2,transcript_version=source.VERSION,clock_ms=None,monotonic_ms=None,source_identity='actual-native-owner',run=RUN,ticket=TICKET,fixture_url=URL,origins=None,browser=None):
        self.run,self.ticket,self.fixture_url=run,ticket,fixture_url;self.transcript_version=transcript_version
        self.dom_version=dom_version;self.clock_ms=clock_ms;self.monotonic_ms=monotonic_ms
        self.epoch=100000;self.events=[];self.inputs=[];self.sequence=0;self.dom_sequence=0
        self.browser=BrowserResources(clock_ms=self.clock) if browser is None else browser
        if browser is None:self.browser.open(run)
        self.origins=dict(primary='http://127.0.0.1:43210',foreign='http://127.0.0.1:43211') if origins is None else deepcopy(origins)
        self.resource=resource;status,_mime,self.body,response=self.browser.resource(run,ticket,resource,origin=status_origin)
        self.url=self.origins[status_origin]+'/feature-fixture/v1/runs/'+run+'/tickets/'+ticket+'/'+resource
        self.identity=dict(handle='1',creation=1,grant=1,page=1,nonce='00000000-0000-4000-8000-000000000001',url=self.url,
            sourceUrl=fixture_url+'tickets/'+ticket+'/reference.html',sourceIdentity=source_identity,surface='world-entity')
        self.event('view-created',{},identity=self.identity|dict(page=0,nonce=''))
        self.event('document-began',dict(frame=self.url))
        self.event('dom-observer-installed',dict(sourceSha256=dom.SOURCE_PINS[dom_version],wrapperSha256='a'*64))
        self.event('main-response',dict(url=self.url,status=status,responseId=response,mimeType='text/html'))
        self.finished=self.event('native-finished',{})['clock']['epochMs'];self.event('document-verified',{})
        self.view={key:deepcopy(value) for key,value in self.identity.items() if key!='surface'}
        self.view.update(nativeFinished=True,httpErrorStatus=404 if status==404 else 0,inlineLease=False,
            httpStatus=status,responseId=response,finishedEpochMs=self.finished,observerSha256=dom.SOURCE_PINS[dom_version])
    def clock(self):
        if self.clock_ms is not None:self.epoch=self.clock_ms();return self.epoch
        self.epoch+=1;return self.epoch
    def stamp(self):
        epoch=self.clock();return dict(epochMs=epoch,monotonicMs=self.epoch-100000 if self.monotonic_ms is None else self.monotonic_ms())
    def event(self,kind,detail,*,identity=None):
        value=dict(sequence=len(self.events)+1,eventId=secrets.token_hex(16),kind=kind,clock=self.stamp(),
            identity=deepcopy(self.identity if identity is None else identity),detail=deepcopy(detail))
        self.events.append(value);return deepcopy(value)
    def ledger(self,request=None):
        self.sequence+=1;query=dict(schemaVersion=1,action=source.ACTION,commandId='ios-'+secrets.token_hex(16),runId=self.run,fixtureUrl=self.fixture_url) if request is None else request
        return dict(iosWorldWebVersion=self.transcript_version,commandId=query['commandId'],runId=self.run,fixtureUrl=self.fixture_url,instance='c'*32,
            sequence=self.sequence,processId=42,clockDomain='native-main-ios-world-web',clockBefore=self.stamp(),clockAfter=self.stamp(),
            complete=True,eventSequence=len(self.events),events=deepcopy(self.events))
    def document(self,request=None):
        self.dom_sequence+=1;query='ios-'+secrets.token_hex(16) if request is None else request['commandId'];stamp=self.clock()
        elements=[dict(id=key,birth=index,tag='INPUT' if key in ('text','foreign') else 'IMG' if key=='feature-marker' else 'BUTTON',
            type='text' if key=='text' else 'url' if key=='foreign' else '',rect=[10,10,90,90],enabled=True,visible=True,href=None)
            for index,key in enumerate(sorted(dom.IDS),1)]
        if self.dom_version>=2:
            for row in elements:row.update(focused=False,value='' if row['id'] in ('text','foreign') else None)
        body=dict(iosWorldWebDOMVersion=self.dom_version,requestId=query,instance='d'*32,sequence=self.dom_sequence,capturedEpochMs=stamp,
            document=dict(runId=self.run,href=self.url,responseId=self.view['responseId'],readyState='complete',title='Actual fixture title',width=100,height=100),
            editor=dict(text='',focused=False),elements=elements,events=deepcopy(self.inputs),echoes=[])
        return dict(iosWorldWebDOMNativeVersion=1,commandId=query,runId=self.run,surface='world',instance='e'*32,sequence=self.dom_sequence,
            processId=42,capturedEpochMs=self.clock(),status='ready',source=dict(nativeView=deepcopy(self.view),dom=body))
    def pointer(self,*,returned=True):
        entry=self.event('pointer-enter',dict(type='release',x=50,y=50,width=100,height=100,button=0,codeSha256='a'*64))
        birth=sorted(dom.IDS).index('bridge')+1
        for kind in ('mouseup','click'):
            self.inputs.append(dict(ordinal=len(self.inputs)+1,kind=kind,capturedEpochMs=self.clock(),eventTimeMs=self.epoch-100000,
                trusted=False,target=dict(id='bridge',birth=birth),x=50 if kind=='mouseup' else 0,y=50 if kind=='mouseup' else 0,button=0,key=None))
        if returned:
            self.event('callback-enter',dict(entry=entry['sequence'],result=dict(error=False,result=False)))
            self.event('callback-return',dict(entry=entry['sequence']))
        return entry
