"""Synthetic browser product producers reused from frozen Phone5527.

Only target/DOM/HTTP fixture behavior is reused. All effects here are explicit
host seams; no actual Qt, browser, input, HMD, GPU or VM execution is claimed.
Pico protocols and original transaction/owner classes are exercised separately.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
# Reused sources:5527d540e99cc6dba4204a5e904a854e6e1cd2b4
# android/phone/tests/device/test_world_web_feature.py (pure Target/Clock/Manager)
# android/phone/tests/device/test_tablet_web_feature.py (pure Target/Manager)
from contextlib import nullcontext
from copy import deepcopy
import base64
import hashlib
import json
from pathlib import Path
import re
import secrets
import time
from urllib.error import HTTPError
from urllib.request import urlopen
from urllib.parse import urlsplit
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.pico4.browser_source import command,identity
from adapters.pico4.tablet_browser_source import PicoTabletBrowserIO
from adapters.native_web_runtime import NativeWebRuntime
from adapters.script_journey.lock import ScriptSourceLock
from adapters.pico4.browser_vm import PicoBrowserVm,reviewed
from self_tests.test_pico_browser_vm import Boundary as VmBoundary
from self_tests.test_native_script_observation import code_source
from self_tests.test_native_script_membership import membership_source,manager
DEVICE=Path(__file__).resolve().parents[1]

class Clock:
    def __init__(self):self.value=0.;self.base=int(time.time()*1000)
    def now(self):return self.value
    def epoch(self):return self.base+round(self.value*1000)
    def sleep(self,seconds):self.value+=seconds
    def tick(self):self.value+=.001;return self.epoch()


class OriginalBrowserTarget:
    def __init__(self,clock,client,foreign,path):
        self.clock,self.client,self.foreign,self.path=clock,client,foreign,Path(path)
        self.run=client.run;self.root=client.url+'/runs/'+self.run+'/'
        self.binding=dict(sourceRevision='a'*40,artifactSha256='b'*64,processIdentity='31:456',sessionId='session',generation=1,targetFingerprint='c'*64)
        self.owner=None;self.current=None;self.script=None;self.source=None;self.page=0;self.creation=1
        self.documents=[];self.requests=[];self.replies=[];self.dom_history={};self.history=[];self.known=[]
        self.lifecycle=dict(backgrounds=0,activations=1,launches=1);self.foreground=True;self.retired=False
        self.sequence=0;self.dom_sequence=0;self.native_sequence=0;self.dom_native_sequence=0
        self.request=None;self.fail=None;self.inputs=[];self.backgrounds=0
        self.instance=secrets.token_hex(16);self.dom_native_instance=secrets.token_hex(16);self.runtime_instance=secrets.token_hex(16)
        self.raw=None;self.input_count=0;self.status_mutation=None

    def state_path(self,_selector):return self.path/'session.json'
    def existing_input_session(self,_selector):return nullcontext()
    def existing_session(self,_selector):return self,'session',{'generation':1}
    def world_web_manager_store(self,_selector):return PrivateFeatureState(self.path/'pico-world-web-manager.json')
    def _world_web_clock(self,_selector):return self.clock.epoch()
    def normal_feature_runtime(self,_selector,**_kwargs):
        def observe(_after):return dict(scripts=[] if self.script is None else [dict(url=self.script,path=self.script)],sampleEpochMs=self.clock.tick()),self.clock.epoch()
        return None,observe,deepcopy(self.binding),lambda:self.foreground,None
    def _native_feature_observer(self,_selector,**_kwargs):
        target=self
        class Source:
            def read(self,_after):return dict(instance=target.instance,capturedEpochMs=target.clock.tick(),lifecycle=deepcopy(target.lifecycle))
        return Source()
    def _graphics_lifecycle_status(self,_selector,binding):return dict(foreground=self.foreground,binding=deepcopy(binding))
    def invoke(self,_selector,operation,_values):
        if operation=='lifecycle.background':self.foreground=False;self.lifecycle['backgrounds']+=1;self.backgrounds+=1
        elif operation=='app.launch':
            self.foreground=True;self.lifecycle['activations']+=1
            if self.fail!='old-resume':self.creation+=1;self.load(self.source,history=False)
        else:raise AssertionError(operation)
        return {'performed':True}

    def send(self,request):
        command(request);self.request=deepcopy(request);self.clock.tick();op=request['operation']
        if self.owner is None:
            if op!='reserve':raise NativeUIError('No original lease')
            self.owner=request['ownerToken']
        if self.owner!=request['ownerToken']:raise NativeUIError('Foreign original lease')
        self.sequence+=1
        if op=='reserve':source={'reserved':True}
        elif op=='retire':
            if self.current is not None:raise NativeUIError('Original view still exists')
            self.retired=True;self.documents=[];self.requests=[];self.replies=[];self.dom_history={};self.inputs=[];source={'retired':True}
        elif op=='input':
            self.input_count+=1;self.input_attempt(request)
            if self.fail=='lost-input':raise NativeUIError('Lost native return')
            self.input(request);source={'delivered':True}
        else:
            current=self.dom_packet(request['commandId']) if self.current else {}
            if current:self.dom_history[identity(current['source']['nativeView'])]=deepcopy(current)
            source=dict(retired=self.retired,documents=deepcopy(self.documents),requests=deepcopy(self.requests),replies=deepcopy(self.replies),inputs=deepcopy(self.inputs),domHistory=deepcopy(self.dom_history),current=current)
        value=dict(picoBrowserVersion=2,commandId=request['commandId'],runId=self.run,ownerToken=self.owner,
            instance=self.instance,sequence=self.sequence,processId=31,capturedEpochMs=self.clock.tick(),status='ready',source=source)
        if self.status_mutation:self.status_mutation(value)
        self.raw=json.dumps(value)

    def fetch(self,url):
        try:response=urlopen(url,timeout=2)
        except HTTPError as error:response=error
        with response:return response.status,response.read(),response.headers['X-Overte-Fixture-Response']
    def load(self,url,*,history=True):
        if self.current and history:self.history.append(self.current['url'])
        status,raw,response=self.fetch(url);self.page+=1
        self.current=dict(url=url,response=response,text='',focused=False,attempts=[],echoes=[],instance=secrets.token_hex(16),sequence=0,status=status)
        row=dict(handle='42',creation=self.creation,grant=self.creation,page=self.page,url=url,finishedEpochMs=self.clock.tick())
        self.documents.append(row)
        if not self.known:self.known=[dict(handle='42',firstObservedEpochMs=self.clock.epoch(),sourceSha256=hashlib.sha256(self.source.encode()).hexdigest())]
        self.assert_consumption=raw
    def dom_packet(self,request):
        self.dom_native_sequence+=1;current=self.current;current['sequence']+=1;epoch=self.clock.tick()
        dom=dict(webDOMVersion=1,requestId=request,instance=current['instance'],sequence=current['sequence'],capturedEpochMs=epoch,
            document=dict(runId=self.run,href=current['url'],responseId=current['response'],readyState='complete'),
            editor=dict(text=current['text'],focused=current['focused']),attempts=deepcopy(current['attempts']),echoes=deepcopy(current['echoes']))
        view=dict(handle='42',creation=self.creation,grant=self.creation,page=self.page,url=current['url'],nativeFinished=True,
            httpErrorStatus=404 if current['status']==404 else 0,inlineLease=False,sourceUrl=self.source,sourceIdentity='original-surface')
        return dict(webNativeVersion=1,commandId=request,runId=self.run,surface='world',instance=self.dom_native_instance,
            sequence=self.dom_native_sequence,processId=31,capturedEpochMs=self.clock.tick(),status='ready',source=dict(nativeView=view,dom=dom))
    def input(self,request):
        current=self.current;control=request['control']
        if self.fail=='ignored-input':return
        if control in ('text','foreign'):
            if control=='text':current.update(text=request['text'],focused=True)
            else:self.foreign_editor=request['text']
        elif control=='bridge':
            epoch=self.clock.tick();ordinal=len(current['attempts'])+1
            current['attempts'].append(dict(ordinal=ordinal,capturedEpochMs=epoch,eventTimeMs=self.clock.now()*1000))
            primary=urlsplit(current['url']).netloc==urlsplit(self.root).netloc
            if primary or self.fail=='foreign-accepted':
                seq=len(current['echoes'])+1;packet=dict(contract='overte-web-parity-v1',action='echo',sequence=seq)
                original={k:self.documents[-1][k] for k in ('handle','creation','grant','page','url')}
                self.requests.append(dict(original,message=json.dumps(packet),capturedEpochMs=self.clock.tick()))
                reply={**packet,'surface':'world'};self.replies.append(dict(original,message=json.dumps(reply),capturedEpochMs=self.clock.tick()))
                if self.fail!='no-page-receive':current['echoes'].append(dict(sequence=seq,surface='world',message=json.dumps(reply),receivedEpochMs=self.clock.tick(),observedEpochMs=self.clock.tick()))
        elif control in ('reference','second','recovery'):
            self.load(current['url'].rsplit('/',1)[0]+'/'+{'reference':'reference.html','second':'page-b.html','recovery':'recovery.html'}[control])
        elif control=='back':self.load(self.history.pop(),history=False)
        elif control=='reload':self.load(current['url'],history=False)
        elif control=='navigate':self.load(self.foreign_editor)
        else:raise AssertionError(control)



class OriginalManager:
    def __init__(self,target):
        self.target=target;self.store=target.world_web_manager_store('target');self.previous=self.store.read()
        self.state=deepcopy(self.previous) if self.previous else dict(loadAttempted=False,tabletOwned=False,source=None)
    def save(self):self.store.write(self.state,self.previous);self.previous=deepcopy(self.state)
    def open(self):self.state['tabletOwned']=True;self.save()
    def load_source(self,url):
        self.state.update(loadAttempted=True,source=url);self.save();self.target.script=url
        self.target.source=url.rsplit('/',1)[0]+'/index.html';self.target.load(self.target.source)
    def wait_rows(self,predicate):
        if not predicate([dict(url=self.target.script,path=self.target.script)]):raise NativeUIError('No actual script')
    def close_tablet(self):self.state['tabletOwned']=False;self.save()
    def stop_source(self,url):
        if self.target.fail=='cleanup-view-left':return
        self.target.script=None;self.target.current=None;self.state['loadAttempted']=False;self.save()
    def close(self):
        if self.state['loadAttempted']:raise NativeUIError('Original script remains')
        self.store.discard(self.previous)


class OriginalTabletTarget(OriginalBrowserTarget):
    def __init__(self,*args):
        super().__init__(*args);self.deferred=dict(armed=False,pending=False,held=None,deliveries=[])
        self.tablet_actions=[];self.inline_live=False;self.inline_data=None
    def tablet_web_manager_store(self,_selector):return PrivateFeatureState(self.path/'pico-tablet-web-manager.json')
    def _tablet_web_entry(self,_selector,label,*,initial):
        self.tablet_actions.append(label);self.inline_live=False
        if self.fail=='ignored-entry':return
        self.creation+=1
        if label=='WEB TEST':self.load(self.source)
        else:
            with urlopen(self.root+'current',timeout=2) as response:phase=json.load(response)
            url=self.root+'tickets/'+phase['ticket']+'/inline-input.json'
            _status,raw,_response=self.fetch(url);data=json.loads(raw)['dataUrl'];body=base64.b64decode(data.split(',',1)[1],validate=True)
            token=secrets.token_hex(16);transport='http://'+token+'.overte-inline.invalid/index.html'
            self.inline_data=data;self.inline_live=True;self.page+=1
            self.current=dict(url=transport,response=None,text='',focused=False,attempts=[],echoes=[],instance=secrets.token_hex(16),sequence=0,status=0,
                title=re.search(b'<title>([^<]+)</title>',body)[1].decode(),body=body,
                inline=dict(token=token,revision=1,transportUrl=transport,sourceSha256=hashlib.sha256(data.encode()).hexdigest(),
                    bodySha256=hashlib.sha256(body).hexdigest(),bytes=len(body),charset='utf-8',scriptUrl=self.source.rsplit('/',1)[0]+'/injected.js',current=True))
            self.documents.append(dict(handle='42',creation=self.creation,grant=self.creation,page=self.page,url=transport,finishedEpochMs=self.clock.tick()))
    def _tablet_web_close(self,_selector):
        self.tablet_actions.append('CLOSE');self.inline_live=False
        if self.fail!='cleanup-view-left':self.current=None
    def load(self,url,**kwargs):
        super().load(url,**kwargs);self.current['title']=re.search(b'<title>([^<]+)</title>',self.assert_consumption)[1].decode()
    def dom_packet(self,request):
        value=super().dom_packet(request);value['surface']='tablet';value['source']['dom']['document']['title']=self.current['title']
        if 'inline' in self.current:
            value['source']['nativeView'].update(sourceUrl=self.inline_data,inlineLease=self.inline_live,sourceIdentity='tablet:original-owner')
            value['source']['inline']=deepcopy(self.current['inline']);value['source']['inline']['current']=self.inline_live
        return value
    def input(self,request):
        if request['control']!='bridge':return super().input(request)
        current=self.current
        if self.fail=='ignored-input':return
        ordinal=len(current['attempts'])+1;current['attempts'].append(dict(ordinal=ordinal,capturedEpochMs=self.clock.tick(),eventTimeMs=self.clock.now()*1000))
        packet=dict(contract='overte-web-parity-v1',action='echo',sequence=len(current['echoes'])+1)
        original={key:self.documents[-1][key] for key in ('handle','creation','grant','page','url')}
        if self.deferred['armed'] and 'inline' in current:
            lease=current['inline'];self.deferred.update(armed=False,pending=True,held=dict(original,token=lease['token'],revision=lease['revision'],
                bodySha256=lease['bodySha256'],sourceSha256=lease['sourceSha256'],payloadSha256=hashlib.sha256(json.dumps(packet).encode()).hexdigest(),capturedEpochMs=self.clock.tick(),origin=urlsplit(current['url']).scheme+'://'+urlsplit(current['url']).netloc,mainFrame=True,payloadBytes=len(json.dumps(packet).encode())))
            return
        primary=urlsplit(current['url']).netloc==urlsplit(self.root).netloc
        if primary or self.inline_live or self.fail=='foreign-accepted':
            self.requests.append(dict(original,message=json.dumps(packet),capturedEpochMs=self.clock.tick()))
            reply=packet|dict(surface='tablet');self.replies.append(dict(original,message=json.dumps(reply),capturedEpochMs=self.clock.tick()))
            if self.fail!='no-page-receive':current['echoes'].append(dict(sequence=packet['sequence'],surface='tablet',message=json.dumps(reply),receivedEpochMs=self.clock.tick(),observedEpochMs=self.clock.tick()))
    def send(self,request):
        command(request);self.request=deepcopy(request);self.clock.tick();op=request['operation']
        if self.owner is None:
            if op!='reserve':raise NativeUIError('No original lease')
            self.owner=request['ownerToken']
        if self.owner!=request['ownerToken']:raise NativeUIError('Foreign original lease')
        self.sequence+=1
        if op=='reserve':source={'reserved':True}
        elif op=='arm-held':self.deferred['armed']=True;source={'armed':True}
        elif op=='cancel-held':self.deferred['armed']=False;source={'cancelled':True}
        elif op=='deliver-held':
            if not self.deferred['pending']:raise NativeUIError('Original callback absent')
            delivery=self.deferred['held']|dict(deliveredEpochMs=self.clock.tick(),leaseCurrent=self.inline_live,ownerAlive=True,accepted=self.fail=='retired-accepted')
            self.deferred['deliveries'].append(delivery);self.deferred['pending']=False;source={'delivered':True}
        elif op=='retire':
            if self.current or self.deferred['pending'] or self.deferred['armed']:raise NativeUIError('Original browser/callback remains')
            self.retired=True;self.documents=[];self.requests=[];self.replies=[];self.dom_history={};self.inputs=[]
            self.deferred=dict(armed=False,pending=False,held=None,deliveries=[]);source={'retired':True}
        elif op=='input':
            self.input_count+=1;self.input_attempt(request)
            if self.fail=='lost-input':raise NativeUIError('Lost native return')
            self.input(request);source={'delivered':True}
        else:
            current=self.dom_packet(request['commandId']) if self.current else {}
            if current:self.dom_history[identity(current['source']['nativeView'])]=deepcopy(current)
            source=dict(retired=self.retired,documents=deepcopy(self.documents),requests=deepcopy(self.requests),replies=deepcopy(self.replies),inputs=deepcopy(self.inputs),domHistory=deepcopy(self.dom_history),current=current,deferred=deepcopy(self.deferred))
        value=dict(picoBrowserVersion=2,commandId=request['commandId'],runId=self.run,ownerToken=self.owner,
            instance=self.instance,sequence=self.sequence,processId=31,capturedEpochMs=self.clock.tick(),status='ready',source=source)
        if self.status_mutation:self.status_mutation(value)
        self.raw=json.dumps(value)


class OriginalTabletManager(OriginalManager):
    def __init__(self,target):
        super().__init__(target);self.store=target.tablet_web_manager_store('target');self.previous=self.store.read()
        self.state=deepcopy(self.previous) if self.previous else dict(loadAttempted=False,tabletOwned=False,source=None)
    def load_source(self,url):
        _status,raw,_response=self.target.fetch(url)
        if raw!=(DEVICE/'fixture/parity/tablet-feature-client.js').read_bytes():raise NativeUIError('Changed ordinary fixture application')
        self.state.update(loadAttempted=True,source=url);self.save();self.target.script=url;self.target.source=url.rsplit('/',1)[0]+'/index.html'


class PicoTarget(OriginalTabletTarget):
    """Pico-owned host seams; no scene or state is read from expected scenarios."""
    scene_url='http://controlled.invalid/scene.json'
    def __init__(self,*args):
        super().__init__(*args);self.lock=ScriptSourceLock(self.path/'script-sources.lock')
        self.vm=VmBoundary(self.path);self.vm_epoch=None;self.geometry_sequence=0;self.scroll=0
        self.runtime_sequence=0;self.runtime_raw=None;self.renderer_rows={};self.inputs=[];self.command_log=[]
        original=self.vm.objects.send
        def objects(request):
            self.vm.objects.epoch=self.clock.epoch();self.vm.objects.host=self.clock.now();return original(request)
        self.vm.objects.send=objects

    def _lock(self,target):return self.lock
    def input_attempt(self,request):
        issued=self.clock.tick();geometry=self.geometry_raw(request)
        pointer=wheel=ime=None;focus=None;native=None
        if request['control'] in ('scroll-up','scroll-down'):wheel=self.clock.tick()
        else:
            pointer=self.clock.tick()
            if request['control'] in ('text','foreign'):
                self.current['focused']=True;focus=self.geometry_raw(request,focused=True)
                text=self.current['text'] if request['control']=='text' else getattr(self,'foreign_editor','')
                length=len(text.encode('utf-16le'))//2
                native=dict(text=text,cursor=length,anchor=length,absoluteCursor=length,kind='text' if request['control']=='text' else 'url',
                    sensitive=False,focused=True,enabled=True);ime=self.clock.tick()
        self.inputs.append(dict(command=deepcopy(request),issuedEpochMs=issued,geometryRaw=geometry,focusRaw=focus,
            pointerEpochMs=pointer,wheelEpochMs=wheel,imeEpochMs=ime,nativeBeforeIME=native,
            completion=dict(status='ready',capturedEpochMs=self.clock.tick())))

    def geometry_raw(self,request,*,focused=False):
        self.geometry_sequence+=1;control=request['control'];y=300 if control.startswith('scroll-') else 700-self.scroll
        text=self.current['text'] if control=='text' else getattr(self,'foreign_editor','')
        editing=control in ('text','foreign')
        geometry=dict(webGeometryVersion=1,requestId=request['commandId'],instance=self.current['instance'],sequence=self.geometry_sequence,
            capturedEpochMs=self.clock.tick(),document=dict(runId=self.run,href=self.current['url'],responseId=self.current['response'],readyState='complete'),
            control=control,editor=dict(focused=focused,text=text if editing else None,cursor=len(text) if editing else None,anchor=len(text) if editing else None),
            viewport=dict(width=640,height=480,scale=1,offsetLeft=0,offsetTop=0),rect=dict(x=80,y=y-40,width=160,height=80),
            center=dict(x=160,y=y),hit=0<=y<480,enabled=True,connected=True)
        if control.startswith('scroll-'):
            geometry.update(rect=dict(x=0,y=0,width=640,height=480),center=dict(x=320,y=240))
        return json.dumps(json.dumps(geometry))

    def send(self,request):
        self.command_log.append(deepcopy(request))
        if request['operation']!='measure':return super().send(request)
        command(request);self.sequence+=1
        view={key:self.documents[-1][key] for key in ('handle','creation','grant','page','url')}
        geometry=self.geometry_raw(request)
        self.raw=json.dumps(dict(picoBrowserVersion=2,commandId=request['commandId'],runId=self.run,ownerToken=self.owner,
            instance=self.instance,sequence=self.sequence,processId=31,capturedEpochMs=self.clock.epoch(),status='ready',
            source=dict(nativeView=view,geometryRaw=geometry)))

    def input(self,request):
        if request['control'].startswith('scroll-'):
            if self.fail!='ignored-wheel':self.scroll+=400 if request['control']=='scroll-down' else -400
            return
        super().input(request)

    def _tablet_web_io(self,target,flow,*,read_only=True):
        boundary=self
        class Owned(PicoTabletBrowserIO):
            def request(inner,*args,**kwargs):
                packet=super().request(*args,**kwargs)
                if packet['source'].keys() in ({'reserved'},{'delivered'},{'armed'},{'cancelled'},{'retired'}):flow.input_done()
                return packet
        reader=Owned(self.send,lambda:self.raw,self.clock.epoch,lambda:True,31,source_lock=self.lock,read_only=read_only,
            monotonic=self.clock.now,sleep=self.clock.sleep)
        if not read_only:reader.before_send=flow.input_fence().before_send
        return reader

    def _tablet_web_manager(self,target,flow):return PicoManager(self,flow)
    def action(self,flow,operation,callback):
        flow.input_begin(dict(kind='normal-ui',operation=operation))
        flow.input_fence().before_send(dict(command=operation));value=callback();flow.input_done();return value
    def _tablet_web_entry(self,target,flow,identifier,*,initial):
        label='WEB TEST' if identifier=='browser-app.web' else 'INLINE TEST'
        self.action(flow,'app-entry',lambda:super(PicoTarget,self)._tablet_web_entry(target,label,initial=initial));flow.tablet_lease(True)
    def _tablet_web_close(self,target,flow):
        self.action(flow,'app-close',lambda:super(PicoTarget,self)._tablet_web_close(target));flow.tablet_lease(False)
    def _tablet_web_lifecycle(self,target,flow,operation):
        flow.input_fence().before_send(dict(command=operation));return self.invoke(target,operation,{})

    def _tablet_web_vm(self,target,flow):
        b=self.vm;b.objects.epoch=self.clock.epoch();b.objects.host=self.clock.now()
        def measured(value):
            value.update(instance='a'*32,requestedEpochMs=self.clock.epoch(),capturedEpochMs=self.clock.epoch())
            if self.script is None:value['source']['engines']=[]
            else:value['source']['engines'][0]['url']=self.script
            pins,raw=reviewed();code_source(value,raw.decode(),submitted=self.vm_epoch+2)
            membership_source(value,[] if self.script is None else [manager(url=self.script,epoch=self.vm_epoch+1)],2 if self.script is None else 1)
            value['source'].update(effectSourceVersion=1,effects=dict(complete=True,scanRadiusMeters=64,scannedEntities=0,entities=[],absentIds=[]),
                loadSourceVersion=1,loads=dict(complete=True,instance='d'*32,sequence=0,events=[]),compiledSourceVersion=1)
            for engine in value['source']['engines']:
                engine['required'].update(sequence=0,modules=[])
                engine['compiled']=dict(compiledSourcesVersion=1,complete=True,compilations=[dict(scriptId=17,resourceName=self.script,**pins,compiledEpochMs=self.vm_epoch+3)])
        b.script.mutate=measured;scripts=b.script.reader();scripts.clock_ms=self.clock.epoch;scripts.monotonic=self.clock.now
        objects=b.objects.reader();objects.clock_ms=self.clock.epoch;objects.monotonic=self.clock.now
        return PicoBrowserVm(flow.run,flow.fixture_url,flow.live_owner['scriptUrl'],flow.role,self.binding,scripts,objects,
            PrivateFeatureState(self.path/('pico-tablet-web-'+flow.role+'-vm.json')),self.lock,
            lambda:flow.source.client.request('/runs/'+flow.run+'/browser'))

    def _web_runtime_observer(self,target,*,read_only=True):
        def send(request):
            self.runtime_sequence+=1;before=self.clock.tick();views=[];java=[]
            if self.current:
                native=self.dom_packet(secrets.token_hex(16))['source']['nativeView']
                source=hashlib.sha256(native['sourceUrl'].encode()).hexdigest();document=hashlib.sha256(native['url'].encode()).hexdigest()
                identity_row=dict(handle='42',creation=self.creation,grant=self.creation,page=self.page,sourceOwned=True,documentOwned=True,
                    sourceSha256=source,documentSha256=document)
                views=[dict(identity_row,surface='tablet',creationOwned=True,creationSha256=source,sessionActive=True,authorized=True,created=True,
                    pendingCreate=False,retryPending=False,suspended=False,loading=False,callbacks=0,scriptReplies=0,domPending=False)]
                java=[dict(identity_row,active=True,destroyed=False,closing=False,ownerCurrent=True,foreground=True,loading=False)]
                renderer_source=hashlib.sha256(self.current['url'].encode()).hexdigest() if 'inline' in self.current else source
                if 'inline' in self.current:java[0].update(sourceOwned=False,documentOwned=False,sourceSha256=renderer_source)
                self.renderer_rows.setdefault(self.creation,dict(id=secrets.token_hex(16),handle='42',creation=self.creation,sourceOwned=True,
                    sourceSha256=renderer_source,objectAlive=True,threadAlive=True,mainCallbacks=0,glCallbacks=0,retainedCallbacks=0,
                    closed=False,released=False,releaseSucceeded=True))
            for creation,row in self.renderer_rows.items():
                if not self.current or creation!=self.creation:row.update(objectAlive=False,threadAlive=False,closed=True,released=True)
            snap=lambda:dict(capturedEpochMs=self.clock.tick(),complete=True,knownHandles=deepcopy(self.known),views=deepcopy(views))
            native_before=snap();java_packet=dict(javaWebRuntimeVersion=2,commandId=request['commandId'],instance=self.runtime_instance,
                sequence=self.runtime_sequence,processId=31,capturedEpochMs=self.clock.tick(),complete=True,views=java,creations=[],
                renderers=deepcopy(sorted(self.renderer_rows.values(),key=lambda row:row['id'])))
            native_after=snap()
            self.runtime_raw=json.dumps(dict(webRuntimeVersion=2,commandId=request['commandId'],runId=request['runId'],instance=self.runtime_instance,
                sequence=self.runtime_sequence,processId=31,capturedEpochMs=self.clock.tick(),status='ready',
                source=dict(nativeBefore=native_before,java=java_packet,nativeAfter=native_after)))
        return NativeWebRuntime(send,lambda:self.runtime_raw,self.clock.epoch,lambda:True,31,require_renderers=True,
            monotonic=self.clock.now,sleep=self.clock.sleep)


class PicoManager(OriginalTabletManager):
    def __init__(self,target,flow):super().__init__(target);self.flow=flow
    def open(self):return self.target.action(self.flow,'scripts-open',super().open)
    def close_dialog(self):pass # Explicit native UI seam; no modal was opened here.
    def load_source(self,url):
        def load():
            super(PicoManager,self).load_source(url);self.target.vm_epoch=self.target.clock.epoch()
            self.target.vm.objects.row.update(registeredEpochMs=self.target.vm_epoch,workerCreatedEpochMs=self.target.vm_epoch+1)
            self.target.clock.sleep(.004)
        return self.target.action(self.flow,'scripts-load',load)
    def close_tablet(self):return self.target.action(self.flow,'scripts-tablet-close',super().close_tablet)
    def stop_source(self,url):
        def stop():
            super(PicoManager,self).stop_source(url)
            if self.target.script is None:
                epoch=self.target.clock.epoch()
                for kind in ('manager','engine','worker'):
                    self.target.vm.objects.row.update({kind+'Alive':False,kind+'DestroyedEpochMs':epoch})
        return self.target.action(self.flow,'scripts-stop',stop)
    def close(self):return self.target.action(self.flow,'scripts-close',super().close)

