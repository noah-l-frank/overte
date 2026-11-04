"""Declared bounded source for ONE positive HOST CurrentDocument component.

It creates no Qt/Android/device/current-product fact or input. Scope/clock
context is born explicitly before any query; produced packets are never
rewritten. Real owned file/OFD/source-literal lineage is exercised on host.
The stage resource API must be selected and funded before its constructor.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0

VERSION=1  # Internal HOST contract; no public/native capability.
from dataclasses import dataclass
import os,re
from adapters.host_process_identity import host_identity
from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.pico4.lifecycle_process_file import LifecycleProcessFile
from adapters.pico4.world_current_document import command
from adapters.pico4.browser_source import fixture
from adapters.pico4.assets_raw_archive import quoted_bytes
from adapters.script_journey.history import canonical


@dataclass(frozen=True,eq=False)
class WorldDocumentModelContext1:
    run:str
    fixture_url:str
    owner:str
    instance:str
    item:str
    dom:str
    response:str
    entity:str
    ticket:str

    def validate(self):
        need(type(self) is WorldDocumentModelContext1);fixture(self.run,self.fixture_url)
        for name in ('run','owner','instance','item','dom','response','ticket'):
            value=getattr(self,name);need(type(value) is str and re.fullmatch('[0-9a-f]{32}',value))
        need(type(self.entity) is str and re.fullmatch('[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}',self.entity))
    @property
    def url(self):return self.fixture_url+'tickets/'+self.ticket+'/index.html'
    def model_work(self):
        self.validate();u=quoted_bytes(self.url)
        q=max(quoted_bytes(getattr(self,name)) for name in ('run','owner','instance','item','dom','response','entity','ticket'))
        bound=16384+64*u+128*q
        return 44*bound+524288


class WorldDocumentFileModel1:
    def __init__(self,stage,context):
        need(type(context) is WorldDocumentModelContext1);context.validate()
        self.stage,self.context=stage,context
        self.process=host_identity();self.pid=os.getpid()
        self.sequence=0;self.packet=self.request=None
        self.alive=True;self.native_grant=2;self.original_grant=1;self.page=self.creation=1
        self.store=PrivateFeatureState(stage.parent.root/'pico-world-current-host-model-source.json')
        self.file=object.__new__(LifecycleProcessFile)
        # stage.model must already be this original object before __init__.
        need(stage.model is self and stage.model_credit>=context.model_work())
        LifecycleProcessFile.__init__(self.file,self.store)
        need(self.file.file is None)
        self.finished_epoch=stage.native_epoch_ms()  # Once at document birth.
        self.guard()

    def guard(self):
        need(self.stage.model is self and self.process==host_identity() and self.pid==os.getpid() and self.alive)
        self.context.validate();self.stage.model_identity(self)
        need(type(self.sequence) is int and 0<=self.sequence<=9007199254740991
            and all(type(v) is int and 1<=v<=9007199254740991 for v in (self.creation,self.page,self.native_grant,self.original_grant,self.finished_epoch)))
        self.file.guard();return True

    def snapshot(self):
        c=self.context
        base=dict(handle='1',creation=self.creation,grant=self.native_grant,page=self.page,url=c.url,sourceUrl=c.url)
        native=dict(base,itemInstance=c.item,sourceIdentity='web-entity:'+c.entity,
            created=True,authorized=True,sessionActive=True,suspended=False,loading=False,
            capturedEpochMs=self.stage.native_epoch_ms(),capturedMonotonicMs=self.stage.native_monotonic_ms())
        java=dict(base,ownerCurrent=True,active=True,foreground=True,windowFocused=True,
            destroyed=False,closing=False,loading=False,capturedEpochMs=self.stage.native_epoch_ms(),
            capturedElapsedMs=self.stage.native_monotonic_ms())
        return dict(native=native,java=java)

    def send(self,request):
        # Entire model producer credit BEFORE its clock/guard/copy/builder/IO.
        self.stage.model_before_produce(self,request)
        command(request);self.guard();c=self.context
        need(request['runId']==c.run and request['ownerToken']==c.owner and request['fixtureUrl']==c.fixture_url)
        need(self.sequence<9007199254740991)
        epoch=self.stage.native_epoch_ms();monotonic=self.stage.native_monotonic_ms()
        self.sequence+=1
        before=self.snapshot()
        dom=dict(webDOMVersion=1,requestId=request['commandId'],instance=c.dom,sequence=self.sequence,
            capturedEpochMs=self.stage.native_epoch_ms(),document=dict(runId=c.run,href=c.url,responseId=c.response,readyState='complete'),
            editor=dict(text='',focused=False),attempts=[],echoes=[])
        after=self.snapshot()
        finish=dict(handle='1',creation=self.creation,grant=self.original_grant,page=self.page,url=c.url,finishedEpochMs=self.finished_epoch)
        import json
        transaction=dict(before=before['java'],domRaw=json.dumps(json.dumps(dom)),after=after['java'])
        value=dict(picoWorldCurrentDocumentVersion=1,commandId=request['commandId'],runId=c.run,ownerToken=c.owner,
            instance=c.instance,sequence=self.sequence,processId=self.pid,requestedEpochMs=epoch,requestedMonotonicMs=monotonic,
            capturedEpochMs=self.stage.native_epoch_ms(),capturedMonotonicMs=self.stage.native_monotonic_ms(),status='ready',
            source=dict(authorityBefore=before,authorityAfter=after,originalFinish=finish,documents=[dict(finish)],
                domRaw=json.dumps(transaction),dom=dom))
        raw=canonical(value)+b'\n';need(len(raw)<=65536)
        self.file.write(value,self.packet)
        self.packet=value;self.request=dict(request)
        self.guard();self.stage.model_published(self)
        return None

    def original(self):
        self.stage.model_before_get(self);self.guard();need(self.file.file is not None)
        raw,stamp=self.file.read(self.file.file,self.file.path)
        need(raw==self.file.raw and stamp==self.file.stamp and 0<len(raw)<=65536)
        # This is an actual newly read original, not a cached current verdict.
        return raw.decode('utf-8',errors='strict')

    def close_host(self):return self.file.close_host()
