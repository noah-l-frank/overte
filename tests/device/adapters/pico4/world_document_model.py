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
import os,re,time
from adapters.host_process_identity import host_identity
from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.pico4.lifecycle_process_file import LifecycleProcessFile
from adapters.pico4.world_current_document import command
from adapters.pico4.browser_source import fixture
from adapters.pico4.assets_raw_archive import quoted_bytes
from adapters.script_journey.history import canonical
from adapters.pico4.lifecycle_namespace_bill import canonical_size


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
        self.sequence=0;self.packet=self.request=self.document_packet=None
        self.focused=stage.host_selection.operation in ('focus','ime') and not stage.host_selection.controller_focus;self.dom_sequence=0;self.focus_delay_done=False
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
        need(type(self.focus_delay_done) is bool and type(self.focused) is bool and (self.stage.host_selection.controller_focus or self.focused==(self.stage.host_selection.operation in ('focus','ime')))
            and type(self.dom_sequence) is int and 0<=self.dom_sequence<=9007199254740991
            and type(self.sequence) is int and 0<=self.sequence<=9007199254740991
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
        if self.stage.node is not None:
            dom=self.stage.node.snapshot(request['commandId'])
            need(type(dom) is dict and dom['requestId']==request['commandId']
                and canonical_size(dom,8192)<=8192)
            # This fixed Host worker emits only31 DOM key/value nodes; do not
            # silently admit arbitrary external JSON into model44B metadata.
            need(set(dom)=={'webDOMVersion','requestId','instance','sequence','capturedEpochMs','document','editor','attempts','echoes'}
                and type(dom['editor']) is dict and set(dom['editor'])=={'text','focused'}
                and type(dom['document']) is dict and set(dom['document'])=={'runId','href','responseId','readyState'}
                and dom['attempts']==[] and dom['echoes']==[])
            if self.stage.host_selection.controller_focus:
                need(dom['document']==dict(runId=c.run,href=c.url,responseId=c.response,readyState='complete')
                    and type(dom['editor']['text']) is str and type(dom['editor']['focused']) is bool
                    and sum(2 if ord(ch)>65535 else 1 for ch in dom['editor']['text'])<=512)

        else:dom=dict(webDOMVersion=1,requestId=request['commandId'],instance=c.dom,sequence=self.sequence,
            capturedEpochMs=self.stage.native_epoch_ms(),document=dict(runId=c.run,href=c.url,responseId=c.response,readyState='complete'),
            editor=dict(text='',focused=self.focused),attempts=[],echoes=[])
        if self.stage.host_selection.controller_focus:
            need(type(dom['editor']['focused']) is bool);self.focused=dom['editor']['focused']
        after=self.snapshot()
        finish=dict(handle='1',creation=self.creation,grant=self.original_grant,page=self.page,url=c.url,finishedEpochMs=self.finished_epoch)
        import json
        transaction=document_transaction(before,dom,after)
        value=dict(picoWorldCurrentDocumentVersion=1,commandId=request['commandId'],runId=c.run,ownerToken=c.owner,
            instance=c.instance,sequence=self.sequence,processId=self.pid,requestedEpochMs=epoch,requestedMonotonicMs=monotonic,
            capturedEpochMs=self.stage.native_epoch_ms(),capturedMonotonicMs=self.stage.native_monotonic_ms(),status='ready',
            source=document_source(before,after,finish,dom,transaction))
        raw=canonical(value)+b'\n';need(len(raw)<=65536)
        if self.stage.host_selection.controller_focus:need(len(raw)<=self.document_wire_bound())
        self.file.write(value,self.packet)
        self.packet=value;self.document_packet=value;self.dom_sequence=dom['sequence'];self.request=dict(request)
        self.guard();self.stage.model_published(self)
        return None

    def send_focus(self,request):
        # Readonly model query, not a Qt focus event/IME or claimed native fact.
        from adapters.pico4.world_current_input import command as focus_command
        self.stage.model_before_produce(self,request)
        focus_command(request);self.guard();c=self.context;doc=self.document_packet
        need(request['operation'] in (('measure-current-ray','observe-current-focus') if self.stage.host_selection.controller_focus else ('observe-current-focus',)) and request['control']=='text'
            and doc is not None and request['documentNonce']==doc['commandId']
            and all(request[k]==doc[k] for k in ('runId','ownerToken'))
            and request['fixtureUrl']==c.fixture_url and self.sequence<9007199254740991)
        epoch=self.stage.native_epoch_ms();monotonic=self.stage.native_monotonic_ms()
        self.sequence+=1;self.dom_sequence+=1
        a=self.snapshot()
        geometry=dict(webGeometryVersion=1,requestId=request['commandId'],instance=c.dom,sequence=self.dom_sequence,
            capturedEpochMs=self.stage.native_epoch_ms(),document=dict(doc['source']['dom']['document']),control='text',
            editor=dict(focused=self.focused,text='',cursor=0,anchor=0),
            viewport=dict(width=640,height=480,scale=1,offsetLeft=0,offsetTop=0),
            rect=dict(x=80,y=60,width=160,height=80),center=dict(x=160,y=100),hit=True,enabled=True,connected=True)
        b=self.snapshot()
        import json
        transaction=dict(before=a['java'],geometryRaw=json.dumps(json.dumps(geometry)),after=b['java'])
        value=dict(picoWorldCurrentInputVersion=1,commandId=request['commandId'],runId=c.run,ownerToken=c.owner,
            documentNonce=request['documentNonce'],instance=c.item,sequence=self.sequence,processId=self.pid,
            requestedEpochMs=epoch,requestedMonotonicMs=monotonic,capturedEpochMs=self.stage.native_epoch_ms(),
            capturedMonotonicMs=self.stage.native_monotonic_ms(),status='ready',source=dict(
                documentReference={k:doc[k] for k in ('commandId','instance','sequence')},
                originalFinish=dict(doc['source']['originalFinish']),authorityBefore=a,authorityAfter=b,
                focusRaw=json.dumps(transaction),nativeEditor=dict(text='',cursor=0,anchor=0,absoluteCursor=0,
                    kind='text',sensitive=False,focused=self.focused,enabled=True)))
        if request['operation']=='measure-current-ray':
            import math
            from adapters.pico4.world_browser_ray import rotate
            factor=39.3701*40;dimensions=[1.8,2.2,.01];size=[int(v*factor) for v in dimensions[:2]]
            quad=[[0,0],[size[0],0],size,[0,size[1]]];uv=[160/640,100/480]
            point=[uv[0]*size[0],uv[1]*size[1]]
            offset=[point[0]/factor-.9,1.1-point[1]/factor,0]
            ray=dict(worldWebRayVersion=1,capturedEpochMs=self.stage.native_epoch_ms(),sourceIdentity='web-entity:'+c.entity,
                entityId=c.entity,entityName='OVERTE_PARITY_WEB_REFERENCE',entityType='Web',hostType='local',
                sourceUrl=c.url,visible=True,ignorePickIntersection=False,position=[0,1.4,-2.5],rotation=[0,0,0,1],
                dimensions=dimensions,registrationPoint=[.5,.5,.5],dpi=40,scenePoint=point,itemQuad=quad,surfaceSize=size,
                worldPoint=[offset[0],1.4+offset[1],-2.5],sensorToWorld=[1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1],headPosition=[0,1.6,0])
            if self.stage.host_selection.controller_foreign_scene:
                ray['entityId']='00000000-0000-0000-0000-000000000001'
            value['source']['geometryRaw']=value['source'].pop('focusRaw')
            del value['source']['nativeEditor'];value['source']['worldRay']=ray
        raw=canonical(value)+b'\n';need(len(raw)<=65536)
        self.file.write(value,self.packet);self.packet=value;self.request=dict(request)
        self.guard();self.stage.model_published(self);return None

    def original(self):
        self.stage.model_before_get(self);self.guard();need(self.file.file is not None)
        if self.request['operation']=='observe-current-focus' and not self.focus_delay_done:
            self.focus_delay_done=True
            time.sleep(self.stage.host_selection.focus_get_delay)
        raw,stamp=self.file.read(self.file.file,self.file.path)
        need(raw==self.file.raw and stamp==self.file.stamp and 0<len(raw)<=65536)
        # This is an actual newly read original, not a cached current verdict.
        return raw.decode('utf-8',errors='strict')

    def close_host(self):return self.file.close_host()

    def document_wire_bound(self):
        # Closed Node document: exact fixed keys, no echoes/attempts, one
        # initial-empty+once-IME editor <=512 UTF16 units. This is allocation
        # planning, not expected text/current authority or a Native wire cap.
        return document_format_bound(self.context)


def document_transaction(before,dom,after):
    import json
    return dict(before=before['java'],domRaw=json.dumps(json.dumps(dom)),after=after['java'])


def document_source(before,after,finish,dom,transaction):
    import json
    return dict(authorityBefore=before,authorityAfter=after,originalFinish=finish,documents=[dict(finish)],
        domRaw=json.dumps(transaction),dom=dom)


def document_format_bound(c):
    c.validate()
    q=max(quoted_bytes(getattr(c,k)) for k in ('run','owner','instance','item','dom','response','entity','ticket'))
    # Triple quoted DOM plus direct DOM: BMP/astral <=19 per UTF16 unit;
    # backslash/quote <=18.20 includes both actual representations.
    return min(65536,16384+20*512+24*quoted_bytes(c.url)+32*q)
