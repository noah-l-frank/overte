"""Complete v17 composition at explicit synthetic target boundaries.

Real ordinary NativeUI and token transports, private CAS journals, PNG decode,
HTTP source and common Journey execute. Native Qt/GPU/kernel boundaries remain
synthetic; these tests claim neither a native build nor device acceptance.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import hashlib
import io
import json
import math
import os
import subprocess
import sys
import tempfile
import unittest
import uuid
from unittest.mock import patch
from urllib.parse import urlsplit

ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT/'tests/device'),str(ROOT/'tests/device/adapters/android-phone')]
from PIL import Image,ImageDraw
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.native_feature_observation import NativeFeatureObservation
from adapters.native_avatar_render import NativeAvatarRender
from adapters.native_navigation_replies import NativeNavigationReplies
from adapters.native_phone_web_runtime import NativePhoneWebRuntime
from feature_journeys.contract import arguments
from feature_journeys.engine import Journey
from feature_journeys.fixtures import context,marker_bytes
from feature_journeys.navigation_fixture import NavigationResources,DIRECTORY,QUERY
from feature_journeys.witness import Client,Journal
from feature_journeys.evidence import read_private_artifact
from feature_journeys.scenarios import VERSION
from overte_phone_navigation_feature import PhoneNavigationFeature,NavigationImages
from overte_phone_navigation_fixture import NavigationFixtureReader
from overte_phone_navigation_native import PhoneNavigationIO,PhoneNavigationView,validate as validate_view
from overte_phone_navigation_marker import NativePhoneNavigationMarker
from overte_phone_script_history import unpack,canonical
from self_tests.test_phone_navigation import NativePhone
from self_tests.test_native_feature_observation import Boundary as LifecycleBoundary
from self_tests.test_native_avatar_render import avatar_source
from self_tests.test_world_render_evidence import frame_view
from self_tests.test_native_phone_web_runtime import Boundary as WebBoundary
from self_tests.test_native_process_presence import Boundary as PresenceBoundary
from test_graphics_samples import Originals

RUN='b'*32
URL='http://controlled.invalid/feature-fixture/v1'
ORIGIN='http://controlled.invalid'
POLICY=dict(imageExtent=[640,480],markerRoi=[20,20,180,60],imagePolicy=dict(source='world-render-target',marker=[24,24,152,56],subject=[200,100,600,420]))
INPUTS=dict(protocolSignature='AAAAAAAAAAAAAAAAAAAAAA==',sourceRevision='1'*40,sceneUrl=ORIGIN+'/owned/scene.json')


class SDK(NativePhone):
    def __init__(self,owner):
        super().__init__();self.owner=owner;self.scene=INPUTS['sceneUrl'];self.current=self.scene
    def arrive(self,url):
        if url.startswith('hifi://hidden-'):
            with self.owner.provider.response(DIRECTORY+'/'+context(RUN)['hidden'],'') as response:
                status,raw,identifier=response
            self.owner.modal=True;self.owner.reply=dict(sequence=1,eventId=uuid.uuid4().hex,runId=RUN,responseId=identifier,origin=ORIGIN,
                httpStatus=status,networkError=203,contentNotFound=True,current=True,lookupGeneration=2,callbackEpochMs=self.owner.epoch())
            return
        original=url
        if '?' not in url:url+='?location=/0,0,4/0,0,0,1'
        super().arrive(url)
        self.current=original
    def sleep(self,value):self.owner.sleep(value)
    def call(self,method,path,body=None):
        if path.endswith('/text'):return self.field
        if path.endswith('/source'):
            return '<hierarchy><node package="io.github.noah_be.overte.phone" /></hierarchy>'
        return super().call(method,path,body)


class Composite(Originals):
    def __init__(self,root):
        super().__init__(root);self.sdk=SDK(self);self.binding.update(sourceRevision='1'*40,artifactSha256='2'*64,processIdentity='31:19',sessionId='owned-session')
        self.pid=31;self.birth='a'*32;self.running=True;self.launches=1;self.activations=1;self.qt_sequence=0;self.qt_command=0
        self.view_sequence=0;self.native_sequence=0;self.marker_sequence=0;self.avatar_sequence=0
        self.focus=None;self.dialog=False;self.dialog_old='';self.dialog_text='';self.query='';self.records=[];self.page_birth='c'*32
        self.bookmark_path=root/'native-location-bookmarks.json';self.bookmarks={'Unowned':ORIGIN+'/personal'};self.persist()
        self.modal=False;self.reply=None;self.marker=None;self.marker_input_count=0;self.fault='';self.inputs=[]
        self.actor_enabled=False;self.actor_busy=False;self.actor_retired=False;self.actor_error=None
        self.provider=NavigationResources(INPUTS,clock_ms=self.epoch);self.provider.provision(RUN)
        self.journal=Journal(self.epoch)
        with patch('feature_journeys.witness.secrets.token_hex',return_value=RUN):self.journal.register('world-navigation')
        self.reader=Client(URL,'x'*64);self.actor=Client(URL,'y'*64)
        for role,client in [('primary',self.reader),('actor',self.actor)]:client.request=lambda *args,role=role,**kwargs:self.request(role,*args,**kwargs)
        self.web_known=[];self.web=WebBoundary();self.web.now=self.epoch;self.web.edit=self.web_edit
        self.storage.mutate=lambda packet:packet.update(instance=self.birth,processId=self.pid,capturedEpochMs=self.epoch())
        self.inventory.mutate=lambda packet:packet.update(instance=self.birth,processId=self.pid,capturedEpochMs=self.epoch())
        self.activate(uuid.uuid4().hex)
    def epoch(self):return 100000+round(self.sdk.clock*1000)
    def options(self):return dict(monotonic=lambda:self.sdk.clock,sleep=self.sleep)
    def guard(self):return self.running
    def state_path(self,_selector):return self.root/'session.json'
    @contextmanager
    def existing_input_session(self,_selector):yield
    def normal_feature_runtime(self,_selector,*,read_only=False):
        if not self.guard():raise NativeUIError('Synthetic process is absent')
        return self.sdk.ui,None,deepcopy(self.binding),self.guard,None
    def world_render_store(self,_selector,*,role='primary'):return PrivateFeatureState(self.root/('world-'+role+'.json'))
    def persist(self):self.bookmark_path.write_text(json.dumps(self.bookmarks,sort_keys=True));self.bookmark_path.chmod(0o600)
    def request(self,role,path,value=None,method=None,**kwargs):
        if path=='/navigation-provider':return self.provider.ready()|dict(internalErrors=0)
        if path.endswith('/phase'):return self.journal.phase(RUN,kwargs['phase_nonce'])
        if path.endswith('/navigation'):return self.provider.snapshot(RUN)
        if path.endswith('/samples'):
            assert role=='actor';return self.journal.publish(RUN,value)
        if path.endswith('/'+RUN):return self.journal.snapshot(RUN)
        raise AssertionError('Unexpected synthetic fixture request '+path)
    def activate(self,ticket,verb='baseline',inputs=None):
        self.journal.activate(RUN,ticket,verb,inputs or {});self.provider.activate(RUN,ticket)
    def sleep(self,value):
        self.sdk.clock+=value
        if self.actor_enabled and not self.actor_busy and not self.actor_retired:
            # Simulate separately scheduled actors only after the input owner
            # releases the real advisory lock; never pay a wall-clock wait in
            # the single-threaded synthetic clock.
            import fcntl,os
            lock=os.open(self.root/'phone-script-sources.lock',os.O_RDWR|os.O_CREAT,0o600)
            try:
                try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
                except BlockingIOError:return
                fcntl.flock(lock,fcntl.LOCK_UN)
            finally:os.close(lock)
            self.actor_busy=True
            try:self.flow('actor').publish()
            except Exception as error:
                from feature_journeys.phase_fixture import PhasePending,PhaseRetired
                from overte_phone_script_lock import PhoneScriptSourceBusy
                if isinstance(error,PhaseRetired):self.actor_retired=True
                elif not isinstance(error,(PhasePending,PhoneScriptSourceBusy)):
                    self.actor_error=error;raise
            finally:self.actor_busy=False
    def flow(self,role='primary'):
        client=self.reader if role=='primary' else self.actor
        return PhoneNavigationFeature(self,'controlled',NavigationFixtureReader(client,RUN,epoch_ms=self.epoch,monotonic=lambda:self.sdk.clock),
            self.root,POLICY,role=role,**self.options())
    def _navigation_probe(self,_selector,after=0):
        self.sdk.sequence=max(self.sdk.sequence,after);return self.sdk.observe()
    def _native_feature_observer(self,_selector,*,read_only=False):
        source=LifecycleBoundary()
        def send(command):
            source.send(command);self.native_sequence+=1
            source.sample.update(instance=self.birth,sequence=self.native_sequence,processId=self.pid,requestedEpochMs=self.epoch(),capturedEpochMs=self.epoch(),
                animationFence=dict(rigId=2,sequence=self.native_sequence+9,requestedEpochMs=self.epoch()),
                lifecycle=dict(backgrounds=0,activations=self.activations,launches=self.launches))
            source.sample['animation']['capturedEpochMs']=self.epoch();source.sample['animation']['clip']['evaluatedEpochMs']=self.epoch()
        return NativeFeatureObservation(send,source.original,self.epoch,self.guard,self.pid,**self.options())
    def native_source(self):
        ui=dict(present=self.sdk.screen=='places',addressDialog=self.sdk.address_open,notFoundModal=self.modal,bookmarkDialog=self.dialog,pendingCommands=0,activeTimers=0,notFound=dict(modalId='e'*32,createdEpochMs=self.reply['callbackEpochMs'],nativeEvent=deepcopy(self.reply)) if self.modal else {})
        if ui['present']:
            model=[dict(placeId=row['id'],placeName=row['name'],placeAddress=row['address']) for row in self.records
                if self.query.lower().strip() in (row['name']+' '+row['address']).lower()]
            ui.update(generation=self.page_birth,source='file:///actual/scripts/system/places/PicoPlaces.qml',query=self.query,records=deepcopy(self.records),model=model,
                servers=[dict(serverUrl=ORIGIN,serverIndex=0,fetched=True,pinned=False,failed=False)],loading=False,
                maturity=['everyone','teen','mature','adult','unrated'],currentAddress=self.sdk.current)
        raw=self.bookmark_path.read_bytes();stored=json.loads(raw)
        if stored!=self.bookmarks:raise NativeUIError('Synthetic actual backing storage differs')
        prefs={key:dict(present=False,value=None) for key in ('placesAppMetaverseToFetch','placesAppPinnedMetaverse','placesAppMaturityFilter','private/places/federation')}
        value=dict(tabletShown=self.sdk.screen is not None,ui=ui,storage=dict(present=True,sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),bookmarks=deepcopy(stored)),
            keyboard=dict(available=True,backend='native-touch-metrics',visible=False),preferences=prefs,endpoint=ORIGIN,protocolSignature=INPUTS['protocolSignature'])
        if self.fault=='keyboard-visible':value['keyboard']['visible']=True
        if self.fault=='foreign-modal' and self.modal:value['ui']['notFound']['nativeEvent']['eventId']='f'*32
        if self.fault=='foreign-preferences':value['preferences']['placesAppMaturityFilter']=dict(present=True,value=['adult'])
        return value
    def _navigation_view(self,_selector,*,read_only=False):
        state={}
        def send(request):
            self.view_sequence+=1;value=dict(navigationViewVersion=1,commandId=request['commandId'],runId=RUN,instance=self.birth,sequence=self.view_sequence,
                processId=self.pid,requestedEpochMs=self.epoch(),capturedEpochMs=self.epoch(),source=self.native_source())
            if self.fault=='view-cursor':value['sequence']=1
            state['value']=value
        return PhoneNavigationView(send,lambda:json.dumps(state['value']),self.epoch,self.guard,self.pid,**self.options())
    def qt_rows(self):
        ids=[];rows=[]
        if self.modal:ids=['error.ok']
        elif self.sdk.screen=='home':ids=['entry']
        elif self.sdk.screen=='places':
            if self.dialog:ids=['bookmarkName','bookmark.save','bookmark.cancel']
            else:ids=['page','placesTab','bookmarksTab','serversTab','refreshPlaces','addBookmark','placesSearch']
        for name in ids:
            row=dict(id='navigation.'+name,enabled=True,focused=self.focus==name,inputReady=name!='page')
            if name=='placesSearch':row['text']=self.query
            if self.dialog:row.update(dialogOriginalName=self.dialog_old,dialogAddress=self.sdk.current)
            if name=='bookmarkName':row['text']=self.dialog_text
            rows.append(row)
        if self.sdk.screen=='places' and not self.dialog:
            for index,name in enumerate(sorted(self.bookmarks)):
                for kind in ('visitBookmark','renameBookmark','deleteBookmark'):
                    rows.append(dict(id='navigation.'+kind+'.'+str(index),enabled=True,focused=False,inputReady=True,bookmarkName=name,bookmarkAddress=self.bookmarks[name]))
            for index,record in enumerate(self.records):
                if self.query.lower() in record['name'].lower():rows.append(dict(id='navigation.visitPlace.'+str(index),enabled=True,focused=False,inputReady=True,
                    placeId=record['id'],placeName=record['name'],placeAddress=record['address']))
        for row in rows:row['token']=hashlib.sha256(canonical(row)).hexdigest()[:32]
        return rows
    def _navigation_controls(self,_selector,*,read_only=False):
        current={}
        def send(outer):
            request=outer['request'];self.qt_sequence+=1
            if request['action']=='observe':
                current['value']=dict(schemaVersion=1,commandId=request['commandId'],action='observe',instance=self.birth,generation=self.birth,
                    sourceSequence=self.qt_sequence,lastCommandSequence=self.qt_command,elapsedMs=round(self.sdk.clock*1000),capturedEpochMs=self.epoch(),
                    processId=self.pid,navigationControlsVersion=1,ready=True,controls=self.qt_rows());return
            assert not read_only
            self.qt_command+=1;rows=[r for r in self.qt_rows() if r['id']==request['controlId']]
            assert len(rows)==1 and rows[0]['token']==request['controlToken']
            name=request['controlId'].removeprefix('navigation.');self.inputs.append((request['action'],name))
            self.qt_input(name,request)
            current['value']=dict(schemaVersion=1,commandId=request['commandId'],action=request['action'],performed=True,instance=self.birth,generation=self.birth,
                sequence=self.qt_command,processId=self.pid)
            if self.fault=='lost-bookmark-save' and name=='bookmark.save':raise RuntimeError('Synthetic lost input return')
        return PhoneNavigationIO(send,lambda:json.dumps(current['value']),self.epoch,self.guard,self.pid,**self.options())
    def qt_input(self,name,request):
        if request['action']=='replace':
            if name=='placesSearch' and self.fault!='ignore-search':self.query=request['text']
            elif name=='bookmarkName':self.dialog_text=request['text']
            return
        if name=='entry':self.sdk.screen='places';self.query='';self.page_birth=uuid.uuid4().hex
        elif name=='refreshPlaces':
            with self.provider.response(DIRECTORY,QUERY) as response:status,body,_=response
            self.records=json.loads(body)['data']['places']
        elif name=='addBookmark':self.dialog=True;self.dialog_old='';self.dialog_text=''
        elif name.startswith('renameBookmark.'):
            self.dialog_old=sorted(self.bookmarks)[int(name.rsplit('.',1)[1])];self.dialog_text=self.dialog_old;self.dialog=True
        elif name=='bookmark.save':
            if self.dialog_old:self.bookmarks[self.dialog_text]=self.bookmarks.pop(self.dialog_old)
            else:self.bookmarks[self.dialog_text]=self.sdk.current
            self.persist();self.dialog=False
        elif name=='bookmark.cancel' and self.fault!='ignore-cancel':self.dialog=False
        elif name=='error.ok':self.modal=False
        elif name.startswith('deleteBookmark.'):
            self.bookmarks.pop(sorted(self.bookmarks)[int(name.rsplit('.',1)[1])]);self.persist()
        elif name.startswith('visitBookmark.'):self.sdk.arrive(self.bookmarks[sorted(self.bookmarks)[int(name.rsplit('.',1)[1])]])
        elif name.startswith('visitPlace.'):self.sdk.arrive(self.records[int(name.rsplit('.',1)[1])]['address'])
        elif name in ('placesSearch','bookmarkName'):self.focus=name
    def avatar(self):
        source=avatar_source();source['pose']['feetPosition']=[self.sdk.position[k] for k in 'xyz'];source['cameraMode']='first person look at'
        source['view']=frame_view();source['view']['position']=[self.sdk.position['x'],1.6,6]
        return source
    def _avatar_render_observer(self,_selector,*,read_only=True):
        state={}
        def send(request):
            self.avatar_sequence+=1;state['value']=dict(schemaVersion=1,requestId=request['commandId'],instance=self.birth,sequence=self.avatar_sequence,
                processId=self.pid,requestedEpochMs=self.epoch(),capturedEpochMs=self.epoch(),source=self.avatar())
        return NativeAvatarRender(send,lambda:json.dumps(state['value']),self.epoch,self.guard,self.pid,**self.options())
    def _navigation_marker_input(self,_selector,request):
        self.marker_input_count+=1
        if request['operation']=='prepare':
            avatar=self.avatar();view=deepcopy(avatar['view'])|dict(feetPosition=avatar['pose']['feetPosition'],modelScale=1,boomLength=0,mode=avatar['cameraMode'])
            f=1/math.tan(math.radians(30));aspect=4/3;x=self.sdk.position['x'];z=6
            position=[x+(-1+2*100/640)*.25*aspect/f,1.6+(1-2*40/480)*.25/f,z-.25]
            dimensions=[160/640*2*.25*aspect/f,40/480*2*.25/f,.01];id=uuid.uuid4();self.web.revoked=False
            self.marker=dict(phoneNavigationMarkerVersion=1,fixtureInstance=uuid.uuid4().hex,runId=RUN,phase='active',createdEpochMs=self.epoch(),
                originalInput=deepcopy(request),originalView=view,objects=[dict(role='marker',id=str(id))],entities=[dict(id=str(id),role='marker',originalObject=True,
                    name='e2e-'+RUN+'-navigation-marker',type='Web',parentId='00000000-0000-0000-0000-000000000000',hostType='local',position=position,rotation=[0,0,0,1],
                    dimensions=dimensions,color=[255,255,255],visible=True,sourceUrl=request['fixtureUrl']+'tickets/'+request['ticket']+'/graphics-marker.v1.html',
                    locked=False,collisionless=True,canCastShadow=False,dpi=100,lastEditedEpochUs=self.epoch()*1000)],absentIds=[],retainedObjects=1)
            marker_url=self.marker['entities'][0]['sourceUrl']
            self.web_known.append(dict(handle=str(len(self.web_known)+1),firstObservedEpochMs=self.epoch(),sourceSha256=hashlib.sha256(marker_url.encode()).hexdigest()))
        else:
            self.marker.update(phase='drained',entities=[],absentIds=[row['id'] for row in self.marker['objects']],retainedObjects=0);self.web.revoked=True
        return dict(phoneNavigationMarkerInputVersion=1,commandId=request['commandId'],runId=RUN,fixtureInstance=self.marker['fixtureInstance'],operation=request['operation'],recorded=True)
    def _navigation_marker(self,_selector,*,read_only=True):
        state={}
        def send(request):
            self.marker_sequence+=1;state['value']=dict(schemaVersion=1,requestId=request['commandId'],instance=self.birth,sequence=self.marker_sequence,
                processId=self.pid,requestedEpochMs=self.epoch(),capturedEpochMs=self.epoch(),source=deepcopy(self.marker))
        return NativePhoneNavigationMarker(send,lambda:json.dumps(state['value']),self.epoch,self.guard,self.pid,**self.options())
    def web_edit(self,value):
        value.update(runId=RUN,processId=self.pid,instance=self.birth);value['source']['java']['processId']=self.pid
        source=self.marker['originalInput']['fixtureUrl']+'tickets/'+self.marker['originalInput']['ticket']+'/graphics-marker.v1.html'
        wanted=hashlib.sha256(source.encode()).hexdigest()
        import self_tests.test_native_phone_web_runtime as original
        def walk(row):
            if type(row) is dict:
                for key,item in row.items():
                    if item==original.SHA:row[key]=wanted
                    else:walk(item)
            elif type(row) is list:
                for item in row:walk(item)
        walk(value)
        for key in ('nativeBefore','nativeAfter'):
            value['source'][key]['knownHandles']=deepcopy(self.web_known)
            for row in value['source'][key]['views']:row['handle']=self.web_known[-1]['handle']
        for row in value['source']['java']['views']:row['handle']=self.web_known[-1]['handle']
    def _web_runtime_observer(self,_selector,*,read_only=True):
        return NativePhoneWebRuntime(self.web.send,self.web.original,self.epoch,self.guard,self.pid,**self.options())
    def _navigation_replies(self,_selector,*,read_only=True):
        state={}
        def send(request):
            state['value']=dict(navigationReplyVersion=1,commandId=request['commandId'],runId=RUN,instance=self.birth,sequence=self.view_sequence+1,
                processId=self.pid,capturedEpochMs=self.epoch(),currentLookupGeneration=2,currentLookupActive=True,events=[] if self.reply is None else [deepcopy(self.reply)])
        return NativeNavigationReplies(send,lambda:json.dumps(state['value']),self.epoch,self.guard,self.pid,**self.options())
    def send(self,key,request):
        assert key=='capture';journal=PrivateFeatureState(self.root/('phone-navigation-'+self.active_role+'-feature.json')).read()
        assert journal is not None and unpack(journal['payload'])[0]['phase']=='reading'
        self.counters[key]+=1;self.storage.present=True;self.paint()
        packet=deepcopy(self.scene.capture);packet.update(requestId=request['commandId'],instance=self.birth,processId=self.pid,sequence=self.counters[key],
            requestedEpochMs=self.epoch(),capturedEpochMs=self.epoch())
        source=packet['source'];source.update(acquisitionSequence=self.counters[key],recordedEpochMs=self.epoch(),startedEpochMs=self.epoch(),capturedEpochMs=self.epoch(),
            sourceExtent=[640,480],sourceViewport=[0,0,640,480],targetExtent=[640,480])
        source['image'].update(name='world-render-image-'+request['commandId']+'.png',bytes=len(self.storage.raw),sha256=hashlib.sha256(self.storage.raw).hexdigest(),
            pixelSha256=self.pixel_sha,width=640,height=480)
        source['renderTrace'].update(frameId=uuid.uuid4().hex,recordedEpochMs=self.epoch(),begunEpochMs=self.epoch(),completedEpochMs=self.epoch(),recordedView=self.avatar()['view'])
        self.values[key]=packet
    def paint(self):
        ticket=self.journal.active(RUN)['ticket'];image=Image.new('RGBA',(640,480),(128,128,128,255))
        image.paste(Image.open(io.BytesIO(marker_bytes(RUN,ticket))).convert('RGBA'),(20,20));draw=ImageDraw.Draw(image)
        for y in range(100,420,16):
            for x in range(200,600,16):draw.rectangle((x,y,x+15,y+15),fill=((240,80,20,255) if self.sdk.position['x'] else (20,180,240,255)) if (x//16+y//16)%2 else (20,20,20,255))
        output=io.BytesIO();image.save(output,format='PNG');self.storage.raw=output.getvalue();self.pixel_sha=hashlib.sha256(image.tobytes()).hexdigest()
    def _world_render_capture(self,selector,*,role='primary',read_only=True,require_trace=False,require_frame_view=True):
        self.active_role=role
        result=super()._world_render_capture(selector,read_only=read_only,role=role,require_frame_view=require_frame_view)
        # Parent fixture's constructor pins PID31; restart has no later image.
        return result
    def _graphics_lifecycle_status(self,_selector,binding):
        return dict(process=dict(running=self.running,identity=self.binding['processIdentity'] if self.running else None))
    def _process_presence(self,_selector,*,read_only=True):
        source=PresenceBoundary(pid=self.pid,epoch_ms=self.epoch);source.presence='absent';source.edit=lambda value:value.update(instance=self.birth)
        return source.reader()
    def invoke(self,_selector,operation,values):
        if operation=='app.stop':self.running=False;return {'stopped':True}
        if operation=='app.launch':
            self.running=True;self.pid=32;self.birth='d'*32;self.binding['processIdentity']='32:20';self.launches+=1;self.activations+=1
            self.sdk.screen=None;self.sdk.address_open=False;self.dialog=False;self.query='';self.bookmarks=json.loads(self.bookmark_path.read_bytes())
            return {'launched':True}
        kind=operation.rsplit('.',1)[1];return getattr(self.flow(),kind)(values)
    def run(self,invoke=None):
        self.actor_enabled=True;reports=[]
        journey=Journey('world-navigation',RUN,URL+'/runs/'+RUN+'/',invoke=invoke or (lambda operation,values:self.invoke('controlled',operation,values)),
            witness=lambda:self.journal.snapshot(RUN),activate=self.activate,read_artifact=lambda name:read_private_artifact(self.root,name),
            image_policy={'screen':POLICY['imagePolicy']},continuity=lambda *_:None,monotonic=lambda:self.sdk.clock,epoch_ms=self.epoch,
            sleep=self.sleep,report=reports.append,navigation_source=lambda:self.provider.snapshot(RUN))
        phases=journey.execute();return phases,reports


class NavigationFeatureTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='phone-navigation-');self.addCleanup(self.tmp.cleanup)
        self.model=Composite(Path(self.tmp.name))
    def registered_adapter(self):
        from test_account_fixture_launch import AccountFixtureLaunchTests
        setup=AccountFixtureLaunchTests();setup.setUp();self.addCleanup(setup.doCleanups);return setup.f
    def configuration(self):
        policy=self.model.root/'navigation-policy.json';access=self.model.root/'adapter-fixture-access.json'
        for path,value in [(policy,POLICY),(access,dict(fixtureAdapterAccessVersion=1,fixtureUrl=URL,adapterToken='d'*64))]:
            store=PrivateFeatureState(path)
            if store.read() is None:store.write(value,None)
        return dict(OVERTE_PHONE_FEATURE_WORLD_NAVIGATION='1',OVERTE_E2E_FEATURE_FIXTURE_URL=URL,
            OVERTE_PHONE_FEATURE_FIXTURE_CONFIG=str(access),OVERTE_PHONE_NAVIGATION_IMAGE_POLICY=str(policy),OVERTE_DEVICE_ARTIFACT_DIR=str(self.model.root))
    def test_registration_is_default_off_and_missing_sources_cannot_advertise(self):
        f=self.registered_adapter();config=self.configuration()
        with patch.dict(os.environ,config|dict(OVERTE_PHONE_FEATURE_WORLD_NAVIGATION='0')),patch.object(f.adapter,'_navigation_feature') as factory:
            self.assertFalse(any(op.startswith('feature.world-navigation.') for op in f.adapter.advertised_capabilities(f.target)))
            with self.assertRaises(ValueError):f.adapter.invoke('test-only-appium','feature.world-navigation.observe',dict(contractVersion=VERSION,runId=RUN,afterSequence=0))
            factory.assert_not_called()
        for edit in [dict(OVERTE_PHONE_FEATURE_WORLD_NAVIGATION='yes'),dict(OVERTE_PHONE_FEATURE_FIXTURE_CONFIG=''),
            dict(OVERTE_DEVICE_ARTIFACT_DIR=''),dict(OVERTE_PHONE_NAVIGATION_IMAGE_POLICY=''),dict(OVERTE_E2E_FEATURE_FIXTURE_URL=URL+'/foreign')]:
            with self.subTest(edit=edit),patch.dict(os.environ,config|edit),self.assertRaises((ValueError,RuntimeError)):
                f.adapter.advertised_capabilities(f.target)
        with patch.dict(os.environ,config):
            self.assertTrue(all('feature.world-navigation.'+kind in f.adapter.advertised_capabilities(f.target) for kind in ('act','observe','cleanup')))
    def test_separate_observer_configuration_and_readonly_grammar(self):
        from appium_adapter import readonly_feature_command
        from script_observer import configuration
        path=self.model.root/'actor-config.json'
        value=dict(featureObserverVersion=3,area='world-navigation',target='controlled',candidateArguments=[],fixtureUrl=URL,actorToken='e'*64,durationSeconds=60)
        store=PrivateFeatureState(path);store.write(value,None);self.assertEqual(value,configuration(path))
        readonly_feature_command(dict(schemaVersion=1,commandId='a'*32,action='phone-navigation-view-observe',runId=RUN))
        with self.assertRaises(ValueError):readonly_feature_command(dict(schemaVersion=1,commandId='a'*32,action='phone-navigation-marker-input',operation='release',runId=RUN,fixtureInstance='a'*32))
    def test_probe_navigation_grammar_runs_closed_against_real_javascript(self):
        source=(ROOT/'tests/device/probe/overte_e2e_probe.js').read_text()
        def function(name):
            start=source.index('    function '+name+'(');end=source.index('\n    }',start)+6;return source[start:end]
        script='\n'.join(function(name) for name in ('objectKeysMatch','phoneFileInteger','validPhoneNavigationRequest'))
        script+='\nconst assert=require("assert");const n="a".repeat(32);const c={schemaVersion:1,commandId:n,action:"activate",instance:n,generation:n,sequence:1,observedElapsedMs:0,controlId:"navigation.bookmark.save",controlToken:n};'
        script+='assert(validPhoneNavigationRequest(c));for(const edit of [{expectedState:{}},{sequence:true},{controlId:"navigation.deleteBookmark.1000"},{action:"submit"},{text:"foreign"}])assert(!validPhoneNavigationRequest({...c,...edit}));'
        script+='assert(validPhoneNavigationRequest({...c,action:"replace",controlId:"navigation.placesSearch",text:"hidden-"+n}));'
        subprocess.run(['node','-e',script],check=True,timeout=10)
    def test_complete_public_v17_journey_and_separate_original_actor(self):
        model=self.model;registered=self.registered_adapter()
        import test_feature_adapters as bound
        with patch.dict(os.environ,self.configuration()),patch.object(registered.adapter,'_navigation_feature',side_effect=lambda *_args,**_kwargs:model.flow()):
            phases,reports=model.run(lambda operation,values:registered.adapter.invoke(bound.SELECTOR,operation,values))
        self.assertEqual(17,len(phases));self.assertTrue(reports[0]['sequenceCompleted']);self.assertFalse(reports[0]['deviceAcceptance'])
        self.assertIsNone(model.actor_error);self.assertEqual({'Unowned':ORIGIN+'/personal'},model.bookmarks)
        self.assertGreater(model.view_sequence,50);self.assertEqual(2,model.launches)
        model.journal.close(RUN);model.provider.retire(RUN);model.sleep(.25)
        self.assertTrue(model.actor_retired);model.flow().finalize();model.flow().finalize()
        self.assertFalse((model.root/'phone-navigation-feature.json').exists());self.assertFalse((model.root/'phone-navigation-actor-feature.json').exists())
        self.assertFalse(list(model.receipt_root.iterdir()));self.assertTrue((model.root/('navigation-retired-'+RUN+'.json')).exists())
    def test_acknowledged_ignored_search_cannot_become_observation(self):
        model=self.model;model.fault='ignore-search'
        with self.assertRaises((NativeUIError,AssertionError)):model.run()
    def test_replayed_original_view_cursor_is_rejected_across_reconstruction(self):
        model=self.model;first=model.flow().observe(dict(contractVersion=VERSION,runId=RUN,afterSequence=0))
        model.fault='view-cursor'
        with self.assertRaises(NativeUIError):model.flow().observe(dict(contractVersion=VERSION,runId=RUN,afterSequence=first['sequence']))
    def test_role_client_is_independent_and_primary_cannot_publish(self):
        model=self.model;flow=model.flow();flow.observe(dict(contractVersion=VERSION,runId=RUN,afterSequence=0))
        with self.assertRaises(NativeUIError):flow.publish()
        actor=model.flow('actor').publish();self.assertEqual(1,actor['sequence'])
        primary=PrivateFeatureState(model.root/'phone-navigation-primary-feature.json').read();secondary=PrivateFeatureState(model.root/'phone-navigation-actor-feature.json').read()
        self.assertNotEqual(unpack(primary['payload'])[0]['frames'][0]['originalId'],unpack(secondary['payload'])[0]['frames'][0]['originalId'])
    def test_changed_original_preferences_preserve_owner_and_prevent_success(self):
        model=self.model;model.flow().observe(dict(contractVersion=VERSION,runId=RUN,afterSequence=0));model.fault='foreign-preferences'
        with self.assertRaises(NativeUIError):model.flow().observe(dict(contractVersion=VERSION,runId=RUN,afterSequence=0))
        self.assertTrue((model.root/'phone-navigation-feature.json').exists())
    def command(self,verb,inputs=None):
        ticket=uuid.uuid4().hex;self.model.activate(ticket,verb,inputs or {})
        return dict(contractVersion=VERSION,runId=RUN,ticket=ticket,fixtureUrl=URL+'/runs/'+RUN+'/',verb=verb,inputs=inputs or {})
    def test_failed_bootstrap_retires_with_new_independent_quiet_samples(self):
        model=self.model;model.flow().prepare() # No public baseline qualified.
        self.assertIsNone(PrivateFeatureState(model.root/'phone-navigation-primary-feature.json').read())
        self.command('cleanup');call=dict(contractVersion=VERSION,runId=RUN)
        model.flow().cleanup(call);model.flow().cleanup(call)
        self.assertEqual([],model.journal.snapshot(RUN)['entries'])
        model.journal.close(RUN);model.provider.retire(RUN);model.actor_enabled=True
        model.flow().finalize();self.assertTrue(model.actor_retired)
        self.assertFalse((model.root/'phone-navigation-feature.json').exists())
    def test_lost_bookmark_save_is_never_replayed_and_cleanup_preserves_foreign(self):
        model=self.model;model.flow().observe(dict(contractVersion=VERSION,runId=RUN,afterSequence=0))
        model.flow().act(self.command('open'));call=self.command('bookmark-add',{'name':context(RUN)['name']})
        model.fault='lost-bookmark-save'
        with self.assertRaises(NativeUIError):model.flow().act(call)
        model.fault=''
        with self.assertRaises(NativeUIError):model.flow().act(call)
        self.assertEqual(1,sum(name=='bookmark.save' for _,name in model.inputs))
        self.command('cleanup');model.flow().cleanup(dict(contractVersion=VERSION,runId=RUN))
        self.assertEqual({'Unowned':ORIGIN+'/personal'},model.bookmarks)
    def test_ignored_cancel_leaves_real_dialog_and_cannot_complete_action(self):
        model=self.model;model.flow().observe(dict(contractVersion=VERSION,runId=RUN,afterSequence=0))
        model.flow().act(self.command('open'));model.fault='ignore-cancel'
        with self.assertRaises(NativeUIError):model.flow().act(self.command('bookmark-add-cancel',{'name':context(RUN)['name']}))
        self.assertTrue(model.dialog);model.fault='';self.command('cleanup')
        model.flow().cleanup(dict(contractVersion=VERSION,runId=RUN));self.assertFalse(model.dialog)
    def test_changed_candidate_or_native_keyboard_cannot_become_clean_baseline(self):
        model=self.model;model.flow().observe(dict(contractVersion=VERSION,runId=RUN,afterSequence=0))
        before=len(model.inputs);model.binding['artifactSha256']='f'*64
        with self.assertRaises(NativeUIError):model.flow().observe(dict(contractVersion=VERSION,runId=RUN,afterSequence=0))
        self.assertEqual(before,len(model.inputs));model.binding['artifactSha256']='2'*64;model.fault='keyboard-visible'
        with self.assertRaises(NativeUIError):model.flow().observe(dict(contractVersion=VERSION,runId=RUN,afterSequence=0))
    def test_same_text_modal_with_foreign_original_404_is_rejected(self):
        model=self.model;model.flow().observe(dict(contractVersion=VERSION,runId=RUN,afterSequence=0))
        call=self.command('navigate-missing')
        model.flow().act(call);model.fault='foreign-modal'
        with self.assertRaises(NativeUIError):model.flow().observe(dict(contractVersion=VERSION,runId=RUN,afterSequence=0))
    def test_owned_partial_png_is_removed_but_foreign_inode_is_preserved(self):
        model=self.model;ticket=model.journal.active(RUN)['ticket']
        from self_tests.test_world_render_evidence import trace_boundary
        packet,raw=trace_boundary(view=True).reader().read(0)
        images=NavigationImages(model.root,model.binding,RUN,'primary',1,model.guard,lambda _:None,monotonic=lambda:model.sdk.clock)
        value=images.value(ticket,packet);path=model.root/value['name']
        path.write_bytes(raw[:80]);path.chmod(0o600);actual=path.stat();value.update(phase='opened',file=dict(device=actual.st_dev,inode=actual.st_ino))
        original=path.with_suffix('.owned');path.rename(original);path.write_bytes(b'foreign');path.chmod(0o600)
        with self.assertRaises(NativeUIError):NavigationImages.retire_partial(model.root,value)
        self.assertEqual(b'foreign',path.read_bytes());path.unlink();original.rename(path)
        NavigationImages.retire_partial(model.root,value);NavigationImages.retire_partial(model.root,value)
        self.assertFalse(path.exists())
    def test_unrecorded_planned_png_cannot_be_adopted(self):
        model=self.model
        from self_tests.test_world_render_evidence import trace_boundary
        packet,_=trace_boundary(view=True).reader().read(0)
        value=NavigationImages(model.root,model.binding,RUN,'primary',1,model.guard,lambda _:None).value(model.journal.active(RUN)['ticket'],packet)
        path=model.root/value['name'];path.write_bytes(b'unknown');path.chmod(0o600)
        with self.assertRaises(NativeUIError):NavigationImages.retire_partial(model.root,value)
        self.assertEqual(b'unknown',path.read_bytes())
    def test_native_packet_cannot_accept_asserted_state_or_boolean_version(self):
        model=self.model;reader=model._navigation_view('controlled');value=reader.read(RUN)
        request=dict(schemaVersion=1,commandId=value['commandId'],action='phone-navigation-view-observe',runId=RUN)
        for change in ({'navigationViewVersion':True},{'expectedState':{}},{'processId':99},{'capturedEpochMs':1000}):
            with self.subTest(change=change),self.assertRaises(NativeUIError):validate_view(value|change,request,model.pid,model.epoch())


if __name__=='__main__':unittest.main()
