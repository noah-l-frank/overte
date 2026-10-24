"""Composed ordinary host journey; native/Qt/WK/renderer remain explicit models.

The exact staged VM and original IOSWebView/reference/observer JS stay alive in
Node. Native birth/return/weak ledgers describe the actual modeled SDK operands
and host weak objects. No expected scenario result fills the observed state.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import time
from types import SimpleNamespace
from urllib.parse import urlsplit
import uuid
import weakref
from adapters.normal_feature_state import PrivateFeatureState
from feature_journeys.browser_fixture import BrowserResources
from ios.adapters.world_web_sources import WorldWebSources
from ios.adapters.world_web_source import VERSION as TRANSCRIPT_VERSION
from ios.adapters.world_web_runtime import IOSWorldWebRuntime
from ios.adapters.world_web_background import WorldWebBackground
from ios.adapters.world_web_actions import WorldWebActions
from ios.adapters.world_web_input import WorldWebInput
from ios.adapters.world_web_work import worker as validate_worker
from ios.self_tests.world_web_sources_fixture import SDK
from ios.self_tests.world_web_active_source_fixture import ActiveSDK
from ios.self_tests.world_web_source_fixture import OriginalSources
from ios.self_tests.world_web_scope_fixture import WorldWebDomain
from ios.self_tests.emote_marker_domain_fixture import Domain as BaseDomain
from ios.self_tests.world_web_qt_fixture import QtPointer,QtKeys
from ios.self_tests.test_ios_world_web_scope import WorldWebScopeTests
from ios.self_tests.test_ios_emote_marker_measurements import frames


class EntityItem:pass
class ModeledWebHolder:pass


class LiveDomain(WorldWebDomain):
    def world(self,run):
        if not self.running or self.marker is not None:return super().world(run)
        # An actual modeled null SDK return still leaves a real running Node
        # Script/VM. It creates no Entity, renderer, document or marker facts.
        value=BaseDomain.world(self,run);source=value['source'];script=source['scriptOriginal']['source']
        script['engines']=[deepcopy(self.engine)]
        script['membership'].update(revision=1,managers=[deepcopy(self.worker)])
        source['tree'].update(revisionBefore=2,revisionAfter=2)
        return value
    def paint(self):
        # Model each actual native descriptor as its own immutable birth. WK
        # reconstruction and navigation retain older original contexts.
        from ios.adapters.web_closures import KINDS,resources_for,SOFTWARE_RESOURCES,GPU_RESOURCES
        identity=self.sdk.page_source.identity
        descriptor={key:int(identity[key]) for key in ('handle','creation','grant','page')}
        descriptor.update(surface='world-entity',identitySha256=hashlib.sha256(identity['sourceIdentity'].encode()).hexdigest(),sourceUrl=identity['sourceUrl'])
        if not hasattr(self,'contexts'):self.contexts=[]
        if any(row['descriptor']==descriptor for row in self.contexts):return
        row=dict(id=len(self.contexts)+1,descriptor=descriptor,createdEpochMs=self.epoch(),updatedEpochMs=self.epoch(),
            callbacks={key:dict(created=1,retired=0,pending=1) for key in KINDS},resources={key:dict(created=1,retired=0,pending=1) for key in resources_for(5)})
        self.contexts.append(row)
        if not hasattr(self,'holder_refs'):self.holder_refs={};self.native_holders={};self.cached_holders=[]
        refs={};native={}
        for collection in ('callbacks','resources'):
            for key in row[collection]:
                holder=ModeledWebHolder();refs[(collection,key)]=weakref.ref(holder)
                if collection=='resources' and key in SOFTWARE_RESOURCES|GPU_RESOURCES|{'native-bitmap'}:
                    renderer=getattr(self.sdk,'surface_renderer',None)
                    if renderer is None:self.cached_holders.append(holder)
                    else:
                        root=renderer['surface'].root
                        if not hasattr(root,'painted_holders'):root.painted_holders=[]
                        root.painted_holders.append(holder)
                else:native[(collection,key)]=holder
        self.holder_refs[row['id']]=refs;self.native_holders[row['id']]=native
    def retire_contexts(self,creation):
        for row in getattr(self,'contexts',[]):
            if row['descriptor']['creation']!=creation:continue
            # Ending modeled native dispatch releases only its actual strong
            # holders. Cached paint/image/GPU objects still belong to the real
            # host cache model, and an external queued callback copy stays live.
            self.native_holders[row['id']].clear()
    def web(self,run,url,query=None):
        # Sample the actual modeled resource rows before the original source
        # takes its terminal timestamp. A real CPU clock can tick while copying
        # rows; updating them after the source header would put them in its
        # future. No completed original packet is rewritten.
        for row in getattr(self,'contexts',[]):
            for (group,kind),reference in self.holder_refs[row['id']].items():
                pending=int(reference() is not None);counter=row[group][kind]
                if pending!=counter['pending']:
                    counter.update(pending=pending,retired=counter['created']-pending);row['updatedEpochMs']=self.epoch()
        contexts=deepcopy(getattr(self,'contexts',[]))
        value=super().web(run,url);value['contexts']=contexts
        # Assemble this newly captured producer packet with its actual native
        # query before exposing any bytes; no earlier original is rewritten.
        if query is not None:value['commandId']=query['commandId']
        self.scope.web.last=deepcopy(value);return value
    def start(self):
        sdk=self.sdk;raw=(self.files.root/'script-bundle/main.js').read_text();companion=(self.files.root/'script-bundle/companion.js').read_text()
        self.time+=.005;self.worker=dict(instance=uuid.uuid4().hex,assigned=True,url=self.file_url(),loadGeneration=1,assignedEpochMs=self.epoch())
        self.time+=.005;self.terminal_events=[dict(eventSequence=1,capturedEpochMs=self.epoch(),monotonicMs=round(self.time*1000),kind='thread-bound',threadInstance='a'*32,manager=deepcopy(self.worker),code=None,work=None)]
        self.time+=.005;code=dict(submitted=True,encoding='utf-16le-code-units',codeUnits=len(raw.encode('utf-16le'))//2,sha256=hashlib.sha256(raw.encode('utf-16le')).hexdigest(),submittedEpochMs=self.epoch())
        self.engine=deepcopy(frames()[1]['source']['scriptOriginal']['source']['engines'][0]);self.engine.update(url=self.file_url(),code=code)
        self.engine['required']['instance']=self.worker['instance'];self.engine['required']['modules'][0]['url']=(self.files.root/'script-bundle/companion.js').as_uri()
        actual_id=None if getattr(sdk,'deny_entity_rez',False) else str(uuid.uuid4())
        invoked=sdk.tick();result=sdk.evaluate(dict(op='start',entity=actual_id,script=raw,companion=companion,assignedUrl=self.file_url(),
            caller=dict(callerVersion=1,method='emitScriptEvent',manager=deepcopy(self.worker),code=deepcopy(code)),
            camera=dict(position=dict(x=0,y=1.6,z=7),orientation=dict(x=0,y=0,z=0,w=1))))
        assert len(result['created'])==1 and not result['deleted'];created=result['created'][0];assert created['id']==actual_id
        if actual_id is None:
            self.vm=dict(added=deepcopy(result['created']),deleted=[]);self.running=True
            sdk.call('add-returned',None,invoked,result['epoch']);return
        self.vm=dict(added=deepcopy(result['created']),deleted=[]);properties=created['properties'];stamp=str(created['epoch']*1000)
        self.marker={key:properties[key] for key in ('name','type','userData','sourceUrl','visible','collisionless')}
        self.marker.update(id=created['id'],hostType=created['host'],lastEditedEpochUs=stamp)
        for key in ('position','dimensions'):self.marker[key]=[properties[key][axis] for axis in ('x','y','z')]
        self.marker['rotation']=[properties['rotation'][axis] for axis in ('x','y','z','w')];self.running=True
        sdk.add_entity(created,invoked,result['epoch']);sdk.open_document(self.marker['sourceUrl'],first=True)
        self.paint()
    def stop(self):
        result=self.sdk.evaluate(dict(op='stop'));self.vm['deleted']=[row['id'] for row in result['deleted']]
        if self.marker is None:
            assert self.running and not result['deleted'] and self.sdk.entity_row is None
            assert self.sdk.node_work[-1]['value']['event']=='ending-finally'
            for kind in ('shutdown-drained','thread-finished'):
                self.time+=.005;self.terminal_events.append(dict(eventSequence=len(self.terminal_events)+1,capturedEpochMs=self.epoch(),
                    monotonicMs=round(self.time*1000),kind=kind,threadInstance='a'*32,manager=deepcopy(self.worker),code=deepcopy(self.engine['code']),
                    work=dict(signalCallbacks=0,timerCallbacks=0,evaluating=False,timers=0) if kind=='shutdown-drained' else None))
            self.running=False;return
        self.sdk.remove_entity(result['deleted'][-1]);self.sdk.close_document()
        if self.sdk.surface_renderer is not None:self.sdk.surface_cache.release(self.sdk.surface_renderer)
        super().stop()


class WholeSDK(SDK):
    @property
    def time(self):return self.domain.time
    @time.setter
    def time(self,value):self.domain.time=value
    def __init__(self,domain):
        self.domain=domain;domain.sdk=self;super().__init__();self.base_epoch=20000;self.pid=31;self.run=domain.scope.run;self.binding=deepcopy(domain.scope.binding)
        self.fixture_url=domain.scope.fixture_url;self.origins=dict(primary=self.fixture_url.split('/feature-fixture/')[0],foreign='http://second-controlled.invalid')
        self.ticket=domain.scope.ticket;self.activated_epoch=90000;self.activations=[dict(sequence=1,ticket=self.ticket,activatedEpochMs=90000,stimulus=dict(verb='baseline',inputs={}))];self.foreground=True;self.native=domain.boundary;self.browser=BrowserResources(clock_ms=self.tick);self.browser.open(self.run)
        self.page_source=None;self.page=None;self.trace_events=[];self.ledger_sequence=0;self.document_sequence=0;self.node_native=0;self.node_work=[];self.node_entries={}
        from ios.self_tests.world_web_emission_fixture import EmissionOriginals
        self.emissions=EmissionOriginals(self)
        self.lifecycle=dict(backgrounds=0,activations=1,launches=1);self.history=[];self.entity_events=[];self.entity_calls=[];self.entity_row=None;self.item=None;self.item_weak=None
        self.qt_pointer,self.qt_keys=QtPointer(self),QtKeys(self)
        self.surface_renderer=None
        self.shift=False;self.posted=[];self.releases=0;self.lose=False;self.before_post=None
        self.process=subprocess.Popen(['node',str(Path(__file__).with_name('world_web_page_fixture.js'))],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    def activate(self,verb,inputs):
        self.ticket=uuid.uuid4().hex;self.activated_epoch=self.host_epoch()
        if hasattr(self,'controller'):self.controller.activate(self.ticket,verb,inputs)
        if verb=='restore-resource' and not hasattr(self,'controller'):self.browser.control(self.run,dict(operation='restore-resource'))
        self.activations.append(dict(sequence=len(self.activations)+1,ticket=self.ticket,activatedEpochMs=self.activated_epoch,stimulus=dict(verb=verb,inputs=deepcopy(inputs))))
        return dict(contractVersion=16,runId=self.run,ticket=self.ticket,verb=verb,inputs=deepcopy(inputs),fixtureUrl=self.fixture_url)
    def phase(self,path,**kwargs):
        if hasattr(self,'phase_client'):return self.phase_client.request(path,**kwargs)
        value=super().phase(path,**kwargs)
        if not path.endswith('/browser'):value.update(createdEpochMs=89999,activations=deepcopy(self.activations))
        return value
    def host_epoch(self):return 90000+self.time*1000
    def native_send(self,query):
        self.domain.native_send(query);self.native.sample['lifecycle']=deepcopy(self.lifecycle)
    def close(self):ActiveSDK.close(self)
    def evaluate(self,query):
        query=dict(query,epoch=self.tick(),currentTicket=self.ticket);self.process.stdin.write(json.dumps(query)+'\n');self.process.stdin.flush();value=json.loads(self.process.stdout.readline());assert 'error' not in value,value.get('error')
        self.time=max(self.time,(value['epoch']-self.base_epoch)/1000);self.node_work=deepcopy(value['workEvents'])
        if 'keyProgram' in value:self.key_program=value['keyProgram']
        if self.page_source is not None:
            for ordinal,row in enumerate(value['nativeEvents'][self.node_native:],self.node_native+1):
                detail=deepcopy(row['detail'])
                if row['kind'] in ('signal-return','callback-enter','callback-return'):
                    if row.get('sourceEntry'):
                        actual=self.trace_events[detail['entry']-1];assert actual['kind']=='evaluation-enter'
                        if row['kind']=='callback-enter':assert actual['detail']['codeSha256']==row['executedCodeSha']
                    else:detail['entry']=self.node_entries[detail['entry']]
                if row['kind']=='native-envelope':
                    message=detail.pop('message');detail=dict(envelope=json.dumps(dict(type=6,object='eventBridge',method='emitWebEvent',args=[message])),documentNonce=self.page_source.identity['nonce'],frame=self.page_source.url,mainFrame=True)
                event=self.event(row['kind'],detail,epoch=row['epoch']);self.node_entries[ordinal]=event['sequence']
            self.node_native=len(value['nativeEvents'])
        self.emissions.observe(value,self.trace_events,self.node_entries)
        self.page=value;return value
    def emission_packet(self,command):return self.emissions.read(command)
    def event(self,kind,detail,*,identity=None,epoch=None):
        epoch=self.tick() if epoch is None else epoch;item=self.page_source.identity if identity is None else identity
        row=dict(sequence=len(self.trace_events)+1,eventId=uuid.uuid4().hex,kind=kind,identity=deepcopy(item),detail=deepcopy(detail),clock=dict(epochMs=epoch,monotonicMs=epoch-self.base_epoch))
        self.trace_events.append(row);return deepcopy(row)
    def open_document(self,url,*,first=False,new_view=False):
        parsed=urlsplit(url);origin='primary' if parsed.scheme+'://'+parsed.netloc==self.origins['primary'] else 'foreign';ticket,resource=parsed.path.split('/tickets/')[1].split('/')
        if first:
            if hasattr(self,'surface_cache'):
                self.surface_renderer=self.surface_cache.acquire(self.domain.marker['id'],url)
            source=OriginalSources(resource,origin,clock_ms=self.tick,monotonic_ms=lambda:round(self.time*1000),source_identity='web-entity:'+self.domain.marker['id'],
                run=self.run,ticket=ticket,fixture_url=self.fixture_url,origins=self.origins,browser=self.browser)
            self.page_source=source;self.trace_events=source.events
        else:
            source=self.page_source;assert source is not None
            if new_view:
                source.identity.update(creation=source.identity['creation']+1,page=0,nonce='');self.event('view-created',{})
            source.identity.update(page=source.identity['page']+1,nonce=str(uuid.uuid4()),url=url)
            self.event('document-began',dict(frame=url));self.event('dom-observer-installed',dict(sourceSha256=source.view['observerSha256'],wrapperSha256='a'*64))
            status,_mime,source.body,response=self.browser.resource(self.run,ticket,resource,origin=origin)
            self.event('main-response',dict(url=url,status=status,responseId=response,mimeType='text/html'));finished=self.event('native-finished',{})['clock']['epochMs'];self.event('document-verified',{})
            source.view={key:deepcopy(value) for key,value in source.identity.items() if key!='surface'}|dict(nativeFinished=True,httpErrorStatus=404 if status==404 else 0,
                inlineLease=False,httpStatus=status,responseId=response,finishedEpochMs=finished,observerSha256=source.view['observerSha256'])
            source.url=url
        if first:self.trace_events=source.events
        if not new_view:self.history.append(url)
        _status,_mime,marker_script,_response=self.browser.resource(self.run,ticket,'feature-marker.js',origin=origin)
        self.page=self.evaluate(dict(op='open',bridge=origin=='primary',url=url,html=source.body.decode(),markerScript=marker_script.decode()));self.domain.paint()
    def close_document(self,*,owner=False):
        assert self.page_source is not None;self.event('view-teardown',{})
        if owner:self.event('owner-destroyed',{})
        self.evaluate(dict(op='close'));self.domain.retire_contexts(self.page_source.identity['creation']);self.page=None
    def add_entity(self,created,invoked,returned):
        self.item=EntityItem();self.item_weak=weakref.ref(self.item);birth=uuid.uuid4().hex;epoch=created['epoch'];mono=epoch-self.base_epoch
        self.entity_row=dict(id=created['id'],birth=birth,insertedSequence=1,bornEpochMs=epoch,bornMonotonicMs=mono,removedSequence=0,removedEpochMs=0,removedMonotonicMs=0,destroyed=False,destructionObservedEpochMs=0,destructionObservedMonotonicMs=0)
        self.entity_events.append(dict(sequence=1,kind='inserted',id=created['id'],birth=birth,epochMs=epoch,monotonicMs=mono));self.call('add-returned',created['id'],invoked,returned)
    def call(self,kind,entity,invoked,returned):
        self.entity_calls.append(dict(sequence=len(self.entity_calls)+1,eventId=uuid.uuid4().hex,kind=kind,clock=dict(epochMs=returned,monotonicMs=returned-self.base_epoch),
            caller=dict(callerVersion=1,method='addEntity' if kind=='add-returned' else 'deleteEntity',sequence=len(self.entity_calls)+1,invokedEpochMs=invoked,manager=deepcopy(self.domain.worker),code=deepcopy(self.domain.engine['code'])),entityId=entity,localTreeAvailable=True))
    def remove_entity(self,removed):
        epoch=removed['epoch'];self.entity_events.append(dict(sequence=2,kind='removed',id=removed['id'],birth=self.entity_row['birth'],epochMs=epoch,monotonicMs=epoch-self.base_epoch))
        self.entity_row.update(removedSequence=2,removedEpochMs=epoch,removedMonotonicMs=epoch-self.base_epoch);self.item=None;assert self.item_weak() is None
        self.call('delete-returned',removed['id'],epoch,epoch)
    def original(self,name):
        if name=='closures':return json.dumps(self.domain.web(self.run,self.fixture_url,self.queries[name]),separators=(',',':'),ensure_ascii=False)
        if name=='document':
            assert self.page is not None;query=self.queries[name];value=self.evaluate(dict(op='dom-read',requestId=query['commandId']));self.document_sequence+=1;body=deepcopy(value['document']);assert body['requestId']==query['commandId']
            return json.dumps(dict(iosWorldWebDOMNativeVersion=1,commandId=query['commandId'],runId=self.run,surface='world',instance='e'*32,sequence=self.document_sequence,
                processId=self.pid,capturedEpochMs=self.tick(),status='ready',source=dict(nativeView=deepcopy(self.page_source.view),dom=body)),separators=(',',':'),ensure_ascii=False)
        if name=='ledger':
            query=self.queries[name];self.ledger_sequence+=1;before=self.tick()
            return json.dumps(dict(iosWorldWebVersion=TRANSCRIPT_VERSION,commandId=query['commandId'],runId=self.run,fixtureUrl=self.fixture_url,instance='c'*32,sequence=self.ledger_sequence,
                processId=self.pid,clockDomain='native-main-ios-world-web',clockBefore=dict(epochMs=before,monotonicMs=before-self.base_epoch),clockAfter=dict(epochMs=self.tick(),monotonicMs=round(self.time*1000)),complete=True,eventSequence=len(self.trace_events),events=deepcopy(self.trace_events)),separators=(',',':'),ensure_ascii=False)
        if name=='world':self.world=self.domain.world(self.run)
        value=json.loads(super().original(name))
        if name=='keys':value['source']=self.qt_keys.packet_source()
        if name=='pointer':value['source']=self.qt_pointer.packet_source()
        if name=='uikit':
            # The actual Node stop result remains an object after its DOM has
            # retired. It does not retain a focused editor or a native keyboard.
            document=None if self.page is None else self.page['document']
            keyboard=self.foreground and document is not None and any(row['focused'] for row in document['elements'])
            value['observation']['nativeUi'].update(keyboardVisible=keyboard,imeInsetBottom=200 if keyboard else 0)
        if name=='work' and self.domain.worker is not None:
            events=[];calls=[]
            for index,row in enumerate(self.node_work,1):
                original=row['value'];event=dict(sequence=index,event=original['event'],call=original['call'],payload=deepcopy(original['payload']),callerSequence=index,invokedEpochMs=row['epoch'],capturedEpochMs=row['epoch']);events.append(event)
                if original['event']=='loaded':continue
                kind,phase=original['event'].rsplit('-',1)
                if phase=='enter':calls.append(dict(call=original['call'],kind=kind,payload=deepcopy(original['payload']),returned=False))
                elif phase=='return':calls[-1]['returned']=True
                else:calls.pop()
            value['source']=dict(complete=True,eventSequence=len(events),workers=[dict(runId=self.run,nonce=self.domain.scope.state['fileOwnership']['nonce'],manager=deepcopy(self.domain.worker),code=deepcopy(self.domain.engine['code']),calls=calls,events=events,ended=bool(events and events[-1]['event']=='ending-finally'))])
        if name=='geometry':
            source=value['source'];source['tree']=deepcopy(self.world['source']['tree']);source['entities']=[]
            if self.domain.running and self.domain.marker is not None:
                marker=self.domain.marker;row={key:deepcopy(marker[key]) for key in ('id','hostType','sourceUrl','userData','position','rotation','dimensions','visible','lastEditedEpochUs')}
                row.update(parentId='00000000-0000-0000-0000-000000000000',registrationPoint=[.5,.5,.5],dpi=12,inputMode='touch',billboardMode='none',locked=False);source['entities']=[row]
        if name=='entities':
            tree=value['source']['tree'];tree.update(treeInstance=self.world['source']['tree']['treeInstance'],treeBornEpochMs=self.base_epoch-1000,events=deepcopy(self.entity_events),eventSequence=len(self.entity_events))
            if self.entity_row is not None:
                if self.item_weak() is None and not self.entity_row['destroyed']:self.entity_row.update(destroyed=True,destructionObservedEpochMs=tree['observedEpochMs'],destructionObservedMonotonicMs=tree['observedMonotonicMs'])
                tree['entities']=[deepcopy(self.entity_row)]
            value['source']['calls']['events']=deepcopy(self.entity_calls)
        return json.dumps(value,separators=(',',':'),ensure_ascii=False) if name in ('keys','work','geometry') else json.dumps(value)
    def ui(self):return ActiveSDK.ui(self)
    def release(self):self.releases+=1
    def request(self,method,path,body=None):
        if method=='GET' and path=='/window/rect':return dict(x=0,y=0,width=1024,height=768)
        assert method=='POST' and path=='/actions'
        if self.before_post is not None:self.before_post()
        from adapters.operation_transport_guard import check
        check();self.posted.append(deepcopy(body))
        for device in body['actions']:
            if device['type']=='pointer':
                position=None
                for action in device['actions']:
                    if action['type']=='pointerMove':position=(action['x'],action['y'])
                    if action['type'] not in ('pointerDown','pointerUp'):continue
                    import math
                    view=self.world['source']['view'];row=self.domain.marker;distance=view['position'][2]-row['position'][2]
                    nx=(position[0]-512)/512;ny=1-(position[1]-20)/728*2
                    x=(nx*distance*math.tan(math.radians(view['fieldOfViewDegrees'])/2)*view['aspectRatio']/row['dimensions'][0]+.5)*850
                    y=(.5-ny*distance*math.tan(math.radians(view['fieldOfViewDegrees'])/2)/row['dimensions'][1])*661
                    def handler():
                        result=self.evaluate(dict(op='pointer',args=['press' if action['type']=='pointerDown' else 'release',x,y,0]));self.navigate(result['navigations']);return True
                    self.qt_pointer.touch('touch-begin' if action['type']=='pointerDown' else 'touch-end',position=position,handler=handler)
            else:
                scheduled=[]
                for action in device['actions']:
                    key=action['value'];down=action['type']=='keyDown'
                    if key=='\ue008':self.shift=down
                    qt={'\ue010':16777233,'\ue011':16777232,'\ue003':16777219,'\ue008':16777248}.get(key,ord(key) if len(key)==1 else 0)
                    text='' if key in ('\ue010','\ue011','\ue003','\ue008') else key
                    def handler():
                        if down:
                            args=[text,qt,self.shift];entry=self.event('key-enter',dict(text=text,key=qt,modifiers=33554432 if self.shift else 0))
                            code=self.key_program.replace('%1',json.dumps(args,ensure_ascii=False,separators=(',',':')))
                            evaluation=self.event('evaluation-enter',dict(codeSha256=hashlib.sha256(code.encode()).hexdigest()))
                            scheduled.append(dict(args=args,entry=evaluation['sequence']));self.event('signal-return',dict(entry=entry['sequence']))
                        return down
                    self.qt_keys.notify(down,qt,text,33554432 if self.shift else 0,handler)
                self.evaluate(dict(op='key-batch',items=scheduled))
        return None
    def navigate(self,requests):
        for request in requests:
            if request['kind']=='navigate':self.open_document(request['url'])
            elif request['kind']=='back':
                assert len(self.history)>1;self.history.pop();url=self.history.pop();self.open_document(url)
            elif request['kind']=='reload':
                url=self.history.pop();self.open_document(url)


class ComposedWorldWeb:
    def __init__(self,*,wall_clock=False,use_snapshot=True,use_whole_snapshot=False,run=None,fixture_url=None,ticket=None,configure=None):
        self.fixture=WorldWebScopeTests();self.fixture.setUp();self.scope=self.fixture.scope
        if run is not None:
            from ios.adapters.world_web_originals import IOSWorldWebOriginals
            self.scope.run=run;self.scope.fixture_url=fixture_url;self.scope.ticket=ticket
            self.scope.originals=IOSWorldWebOriginals(self.scope.root,self.scope.binding,run,'primary',self.scope.guard,self.scope.storage_intent,kind='inputs')
        self.domain=LiveDomain(self.scope);self.sdk=WholeSDK(self.domain)
        if wall_clock:
            # Explicit native/SDK model clocks now include every real host CPU
            # interval. Existing logical sleeps/ticks remain conservative too.
            # No original is retimed and no native execution is claimed.
            current=self.domain.time
            class CpuClockDomain(LiveDomain):
                @property
                def time(self):return self._wall_offset+time.perf_counter()-self._wall_started
                @time.setter
                def time(self,value):self._wall_offset=value-(time.perf_counter()-self._wall_started)
            self.domain._wall_started=time.perf_counter();self.domain._wall_offset=current;self.domain.__class__=CpuClockDomain
        self.sdk.use_snapshot=use_snapshot;self.sdk.use_whole_snapshot=use_whole_snapshot
        if configure is not None:configure(self)
        self.domain.world_template['source']['view'].update(mode='first person look at',position=[0,1.6,7],rotation=[0,0,0,1],aspectRatio=1024/728)
        self.source=self.sdk.owner(PrivateFeatureState(self.scope.root/'ios-world-web-primary-sources.json'),self.scope.lock)
    def actions(self):
        sdk,scope=self.sdk,self.scope
        base=SimpleNamespace(_candidate_guard=lambda:None,_operation='feature.world-web.act',state_path=lambda _selector:scope.root/'session.json')
        own_scope={key:value for key,value in sdk.binding.items() if key!='processIdentity'}
        gate=SimpleNamespace(continuity=lambda **_kwargs:dict(pid=sdk.pid,foreground=sdk.foreground))
        base._binding=lambda *_args:gate;base._scope=lambda *_args:deepcopy(own_scope);base.query_app_state=lambda *_args:4 if sdk.foreground else 3
        def invoke(_selector,operation,values):
            assert base._operation is None and values=={}
            if operation=='lifecycle.background':sdk.foreground=False;sdk.lifecycle['backgrounds']+=1;sdk.close_document()
            else:
                assert operation=='app.launch';sdk.foreground=True;sdk.lifecycle['activations']+=1
                sdk.history=[];sdk.open_document(sdk.domain.marker['sourceUrl'],new_view=True)
            return {'backgrounded':True} if operation=='lifecycle.background' else {'launched':True}
        base.invoke=invoke;runtime=IOSWorldWebRuntime(base)
        runtime._existing=lambda _selector:(None,sdk.binding['sessionId'],{},dict(),deepcopy(own_scope))
        background=WorldWebBackground(runtime,'owned',self.source,PrivateFeatureState(scope.root/'ios-world-web-background.json'),sleep=sdk.sleep)
        inputs=WorldWebInput(PrivateFeatureState(scope.root/'ios-world-web-inputs.json'),self.source,sdk.ui(),sdk.domain.marker['id'] if sdk.domain.marker else None,lambda:True,epoch_ms=sdk.host_epoch,monotonic=lambda:sdk.time)
        return WorldWebActions(PrivateFeatureState(scope.root/'ios-world-web-actions.json'),self.source,inputs,scope,background,sdk.origins,lambda:True)
    def close(self):
        self.sdk.close();self.fixture.doCleanups()
