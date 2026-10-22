"""Explicit synthetic target IO for the real Create host composition.

No feature operation/result is implemented here. Ordinary widget/SDK buffers,
original source packets and pixels are independent target-side test producers.
The target owns a deterministic query clock; real common deadlines and quiet
windows still use the host monotonic clock. This isolates protocol tests from
workstation scheduling and makes no device timing claim. The private-file producer compiles and executes the actual native header.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import nullcontext
from copy import deepcopy
import base64
import hashlib
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import io
import json
import math
from pathlib import Path
import sys
import threading
import time
from types import SimpleNamespace
from urllib.request import Request,urlopen
import uuid

ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT/'tests/device'),str(ROOT/'tests/device/adapters/android-phone'),str(Path(__file__).parent)]
from PIL import Image,ImageDraw
from adapters.native_feature_observation import NativeFeatureObservation
from adapters.native_avatar_render import NativeAvatarRender
from adapters.native_world_model_draws import NativeWorldModelDraws
from adapters.native_graphics_subject import NativeGraphicsSubject
from adapters.native_phone_touch_state import NativePhoneTouchState
from adapters.native_phone_web_runtime import NativePhoneWebRuntime
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUI,W3C_ELEMENT
from adapters.owned_world_render import WorldRenderOwner,OwnedWorldRenderCapture
from adapters.world_render_evidence import NativeWorldRenderCapture,image_name
from adapters.world_render_storage import NativeWorldRenderStorage
from adapters.world_render_receipts import NativeWorldReceiptInventory,NativeWorldReceiptBatchFiles
from adapters.token_create_ui import TokenCreateUI
from overte_phone_create_controls import PhoneCreateIO
from overte_phone_create_source import PhoneCreateSource
from overte_phone_create_marker import NativePhoneCreateFixture
from overte_phone_create_files import PhoneCreateFiles
from overte_phone_create_fixture import voxel_cells
from feature_journeys.fixtures import marker_bytes,payload
from feature_journeys.graphics_fixture import subject_ids
from overte_phone_graphics_effects import projected_box
from test_graphics_samples import Originals as WorldOriginals
from test_create_workflows import Widgets
from test_create_source import entity,DOMAIN,RUN
from test_create_marker import Boundary as MarkerBoundary
from self_tests.test_native_avatar_render import avatar_source,Boundary as AvatarBoundary
from self_tests.test_native_phone_touch_state import Boundary as TouchBoundary
from self_tests.test_native_phone_web_runtime import Boundary as WebBoundary
from self_tests.test_native_graphics_subject import Boundary as SubjectBoundary
from self_tests.test_native_feature_observation import Boundary as NativeBoundary
from self_tests.test_create_permissions import Settings
from fixture.create_permissions import CreatePermissions,STANDARD,OVERRIDES

POLICY=dict(source='world-render-target',marker=[24,24,152,56],subject=[280,155,720,595])


def epoch():return int(time.time()*1000)
def raw(value):return json.dumps(value)


class Target:
    def __init__(self,root,files):
        self.root,self.files=root,files;self.pid=files.process.pid;self.started=time.monotonic();self.clock=epoch();self.sequence={};self.rows=[]
        self.tablet=False;self.page=False;self.widgets=Widgets();self.widgets.texts.update({'create.voxel-diameter':'1','create.voxel-reach':'1'})
        self.error='';self.inputs=[];self.ignore=set();self.fault=None;self.capture=None;self.marker=None;self.marker_active=False
        self.view=avatar_source();self.view['cameraMode']='look at';self.view['pose']['feetPosition']=[0,0,0]
        self.web=WebBoundary();self.web.revoked=True;self.web.epoch=self.now()
        self.world=WorldOriginals(root);self.world.storage.mutate=lambda packet:packet.update(instance='a'*32,processId=self.pid,capturedEpochMs=self.now())
        self.world.inventory.mutate=lambda packet:packet.update(instance='a'*32,processId=self.pid,capturedEpochMs=self.now())
        self.settings=ThreadingHTTPServer(('127.0.0.1',0),Settings)
        self.settings.security={key:[] for key in OVERRIDES}
        self.settings.security['standard_permissions']=[dict(permissions_id=name,id_can_connect=True,id_can_rez=True,id_can_rez_tmp=True) for name in STANDARD]
        self.settings.domain=DOMAIN;self.settings.posts=[];self.settings.ignore=False
        self.settings_thread=threading.Thread(target=self.settings.serve_forever,daemon=True);self.settings_thread.start()
        self.permissions=CreatePermissions(files.process,lambda pid:pid==self.pid,self.settings.server_address[1],DOMAIN,PrivateFeatureState(root/'domain-permissions.json'))
        self.lock=threading.RLock();self.ticket=None;self.fixture=None

    def now(self):return self.clock
    def close(self):
        self.settings.shutdown();self.settings.server_close();self.settings_thread.join(2)
    def count(self,key):self.sequence[key]=self.sequence.get(key,0)+1;return self.sequence[key]
    def allowed(self):return self.settings.security['standard_permissions'][0]['id_can_rez']
    def envelope(self,key,request,source,*,instance='a'*32):
        now=self.now();return dict(schemaVersion=1,requestId=request['commandId'],instance=instance,sequence=self.count(key),processId=self.pid,
            requestedEpochMs=now,capturedEpochMs=now,source=deepcopy(source))
    def tools(self):
        return self.widgets.actual_tools()
    def controls(self):
        if not self.tablet:return []
        if not self.page:return [dict(id='create.entry',enabled=True,token='8'*32,focused=False,inputReady=True)]
        w=self.widgets;w.clock=time.monotonic()-self.started;value=w.capture();rows=value['controls']
        page=rows[0];page.update(toolSettings=self.tools(),statusError=bool(self.error),statusText=self.error)
        if w.tab==1:
            for row in self.rows:rows.append(dict(id='create.entity.'+row['id'],token=hashlib.sha256(row['id'].encode()).hexdigest()[:32],enabled=True,focused=False,inputReady=True,entityId=row['id']))
        if w.tab==2:rows.append(dict(id='create.delete',token='7'*32,enabled=True,focused=False,inputReady=True))
        return rows
    def ui(self,outer):
        request=outer['request'];w=self.widgets
        if request['action']!='observe':
            rows=[row for row in self.controls() if row['id']==request['controlId']]
            assert len(rows)==1 and rows[0]['token']==request['controlToken'] and request['sequence']==w.sequence+1
            w.sequence+=1;self.inputs.append(deepcopy(request));identifier=request['controlId'];action=request['action']
            if identifier not in self.ignore:
                if action=='replace':w.texts[identifier]=request['text']
                elif action=='select-index':w.choices[identifier]=request['index']
                elif action=='activate':
                    w.focus=identifier
                    if identifier=='create.entry':self.page=True
                    elif identifier.startswith('create.tab.'):w.tab=int(identifier.rsplit('.',1)[1])
                    elif identifier in ('create.new-model','create.new-shape'):
                        if self.allowed():self.create('Model' if identifier=='create.new-model' else 'Box')
                        else:self.error='Invalid entity type, properties or creation permission.'
                    elif identifier=='create.apply':
                        row=next(row for row in self.rows if row['id']==w.selected[0]);row['name']=w.texts['create.name']
                        for group in ('position','dimensions'):
                            keys=['create.field.'+group+'.'+axis for axis in 'xyz']
                            if all(key in w.texts for key in keys):row[group]=[float(w.texts[key]) for key in keys]
                    elif identifier=='create.apply-typed':
                        row=next(row for row in self.rows if row['id']==w.selected[0]);row['textures']=w.texts['create.textures'];url=json.loads(row['textures'])['checker.png']
                        ticket=url.split('/tickets/')[1].split('/')[0];data=payload('checker.png',RUN,ticket)[1]
                        row['render']['geometry']['textures']['rows']=[dict(complete=True,revision=2,material=0,channel=0,name='checker.png',urlSha256=hashlib.sha256(url.encode()).hexdigest(),
                            loaded=True,failed=False,originalSha256=hashlib.sha256(data).hexdigest(),originalBytes=len(data),gpuWidth=16,gpuHeight=16)]
                    elif identifier=='create.voxel-apply':
                        w.applied_diameter=float(w.texts['create.voxel-diameter']);w.applied_reach=float(w.texts['create.voxel-reach'])
                    elif identifier=='create.delete':self.rows=[row for row in self.rows if row['id'] not in w.selected];w.selected=[]
                    elif identifier.startswith('create.entity.'):
                        w.selected=[identifier[len('create.entity.'):]];w.tab=2;w.texts['create.name']=next(row['name'] for row in self.rows if row['id']==w.selected[0])
                    elif identifier in ('create.import-browse','create.export'):
                        save=identifier=='create.export';w.dialog=dict(caption='Select Where to Save' if save else 'Select .json to Import',save=save,directory='file:///private',error='',closing=False,pendingDocuments=False)
                    elif identifier=='create-file.cancel':w.dialog=None
                    elif identifier=='create-file.accept':
                        path=Path(w.texts[identifier.replace('accept','name')])
                        if w.dialog['save']:
                            row=next(row for row in self.rows if row['id']==w.selected[0]);document=dict(DataVersion=0,Entities=[dict(type=row['type'],name=row['name'],modelURL=row['modelUrl'],textures=row['textures'],dimensions=dict(zip('xyz',row['dimensions'])))])
                            with path.open('x') as stream:stream.write(json.dumps(document))
                            path.chmod(0o600)
                        else:
                            document=json.loads(path.read_text());item=document['Entities'][0]
                            self.create(item['type'],item.get('modelURL',''));self.rows[-1]['name']=item['name']
                        w.dialog=None
                    elif identifier=='create.voxel-remove':w.checked=not w.checked
            return dict(schemaVersion=1,commandId=request['commandId'],action=request['action'],performed=True,instance='4'*32,generation='5'*32,sequence=w.sequence,processId=self.pid)
        return dict(schemaVersion=1,commandId=request['commandId'],action='observe',instance='4'*32,generation='5'*32,sourceSequence=self.count('ui'),lastCommandSequence=w.sequence,
            elapsedMs=round((time.monotonic()-self.started)*1000),capturedEpochMs=self.now(),processId=self.pid,createControlsVersion=1,ready=True,controls=self.controls())
    def create(self,kind,url=None):
        w=self.widgets;row=entity('PolyVox' if kind=='PolyVox' else 'Model');row.update(id=str(uuid.uuid4()),instance=uuid.uuid4().hex,type=kind,name='Untitled',createdEpochUs=self.now()*1000)
        if kind=='Model':
            row['modelUrl']=url or w.texts['create.resource'];row['render']['geometry']['sourceSha256']=hashlib.sha256(row['modelUrl'].encode()).hexdigest()
            row['render']['modelInstance']=uuid.uuid4().hex;row['render']['geometry']['instance']=uuid.uuid4().hex
        elif kind=='Box':row.update(render=None,modelUrl='')
        else:row['voxel']['cells']=dict(sha256=hashlib.sha256(voxel_cells()).hexdigest(),occupied=64)
        self.rows.append(row);w.selected=[row['id']];w.tab=2;w.texts['create.name']=row['name'];self.error=''
        for group in ('position','dimensions'):
            for axis,value in zip('xyz',row[group]):w.texts['create.field.'+group+'.'+axis]=str(value)
    def entities(self,request):
        ids=request['trackedIds'];rows=[row for row in self.rows if row['id'] in ids or row['name'] in ['e2e-'+RUN+'-'+role for role in ('model','voxel','cube')]]
        source=dict(phoneCreateObservationVersion=2,connected=True,domainId=DOMAIN,sessionId=DOMAIN,canRez=self.allowed(),canRezTmp=self.allowed(),canRezAvatarEntities=True,
            scan=dict(center=[0,0,0],radiusMeters=128,scannedEntities=len(self.rows),complete=True,inventory=[dict(id=row['id'],instance=row['instance'],type=row['type'],host=row['host'],nameSha256=hashlib.sha256(row['name'].encode()).hexdigest()) for row in self.rows]),
            entities=rows,absentIds=[id for id in ids if id not in {row['id'] for row in self.rows}])
        value=self.envelope('entities',request,source);value['runId']=RUN
        if self.fault=='old-render' and value['source']['entities']:
            row=value['source']['entities'][0]
            if row['render'] is not None:row['render']['geometry']['sourceSha256']='0'*64
        return value
    def marker_input(self,request):
        self.marker_active=request['operation']=='prepare'
        if self.marker_active:
            b=MarkerBoundary();self.marker=deepcopy(b.fixture)
            self.marker=json.loads(json.dumps(self.marker).replace('d'*32,RUN));self.marker['originalInput']=deepcopy(request)
            self.marker['originalView']=deepcopy(self.view['view'])|dict(feetPosition=[0,0,0],modelScale=1.,boomLength=0.,mode='first person look at')
            from overte_phone_create_marker import layout
            for row in self.marker['entities']:
                row['sourceUrl']=self.fixture+'tickets/'+request['ticket']+'/graphics-marker.v1.html' if row['role']=='marker' else ''
                row.update(layout(self.marker)[row['role']]);row['lastEditedEpochUs']=self.now()*1000
            self.marker['createdEpochMs']=self.now();self.marker['phase']='active'
            self.web.revoked=False;self.web_birth=self.now()
        else:self.marker.update(phase='drained',entities=[],absentIds=[row['id'] for row in self.marker['objects']],retainedObjects=0);self.web.revoked=True
        return dict(phoneCreateFixtureInputVersion=1,commandId=request['commandId'],runId=RUN,fixtureInstance='e'*32,operation=request['operation'],recorded=True)
    def capture_packet(self,request):
        b=AvatarBoundary();packet=deepcopy(b.capture);now=self.now();packet.update(requestId=request['commandId'],sequence=self.count('capture'),processId=self.pid,requestedEpochMs=now,capturedEpochMs=now)
        source=packet['source'];source.update(sourceExtent=[1000,750],sourceViewport=[0,0,1000,750],targetExtent=[1000,750],acquisitionSequence=self.sequence['capture'],recordedEpochMs=now,startedEpochMs=now,capturedEpochMs=now)
        source['renderTrace'].update(frameId=uuid.uuid4().hex,recordedEpochMs=now,begunEpochMs=now,completedEpochMs=now,recordedView=deepcopy(self.view['view']))
        image=Image.new('RGBA',(1000,750),(128,128,128,255));draw=ImageDraw.Draw(image)
        draw.rectangle((0,0,499,749),fill=(40,70,100,255))
        for row in self.rows:
            geometry=deepcopy(row)
            if row['type']=='Model':geometry['dimensions'][2]=0
            box=projected_box(geometry,self.view['view'],[1000,750]);box=tuple(round(value) for value in box)
            color=(180,90,50,255) if row['type']=='Model' else (50,170,70,255) if row['type']=='PolyVox' else (90,80,210,255)
            draw.rectangle(box,fill=color)
            if row['textures']:draw.rectangle((box[0],box[1],(box[0]+box[2])//2,box[3]),fill=(10,20,240,255))
            if row['type']=='PolyVox' and row['voxel']['cells']['occupied']<64:draw.rectangle((box[0],box[1],box[2],(box[1]+box[3])//2),fill=(128,128,128,255))
        with Image.open(io.BytesIO(marker_bytes(RUN,self.ticket))) as card:image.paste(card,(20,20))
        stream=io.BytesIO();image.save(stream,format='PNG');data=stream.getvalue()
        source['image'].update(name=image_name(request['commandId']),width=1000,height=750,bytes=len(data),sha256=hashlib.sha256(data).hexdigest(),pixelSha256=hashlib.sha256(image.tobytes()).hexdigest())
        self.world.storage.raw=data;self.world.storage.present=True;self.capture=deepcopy(packet);return packet
    def source(self,key,request):
        if key=='native' and self.fault=='slow-native':time.sleep(5.1)
        if key=='entities':return self.entities(request)
        if key=='ui':return self.ui(request)
        if key=='files':
            self.files.send(request);value=deepcopy(self.files.value);value.update(requestedEpochMs=self.now(),capturedEpochMs=self.now());return value
        if key=='marker':return self.envelope(key,request,self.marker,instance='f'*32)
        if key=='avatar':return self.envelope(key,request,self.view,instance='f'*32)
        if key=='touch':return self.envelope(key,request,TouchBoundary().touch,instance='f'*32)
        if key=='web':
            now=self.now();self.web.now=lambda:now;self.web.saved=request;self.web.started=now;self.web.sequence=self.count(key);value=self.web.packet()
            url=self.fixture+'tickets/'+self.marker['originalInput']['ticket']+'/graphics-marker.v1.html' if self.marker else self.fixture+'tickets/'+'c'*32+'/graphics-marker.v1.html'
            old=hashlib.sha256(('http://controlled.invalid/feature-fixture/v1/runs/'+RUN+'/tickets/'+'c'*32+'/graphics-marker.v1.html').encode()).hexdigest();new=hashlib.sha256(url.encode()).hexdigest()
            value=json.loads(json.dumps(value).replace(old,new));value['processId']=self.pid;value['source']['java']['processId']=self.pid
            for side in ('nativeBefore','nativeAfter'):
                if self.marker is None:value['source'][side].update(knownHandles=[],views=[])
                else:
                    for row in value['source'][side]['knownHandles']:row['firstObservedEpochMs']=self.web_birth
            if self.marker is None:value['source']['java']['views']=[]
            return value
        if key=='native':
            b=NativeBoundary();b.sequence=self.count(key)-1;b.send(request);value=b.sample;now=self.now()
            def times(value):
                if type(value) is dict:
                    for k,v in value.items():
                        if k.endswith('EpochMs'):value[k]=now
                        else:times(v)
                elif type(value) is list:
                    for row in value:times(row)
            times(value);value['processId']=self.pid
            if self.fault=='stale-native':value['capturedEpochMs']-=1501;value['requestedEpochMs']-=1501;value['animationFence']['requestedEpochMs']-=1501
            return value
        if key=='subject':
            b=SubjectBoundary();b.source.update(subjectVersion=2,avatarPose=deepcopy(self.view['pose']));b.source['view']['mode']=self.view['cameraMode']
            b.source['scan']['unowned']=[dict(id=row['id'],sha256=hashlib.sha256(raw(row).encode()).hexdigest()) for row in self.rows]
            b.source['scan']['scannedEntities']=len(self.rows);value=self.envelope(key,request,b.source);value['runId']=RUN;return value
        if key=='capture':return self.capture_packet(request)
        if key=='draws':
            packet=self.capture;source=packet['source'];models=[]
            for row in self.rows:
                if row['render'] is None:continue
                render=row['render'];geometry=render['geometry'];models.append(dict(modelInstance=render['modelInstance'],geometryInstance=geometry['instance'],loadedSourcePresent=True,loadedSourceSha256=geometry['sourceSha256'],
                    drawCommands=1,skinnedDrawCommands=0,blendshapedDrawCommands=0,originalGeometryDrawCommands=1,indices=36,minimum=[row['position'][0]-.5,row['position'][1]-.5,row['position'][2]],maximum=[row['position'][0]+.5,row['position'][1]+.5,row['position'][2]]))
            trace=source['renderTrace'];model_trace={key:trace[key] for key in ('frameId','recordedEpochMs','begunEpochMs','completedEpochMs','renderer','view')}
            model_trace.update(modelTraceVersion=1,drawCommands=len(models),models=models)
            return self.envelope(key,request,dict(modelCaptureVersion=1,captureRequestId=packet['requestId'],captureSequence=packet['sequence'],acquisitionSequence=source['acquisitionSequence'],captureCapturedEpochMs=source['capturedEpochMs'],
                imageSha256=source['image']['sha256'],pixelSha256=source['image']['pixelSha256'],modelTrace=model_trace))
        raise AssertionError(key)
    def rpc(self,kind,value):
        with self.lock:
            if kind=='clock':return self.now()
            self.clock+=1
            if kind=='source':return self.source(value['key'],value['request'])
            if kind=='marker-input':return self.marker_input(value)
            if kind=='tablet':return self.tablet
            if kind=='binding':return dict(sourceRevision='a'*40,artifactSha256='b'*64,processIdentity=str(self.pid)+':14',sessionId='native-session',generation=1,targetFingerprint='c'*64)
            if kind=='camera':self.view['cameraMode']=value;return None
            if kind=='storage':self.world.storage_send(value);return None
            if kind=='receipt':return (self.world.receipt_root/value).read_text()
            if kind=='inventory':
                self.world.inventory.owner=value['owner'];self.world.inventory.retired=not self.world.storage.present;self.world.inventory.present=self.world.storage.present
                self.world.inventory.callbacks=self.world.storage.callbacks;self.world.inventory.png_bytes=len(self.world.storage.raw) if self.world.storage.present else 0
                self.world.inventory.send(value['request']);return json.loads(self.world.inventory.original())
            if kind=='sdk':
                method,path,body=value
                if path.endswith('/window/rect'):return dict(x=0,y=0,width=1000,height=750)
                if path.endswith('/elements'):
                    id=body['value'].rsplit('/',1)[-1]
                    visible=id=='tablet.open' and not self.tablet or id in ('nav.close','nav.home') and self.tablet
                    return [{W3C_ELEMENT:id}] if visible else []
                if path.endswith('/displayed') or path.endswith('/enabled'):return True
                if path.endswith('/click'):
                    id=path.split('/element/')[1].split('/')[0]
                    if id=='tablet.open':self.tablet=True;self.page=False
                    elif id=='nav.close':self.tablet=False
                    elif id=='nav.home':self.page=False
                    return None
                if path.endswith('/actions'):
                    if method=='POST' and 'world-click' not in self.ignore:
                        row=next(row for row in self.rows if row['type']=='PolyVox');data=bytearray(voxel_cells());data[2*64+2*8+2]=0
                        row['voxel']['cells']=dict(sha256=hashlib.sha256(data).hexdigest(),occupied=63);row['voxel']['savedSha256']=hashlib.sha256(b'changed actual cells').hexdigest()
                    return None
                raise AssertionError(path)
            raise AssertionError(kind)


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            value=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            if self.path=='/v1/create-permissions':
                assert self.headers.get('X-Overte-E2E-Token')=='z'*64;value=self.server.target.permissions.request(value)
            else:value=self.server.target.rpc(value['kind'],value['value'])
            body=json.dumps(value).encode();self.send_response(200)
        except Exception as error:
            import traceback;traceback.print_exc();self.server.errors.append(type(error).__name__);body=b'{}';self.send_response(500)
        self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
    def log_message(self,*_args):pass


class Proxy:
    def __init__(self,url,root):self.url,self.root=url,Path(root);self.binding=self.call('binding',None)
    def call(self,kind,value):
        request=Request(self.url+'/rpc',data=json.dumps(dict(kind=kind,value=value)).encode(),headers={'Content-Type':'application/json'})
        with urlopen(request,timeout=10) as response:return json.loads(response.read())
    def clock_ms(self):return self.call('clock',None)
    def state_path(self,_selector):return self.root/'session.json'
    def existing_input_session(self,_selector):return nullcontext()
    def normal_feature_runtime(self,_selector,*,read_only):
        assert read_only
        client=SimpleNamespace(call=lambda method,path,body:self.call('sdk',[method,path,body]))
        return NativeUI(client,'synthetic',lambda:True),None,deepcopy(self.binding),lambda:True,None
    def reader(self,key,cls,**kwargs):
        original=[None]
        def send(request):original[0]=self.call('source',dict(key=key,request=request))
        return cls(send,lambda:json.dumps(original[0]),self.clock_ms,lambda:True,int(self.binding['processIdentity'].split(':')[0]),**kwargs)
    def _native_feature_observer(self,_s,**kw):return self.reader('native',NativeFeatureObservation)
    def _create_source(self,_s,**kw):return self.reader('entities',PhoneCreateSource)
    def _create_files(self,_s,**kw):return self.reader('files',PhoneCreateFiles)
    def _avatar_render_observer(self,_s,**kw):return self.reader('avatar',NativeAvatarRender)
    def _touch_state_observer(self,_s,**kw):return self.reader('touch',NativePhoneTouchState)
    def _web_runtime_observer(self,_s,**kw):return self.reader('web',NativePhoneWebRuntime)
    def _world_model_draws_observer(self,_s,**kw):return self.reader('draws',NativeWorldModelDraws)
    def _graphics_subject_observer(self,_s,**kw):return self.reader('subject',NativeGraphicsSubject)
    def _create_fixture_observer(self,_s,**kw):return self.reader('marker',NativePhoneCreateFixture)
    def _create_fixture_input(self,_s,command,**kw):return self.call('marker-input',command)
    def _create_controls(self,_s,intent,**kw):
        io_=self.reader('ui',PhoneCreateIO,tablet_shown=lambda:self.call('tablet',None))
        return TokenCreateUI(io_,intent)
    def _graphics_surface(self,_s,run,intent,owns,lease,*args,**kw):
        # Explicit synthetic View-menu input endpoint. Real menu recipe has its
        # own original SDK tests; this endpoint never supplies feature facts.
        def camera(mode):
            source=self._graphics_subject_observer(_s).read(run,require_avatar=True);intent('camera',source,None,mode)
            self.call('camera',mode)
        return SimpleNamespace(select_camera=camera)
    def _world_render_capture(self,_s,*,read_only,role,**kw):
        pid=int(self.binding['processIdentity'].split(':')[0]);original=[None]
        owner=WorldRenderOwner(PrivateFeatureState(self.root/('create-world-'+role+'.json')),self.binding,lambda:True,role=role)
        storage=NativeWorldRenderStorage(lambda request:self.call('storage',request),lambda name:self.call('receipt',name),self.clock_ms,lambda:True,pid,receipt_intent=owner.receipt_intent)
        def inventory(request):original[0]=self.call('inventory',dict(owner=owner.owned(),request=request))
        cleanup=NativeWorldReceiptInventory(inventory,lambda:json.dumps(original[0]),self.clock_ms,lambda:True,pid,owner.owned,lambda:storage.instance)
        files=NativeWorldReceiptBatchFiles(SimpleNamespace(read=lambda name:self.call('receipt',name)),cleanup)
        capture=NativeWorldRenderCapture(lambda request:original.__setitem__(0,self.call('source',dict(key='capture',request=request))),lambda:json.dumps(original[0]),
            storage,self.clock_ms,lambda:True,pid,intent=owner.intent,require_trace=True,require_frame_view=True)
        return OwnedWorldRenderCapture(capture,storage,owner,files)
