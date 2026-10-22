"""Public Avatar composition at explicit synthetic Phone/Qt/GPU seams.

OAuth, social writes, resource responses, PNG decoding, journals and the common
Journey are real host operations. No device, product rendering or APK is used.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from copy import deepcopy
import hashlib
import io
import json
import math
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
import uuid
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import urlencode,urlsplit
from urllib.request import Request

ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT/'tests/device'),str(ROOT/'tests/device/adapters/android-phone')]
from PIL import Image,ImageDraw
from adapters.native_avatar_render import NativeAvatarRender
from adapters.native_feature_observation import NativeFeatureObservation
from adapters.native_graphics_subject import NativeGraphicsSubject
from adapters.native_phone_web_runtime import NativePhoneWebRuntime
from adapters.native_world_model_draws import NativeWorldModelDraws
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUI,NativeUIError
from adapters.token_graphics_ui import TokenGraphicsUI
from adapters.token_login_ui import TokenLoginUI
from adapters.feature_fixture_access import AdapterFixtureClient
from feature_journeys.engine import Journey
from feature_journeys.evidence import read_private_artifact
from feature_journeys.fixtures import marker_bytes,context
from feature_journeys.phase_fixture import PhasePending,PhaseRetired
from feature_journeys.scenarios import VERSION
from feature_journeys.avatar_people_service import REQUEST,DELETE,USERS
from feature_journeys.account_provider import TOKEN_PATH
from feature_journeys.witness import Client
from overte_phone_account_menu import PhoneAccountMenu
from overte_phone_avatar_people_feature import PhoneAvatarPeopleFeature,image_policy
from overte_phone_avatar_people_fixture import AvatarPeopleFixtureReader
from overte_phone_avatar_people_native import PhoneAvatarPeopleObservation,PhoneAvatarPeopleIO,digest
from overte_phone_navigation_marker import NativePhoneNavigationMarker,layout
from overte_phone_script_history import canonical,unpack
from self_tests import test_avatar_people_service as social_tests
from self_tests.test_native_account_observation import account,event,append
from self_tests.test_phone_avatar_people_native import source,loads,SESSION
from self_tests.test_native_feature_observation import Boundary as Lifecycle
from self_tests.test_native_graphics_subject import Boundary as Subject
from self_tests.test_native_phone_web_runtime import Boundary as Web
from self_tests.test_world_render_evidence import frame_view
from self_tests.test_native_avatar_render import avatar_source,model_row
from self_tests.test_token_login_ui import Boundary as Login
from test_graphics_samples import Originals
from test_graphics_surface import Client as SurfaceClient,Qt

PEER='77777777-7777-4777-8777-777777777777'
DOMAIN=social_tests.DOMAIN
POLICY=dict(imageExtent=[640,480],markerRoi=[10,10,170,50],
    imagePolicy=dict(source='world-render-target',marker=[14,14,142,46],subject=[200,32,440,448]))


class SDK(SurfaceClient):
    def __init__(self,phone):super().__init__();self.phone=phone;self.mode='look at'
    def rows(self):
        if self.panel=='menu':return [('nav.close',''),('nav.home',''),('','View'),('','File')]
        if self.panel=='file':return [('nav.close',''),('nav.home',''),('','Directory Service: Logout '+self.phone.principal)] if self.phone.auth['loggedIn'] else [('nav.close',''),('nav.home','')]
        return super().rows()
    def call(self,method,path,body=None):
        if method=='DELETE' and path.endswith('/actions'):return None
        if '/element/' in path and path.endswith('/click'):
            ref=path.split('/element/',1)[1].split('/')[0];resource,label=self.refs[ref]
            if label=='File':self.inputs.append((resource,label));self.panel='file';return
            if label.startswith('Directory Service: Logout '):
                self.inputs.append((resource,label));self.phone.logout();return
        return super().call(method,path,body)


class LoginBoundary(Login):
    def __init__(self,phone):
        super().__init__();self.phone=phone;self.server=phone.lab.origin;self.endpoint=digest(self.server)
        self.instance=phone.birth;self.generation=phone.birth;self.account=phone.auth['observation']['instance']
    def capture(self):
        self.token=self.phone.auth['observation']['tokenPresent'];self.pending=False;self.waiting=False
        return super().capture()
    def input(self,identifier,action,*,token,text=None):
        original=next(row for row in self.capture()['controls'] if row['id']==identifier)
        assert original['token']==token and original['inputReady']
        self.inputs.append((identifier,action))
        if action=='activate':
            if identifier=='login.entry':self.dialog=True
            elif identifier=='login.cancel':self.dialog=False;self.fields={};self.focused=None
            else:self.focused=identifier
        elif action=='replace':self.fields[identifier]=text
        elif action=='submit':self.phone.login(self.fields)


class Phone(Originals):
    def __init__(self,lab,root,role):
        super().__init__(root);self.lab,self.role=lab,role;self.pid=31;self.birth=('f' if role=='primary' else 'e')*32
        self.binding.update(sourceRevision='1'*40,artifactSha256='2'*64,processIdentity='31:19',sessionId=role+'-session',targetFingerprint=('3' if role=='primary' else '4')*64)
        self.sdk=SDK(self);self.ui=NativeUI(self.sdk,role+'-session',self.guard,timeout=.6,**self.options())
        self.state=source();self.state['domainId']=DOMAIN;self.state['accountOrigin']=lab.origin
        self.state['avatar'].update(sessionId=SESSION if role=='primary' else PEER,modelInstance=('c' if role=='primary' else '8')*32,feetPosition=[0,0,-3])
        self.state['avatar']['geometry'].update(instance=('d' if role=='primary' else '9')*32)
        for key in ('advertisedLoads','modelLoads'):self.state['avatar'][key]=loads('qrc:/original.fst',instance=('1' if key=='advertisedLoads' else '2')*32)
        self.state['avatar']['requestedUrl']='qrc:/original.fst';self.state['avatar']['geometry'].update(url='qrc:/original.fbx',textures={'original':'qrc:/original.png'})
        self.state['preferredAvatarUrl']='qrc:/original.fst'
        for pref in self.state['view']['preferences'].values():pref.update(present=True,value=0)
        self.auth=account();self.auth['observation'].update(instance=('a' if role=='primary' else 'b')*32,endpointSha256=digest(lab.origin))
        self.state['auth']=self.auth;self.bookmarks={};self.bookmark_path=root/'avatar-bookmarks.json';self.persist()
        self.serial={};self.dialog=None;self.dialog_text='';self.focus=False;self.managing=False;self.scale_draft=1;self.tab='nearbyTab'
        self.consent=dict(phase='idle');self.connections=[];self.selected=None;self.marker=None;self.web_known=[]
        self.web=Web();self.web.now=self.epoch;self.web.edit=self.web_edit;self.login_boundary=LoginBoundary(self)
        self.storage.mutate=lambda p:p.update(instance=self.birth,processId=self.pid,capturedEpochMs=self.epoch())
        self.inventory.mutate=lambda p:p.update(instance=self.birth,processId=self.pid,capturedEpochMs=self.epoch())
    def options(self):return dict(monotonic=lambda:self.lab.clock,sleep=self.lab.sleep)
    def epoch(self):return self.lab.epoch()
    def guard(self):return self.lab.fault!='lost-process'
    def tick(self,key):self.lab.clock+=.001;self.serial[key]=self.serial.get(key,0)+1;return self.serial[key]
    @property
    def principal(self):return self.lab.social.credentials(self.lab.run,self.role if self.role=='primary' else 'peer')['username']
    def persist(self):self.bookmark_path.write_bytes(canonical(self.bookmarks));self.bookmark_path.chmod(0o600)
    def login(self,fields):
        status,raw,_=self.lab.http(TOKEN_PATH,dict(grant_type='password',scope='owner',username=fields['login.username'],password=fields['login.password']),form=True)
        assert status==200;self.access=json.loads(raw)['access_token']
        status,raw,_=self.lab.http('/api/v1/user/profile',token=self.access);assert status==200
        # The actual protected profile response supplies the principal.
        profile=json.loads(raw);username=profile['data']['user']['username']
        self.auth.update(loggedIn=True,principalSha256=digest(username));self.auth['observation'].update(tokenPresent=True,tokenValid=True,refreshPresent=True)
        row=event(1,'profile-reply',self.epoch(),status=200);row['networkError']=0;append(self.auth,row)
    def logout(self):
        self.auth.update(loggedIn=False,principalSha256=digest(''));self.auth['observation'].update(tokenPresent=False,tokenValid=False,refreshPresent=False)
    def original(self):
        state=deepcopy(self.state);state['auth']=deepcopy(self.auth);state['auth']['observation']['capturedEpochMs']=self.epoch()
        panel=self.sdk.panel;view=state['view'];view['tabletShown']=panel is not None
        view['avatar']=dict(present=panel=='avatar',dialogs=[])
        view['people']=dict(present=panel=='people',dialog=panel=='people' and self.consent['phase']!='idle');view['models']={}
        if panel=='avatar':
            view['avatar'].update(current=dict(name='',avatarUrl=state['avatar']['requestedUrl'],avatarScale=state['avatar']['scale']),settings={},managing=self.managing)
            if self.dialog:view['avatar']['dialogs']=[dict(title=self.dialog,source='AvatarApp.qml')]
            rows=[dict(name=k,**v) for k,v in self.bookmarks.items()]
            for key in ('allAvatars','pageOfAvatars'):view['models'][key]=dict(complete=True,count=len(rows),rows=rows)
        if panel=='people':
            view['people'].update(consent=deepcopy(self.consent),nearby=[dict(sessionId=self.lab.other(self).state['avatar']['sessionId'])],self={},tab=self.tab)
            for key,rows in (('connectionsUserModel',self.connections),('nearbyUserModel',[dict(sessionId=self.lab.other(self).state['avatar']['sessionId'])])):
                view['models'][key]=dict(complete=True,count=len(rows),rows=deepcopy(rows))
        raw=self.bookmark_path.read_bytes();state['bookmarks']=dict(present=True,sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),bookmarks=json.loads(raw))
        state['peers']=[deepcopy(self.lab.other(self).state['avatar'])]
        state['peers'][0]['modelInstance']=('5' if self.role=='primary' else '6')*32
        state['peers'][0]['geometry']['instance']=('7' if self.role=='primary' else '0')*32
        for model in (state['avatar'],*state['peers']):
            for key in ('advertisedLoads','modelLoads'):model[key].update(sequence=self.serial['source'],capturedEpochMs=self.epoch())
        for key in ('resourceReplies','peopleReplies','avatarEntityOrigins'):
            state[key].update(sequence=self.serial['source'],capturedEpochMs=self.epoch())
        for row in state['avatarEntities']['entities']:
            row['model']['modelLoads'].update(sequence=self.serial['source'],capturedEpochMs=self.epoch())
        state['resourceReplies']['runId']=self.lab.run;state['avatarEntityOrigins']['runId']=self.lab.run
        return state
    def source_reader(self):
        packet={}
        def send(request):
            sequence=self.tick('source');packet['value']=dict(avatarPeopleObservationVersion=1,commandId=request['commandId'],runId=self.lab.run,
                instance=self.birth,sequence=sequence,processId=31,requestedEpochMs=self.epoch(),capturedEpochMs=self.epoch(),source=self.original())
        return PhoneAvatarPeopleObservation(send,lambda:json.dumps(packet['value']),self.epoch,self.guard,31,**self.options())
    def viewer(self):
        source=avatar_source();model=self.state['avatar'];source.update(modelInstance=model['modelInstance'],cameraMode=self.sdk.mode)
        source['geometry'].update(instance=model['geometry']['instance'],sourceSha256=digest(model['geometry']['url']))
        source['pose']=dict(feetPosition=model['feetPosition'],orientation=model['orientation'],modelScale=model['scale'])
        source['view']=frame_view();source['view']['position']=[0,.9,0];return source
    def viewer_reader(self):
        packet={}
        def send(request):
            seq=self.tick('viewer');packet['value']=dict(schemaVersion=1,requestId=request['commandId'],instance=self.birth,sequence=seq,processId=31,
                requestedEpochMs=self.epoch(),capturedEpochMs=self.epoch(),source=self.viewer())
        return NativeAvatarRender(send,lambda:json.dumps(packet['value']),self.epoch,self.guard,31,**self.options())
    def lifecycle(self):
        boundary=Lifecycle()
        def send(request):
            boundary.send(request);seq=self.tick('lifecycle');value=boundary.sample
            value.update(instance=self.birth,sequence=seq,processId=31,requestedEpochMs=self.epoch(),capturedEpochMs=self.epoch(),account=deepcopy(self.auth))
            value['account']['observation']['capturedEpochMs']=self.epoch();value['animationFence'].update(sequence=seq+9,requestedEpochMs=self.epoch())
            value['animation'].update(capturedEpochMs=self.epoch());value['animation']['clip'].update(evaluatedEpochMs=self.epoch())
        return NativeFeatureObservation(send,boundary.original,self.epoch,self.guard,31,**self.options())
    def rows(self):
        panel=self.sdk.panel;ids=['avatar.entry','people.entry'] if panel=='home' else ['avatar.page','avatar.url','avatar.settings','avatar.wearables','avatar.bookmark.add','avatar.bookmark.manage'] if panel=='avatar' else ['people.page','people.nearby','people.connections'] if panel=='people' else []
        rows=[dict(id=id,enabled=True,focused=False,inputReady=not id.endswith('.page')) for id in ids]
        if panel=='avatar' and self.dialog:
            rows=[r for r in rows if r['id']=='avatar.page']+[dict(id='avatar.dialog.'+id,enabled=True,focused=self.focus and id=='input',inputReady=True,**({'text':self.dialog_text} if id=='input' else {})) for id in ('input','confirm','cancel')]
            if self.dialog=='settings':rows.append(dict(id='avatar.scale',enabled=True,focused=False,inputReady=True,value=self.scale_draft*10,**{'from':1,'to':40,'stepSize':1}))
            if self.dialog=='wearables':
                rows.append(dict(id='avatar.wearable.add',enabled=True,focused=False,inputReady=True))
                if self.lab.worn:
                    actual=self.state['avatarEntities']['entities'][0]
                    rows.append(dict(id='avatar.wearable.remove',enabled=True,focused=False,inputReady=True,wearableId=actual['entityId'],wearableUrlSha256=digest(actual['modelUrl'])))
        elif panel=='avatar':
            for i,(name,record) in enumerate(self.bookmarks.items()):rows.append(dict(id='avatar.bookmark.row.'+str(i),enabled=True,focused=False,inputReady=True,bookmarkName=name))
        if panel=='people':
            if self.consent['phase']!='idle':
                buttons=['ConnectionCancel']+(['ConnectionAccept','ConnectionDecline'] if self.consent['phase']=='incoming' else [])
                rows += [dict(id='people.'+id,enabled=True,focused=False,inputReady=True) for id in buttons]
            else:
                other=self.lab.other(self);username=other.principal
                if self.tab=='nearbyTab':rows += [dict(id='people.row.0',enabled=True,focused=False,inputReady=True,peerSession=other.state['avatar']['sessionId']),dict(id='people.RequestConnection',enabled=True,focused=False,inputReady=True)]
                elif self.connections:rows += [dict(id='people.row.0',enabled=True,focused=False,inputReady=True,userName=username),dict(id='people.remove.'+username,enabled=True,focused=False,inputReady=True,userName=username)]
        for row in rows:row['token']=hashlib.sha256(canonical(row)).hexdigest()[:32]
        return rows
    def controls(self):
        packet={}
        def send(outer):
            request=outer['request'];seq=self.tick('ui')
            if request['action']=='observe':packet['value']=dict(schemaVersion=1,commandId=request['commandId'],action='observe',instance=self.birth,generation=self.birth,
                sourceSequence=seq,lastCommandSequence=self.serial.get('input',0),elapsedMs=round(self.lab.clock*1000),capturedEpochMs=self.epoch(),processId=31,avatarPeopleControlsVersion=1,ready=True,controls=self.rows());return
            row=next(r for r in self.rows() if r['id']==request['controlId']);assert row['token']==request['controlToken']
            self.tick('input');self.input(request)
            packet['value']=dict(schemaVersion=1,commandId=request['commandId'],action=request['action'],performed=True,instance=self.birth,generation=self.birth,sequence=self.serial['input'],processId=31)
        return PhoneAvatarPeopleIO(send,lambda:json.dumps(packet['value']),self.epoch,self.guard,31,**self.options())
    def input(self,request):
        id=request['controlId'];action=request['action'];self.lab.inputs.append((self.role,id,action))
        if action=='replace':self.dialog_text=request['text'];return
        if action=='set-value':self.scale_draft=request['value']/10;return
        if id in ('avatar.entry','people.entry'):self.sdk.panel=id.split('.')[0];return
        if id=='avatar.url':self.dialog='url';self.dialog_text='';return
        if id=='avatar.settings':self.dialog='settings';self.scale_draft=self.state['avatar']['scale'];return
        if id=='avatar.wearables':self.dialog='wearables';return
        if id=='avatar.wearable.add':self.dialog='wearable';self.dialog_text='';return
        if id=='avatar.wearable.remove':self.lab.remove_wearable();return
        if id=='avatar.bookmark.add':self.dialog='bookmark';self.dialog_text='';return
        if id=='avatar.bookmark.manage':self.managing=not self.managing;return
        if id=='avatar.dialog.input':self.focus=True;return
        if id=='avatar.dialog.cancel':self.dialog=None;self.focus=False;return
        if id=='avatar.dialog.confirm':
            dialog=self.dialog;self.dialog=None;self.focus=False
            if dialog=='url':self.load_model(self.dialog_text)
            elif dialog=='settings':
                if self.lab.fault!='ignore-scale':self.state['avatar'].update(scale=self.scale_draft,targetScale=self.scale_draft)
            elif dialog=='bookmark':self.bookmarks[self.dialog_text]=dict(version=3,avatarUrl=self.state['avatar']['requestedUrl'],avatarScale=self.state['avatar']['scale'],avatarEntites=[]);self.persist()
            elif dialog=='wearable':self.lab.add_wearable(self,self.dialog_text);self.dialog='wearables'
            elif dialog=='delete':self.bookmarks.pop(self.delete_name);self.persist()
            return
        if id.startswith('avatar.bookmark.row.'):
            name=list(self.bookmarks)[int(id.rsplit('.',1)[1])]
            if self.managing:self.dialog='delete';self.delete_name=name
            else:self.load_model(self.bookmarks[name]['avatarUrl']);scale=self.bookmarks[name]['avatarScale'];self.state['avatar'].update(scale=scale,targetScale=scale);self.lab.remove_wearable()
            return
        if id=='people.nearby':self.tab='nearbyTab';return
        if id=='people.connections':self.tab='connectionsTab';self.refresh_connections();return
        if id.startswith('people.row.'):self.selected=self.lab.other(self);return
        if id=='people.RequestConnection':
            peer=self.selected;request_id=uuid.uuid4().hex
            self.consent=dict(phase='outgoing',requestId=request_id,peer=peer.state['avatar']['sessionId'])
            peer.consent=dict(phase='incoming',requestId=request_id,peer=self.state['avatar']['sessionId']);return
        if id=='people.ConnectionCancel':
            if self.consent['phase'] in ('outgoing','incoming'):self.lab.other(self).consent['phase']='cancelled'
            self.consent=dict(phase='idle');return
        if id=='people.ConnectionDecline':self.consent['phase']='declined';self.lab.other(self).consent['phase']='declined';return
        if id=='people.ConnectionAccept':self.lab.connect();return
        if id.startswith('people.remove.'):
            self.social(DELETE+id.removeprefix('people.remove.'),method='DELETE');self.refresh_connections();return
        raise AssertionError('Unexpected synthetic ordinary Avatar input '+id)
    def resource(self,url):
        status,raw,response=self.lab.http(urlsplit(url).path)
        pieces=urlsplit(url).path.split('/tickets/')[1].split('/',1)
        rows=self.state['resourceReplies']['events'];rows.append(dict(sequence=len(rows)+1,runId=self.lab.run,ticket=pieces[0],resource=pieces[1],
            requestedUrlSha256=digest(url),replyUrlSha256=digest(url),responseId=response,httpStatus=status,networkError=0 if status==200 else 203,
            fromCache=False,redirected=False,capturedEpochMs=self.epoch(),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()))
    def load_model(self,url):
        model=self.state['avatar'];generation=model['advertisedLoads']['currentGeneration']+1;history=model['advertisedLoads']['events']
        history.append(dict(eventSequence=len(history)+1,generation=generation,kind='requested',capturedEpochMs=self.epoch(),requestedSha256=digest(url),resourceSha256='',success=None))
        missing=url.endswith('/missing.fst')
        history.append(dict(eventSequence=len(history)+1,generation=generation,kind='finished',capturedEpochMs=self.epoch(),requestedSha256=digest(url),resourceSha256=digest(url),success=not missing))
        model['advertisedLoads'].update(currentGeneration=generation,requestedSha256=digest(url));model['requestedUrl']=url
        if url.startswith('https:'):
            for phone in self.lab.phones.values():phone.resource(url)
        geometry='qrc:/original.fbx' if url.startswith('qrc:') or missing else url.rsplit('/',1)[0]+'/mannequin/mannequin.fbx'
        textures={'original':'qrc:/original.png'} if geometry.startswith('qrc:') else {'eyes':url.rsplit('/',1)[0]+'/mannequin/Eyes.png'}
        model['geometry'].update(url=geometry,textures=textures)
        if geometry.startswith('https:'):
            for phone in self.lab.phones.values():
                for resource in (geometry,*textures.values()):phone.resource(resource)
        if not missing:self.state['preferredAvatarUrl']=url
    def social(self,path,body=None,method=None):
        status,raw,response=self.lab.http(path,body,method=method,token=self.access);assert status==200
        rows=self.state['peopleReplies']['events'];rows.append(dict(eventSequence=len(rows)+1,responseId=response,method=method or ('GET' if body is None else 'POST'),
            requestedUrlSha256=digest(self.lab.origin+path),replyUrlSha256=digest(self.lab.origin+path),requestBodySha256=hashlib.sha256(b'' if body is None else json.dumps(body).encode()).hexdigest(),
            httpStatus=status,networkError=0,fromCache=False,redirected=False,capturedEpochMs=self.epoch(),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()))
        return json.loads(raw)
    def refresh_connections(self):
        value=self.social(USERS[1]+'?page=1&per_page=1000')
        self.connections=[dict(userName=row['username'],connection='connection') for row in value['data']['users']]
    def marker_input(self,request):
        if request['operation']=='prepare':
            view=deepcopy(self.viewer()['view'])|dict(mode=self.sdk.mode,feetPosition=[0,0,-3],modelScale=1,boomLength=2)
            original={key:deepcopy(view[key]) for key in ('mode','position','rotation','projection')};held=deepcopy(original);held['mode']='independent';self.sdk.mode='independent'
            self.marker=dict(phoneNavigationMarkerVersion=1,fixtureInstance=uuid.uuid4().hex,runId=self.lab.run,phase='active',createdEpochMs=self.epoch(),originalInput=deepcopy(request),originalView=view,
                objects=[dict(role='marker',id=str(uuid.uuid4()))],entities=[],absentIds=[],retainedObjects=1,
                cameraLease=dict(measuredCameraLeaseVersion=1,instance=uuid.uuid4().hex,phase='held',originalObject=True,originalView=original,heldView=held,currentView=deepcopy(held),foreignModeChanges=0,restoration=None))
            geometry=layout(self.marker)['marker'];url=request['fixtureUrl']+'tickets/'+request['ticket']+'/graphics-marker.v1.html'
            self.marker['entities']=[geometry|dict(id=self.marker['objects'][0]['id'],role='marker',originalObject=True,name='e2e-'+self.lab.run+'-navigation-marker',type='Web',parentId='00000000-0000-0000-0000-000000000000',hostType='local',color=[255,255,255],visible=True,sourceUrl=url,locked=False,collisionless=True,canCastShadow=False,dpi=100,lastEditedEpochUs=self.epoch()*1000)]
            self.web_known=[dict(handle='1',firstObservedEpochMs=self.epoch(),sourceSha256=digest(url))];self.web.revoked=False
        else:
            self.marker.update(phase='drained',entities=[],absentIds=[row['id'] for row in self.marker['objects']],retainedObjects=0);self.web.revoked=True
            lease=self.marker['cameraLease'];self.sdk.mode=lease['originalView']['mode'];lease.update(phase='restored',currentView=deepcopy(lease['originalView']),
                restoration=dict(capturedEpochMs=self.epoch(),originalObject=True,view=deepcopy(lease['originalView'])))
        return dict(phoneNavigationMarkerInputVersion=1,commandId=request['commandId'],runId=self.lab.run,fixtureInstance=self.marker['fixtureInstance'],operation=request['operation'],recorded=True)
    def marker_reader(self):
        packet={}
        def send(request):
            seq=self.tick('marker');packet['value']=dict(schemaVersion=1,requestId=request['commandId'],instance=self.birth,sequence=seq,processId=31,requestedEpochMs=self.epoch(),capturedEpochMs=self.epoch(),source=deepcopy(self.marker))
        return NativePhoneNavigationMarker(send,lambda:json.dumps(packet['value']),self.epoch,self.guard,31,**self.options())
    def web_edit(self,value):
        from test_navigation_feature import Composite
        # Reuse the independently validated original native/Java web producer.
        self.web_known[0]['sourceSha256']=digest(self.marker['entities'][0]['sourceUrl']) if self.marker['entities'] else self.web_known[0]['sourceSha256']
        old_run=__import__('test_navigation_feature').RUN
        import test_navigation_feature
        test_navigation_feature.RUN=self.lab.run
        try:Composite.web_edit(self,value)
        finally:test_navigation_feature.RUN=old_run
    def send(self,key,request):
        assert key=='capture';seq=self.tick('capture');self.storage.present=True
        source=deepcopy(self.scene.capture);source.update(requestId=request['commandId'],instance=self.birth,processId=31,sequence=seq,requestedEpochMs=self.epoch(),capturedEpochMs=self.epoch())
        actual=source['source'];actual.update(acquisitionSequence=seq,recordedEpochMs=self.epoch(),startedEpochMs=self.epoch(),capturedEpochMs=self.epoch(),sourceExtent=[640,480],sourceViewport=[0,0,640,480],targetExtent=[640,480])
        actual['renderTrace'].update(frameId=uuid.uuid4().hex,recordedEpochMs=self.epoch(),begunEpochMs=self.epoch(),completedEpochMs=self.epoch(),recordedView=self.viewer()['view'])
        subject=self.lab.phones['primary'].state['avatar'];scale=subject['scale'];width=int(100*scale);height=int(180*scale)
        image=Image.new('RGBA',(640,480),(35,40,45,255));draw=ImageDraw.Draw(image)
        for y in range(240-height//2,240+height//2,10):
            for x in range(320-width//2,320+width//2,10):draw.rectangle((x,y,x+9,y+9),fill=(190,200,205,255) if (x//10+y//10)%2 else (90,100,120,255))
        if self.lab.worn:draw.rectangle((320,160,389,279),fill=(240,70,30,255))
        image.paste(Image.open(io.BytesIO(marker_bytes(self.lab.run,self.lab.client.observe()['ticket']))),(10,10))
        raw=io.BytesIO();image.save(raw,format='PNG');self.storage.raw=raw.getvalue()
        actual['image'].update(name='world-render-image-'+request['commandId']+'.png',bytes=len(self.storage.raw),sha256=hashlib.sha256(self.storage.raw).hexdigest(),pixelSha256=hashlib.sha256(image.tobytes()).hexdigest(),width=640,height=480)
        self.values[key]=source
    def _world_render_capture(self,selector,*,role,read_only,require_trace=False,require_frame_view=True):
        return super()._world_render_capture(selector,role=role,read_only=read_only,require_frame_view=require_frame_view)
    def draws_reader(self):
        packet={}
        def send(request):
            seq=self.tick('draws');capture=self.values['capture'];source=capture['source'];subject=self.lab.phones['primary'].state['avatar'];scale=subject['scale']
            model=subject if self.role=='primary' else self.original()['peers'][0]
            row=model_row()|dict(modelInstance=model['modelInstance'],geometryInstance=model['geometry']['instance'],loadedSourceSha256=digest(model['geometry']['url']),minimum=[-.5*scale,.9-.9*scale,-3.2],maximum=[.5*scale,.9+.9*scale,-2.8])
            rows=[row]
            if self.lab.worn:
                worn=self.state['avatarEntities']['entities'][0]['model'];rows.append(row|dict(modelInstance=worn['modelInstance'],geometryInstance=worn['geometry']['instance'],loadedSourceSha256=digest(worn['geometry']['url']),skinnedDrawCommands=0))
            trace=dict(modelTraceVersion=1,frameId=source['renderTrace']['frameId'],recordedEpochMs=source['recordedEpochMs'],begunEpochMs=source['recordedEpochMs'],completedEpochMs=source['recordedEpochMs'],renderer='forward',view='main-mono',drawCommands=sum(row['drawCommands'] for row in rows),models=rows)
            packet['value']=dict(schemaVersion=1,requestId=request['commandId'],instance=self.birth,sequence=seq,processId=31,requestedEpochMs=self.epoch(),capturedEpochMs=self.epoch(),source=dict(modelCaptureVersion=1,captureRequestId=capture['requestId'],captureSequence=capture['sequence'],acquisitionSequence=source['acquisitionSequence'],captureCapturedEpochMs=source['capturedEpochMs'],imageSha256=source['image']['sha256'],pixelSha256=source['image']['pixelSha256'],modelTrace=trace))
        return NativeWorldModelDraws(send,lambda:json.dumps(packet['value']),self.epoch,self.guard,31,**self.options())


class Composite:
    def __init__(self,lab,root):
        self.lab,self.root=lab,root;self.clock=0.;self.fault='';self.inputs=[];self.worn=False;self.actor_busy=False;self.actor_enabled=False
        self.run=lab.run;self.origin=lab.origin;self.social=lab.social;self.client=lab.client;self.http=lab.http
        self.reader=AdapterFixtureClient(self.client.url,lab.adapter)
        self.base=math.ceil(lab.server.journal.runs[self.run]['phaseCreatedEpochMs'])+100
        self.phones={}
        self.input_pin=None
        for role in ('primary','actor'):
            directory=root/role;directory.mkdir(mode=0o700);self.phones[role]=Phone(self,directory,role)
        self.actor=Client(self.client.url,lab.actor);self.actor_flow=None
        lab.server.journal.clock=self.epoch;lab.provider.epoch_ms=self.epoch
    def epoch(self):return self.base+round(self.clock*1000)
    def other(self,phone):return self.phones['actor' if phone.role=='primary' else 'primary']
    def sleep(self,seconds):
        self.clock+=seconds
        if self.actor_enabled and not self.actor_busy and self.phones['primary'].root.joinpath('phone-avatar-people-feature.json').exists():
            import fcntl
            fd=os.open(self.phones['primary'].root/'phone-script-sources.lock',os.O_RDWR|os.O_CREAT,0o600)
            try:
                try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
                except BlockingIOError:return
                fcntl.flock(fd,fcntl.LOCK_UN)
            finally:os.close(fd)
            self.actor_busy=True
            try:
                if self.actor_flow is None:self.actor_flow=self.flow('actor')
                self.actor_flow.publish()
            except PhasePending:pass
            finally:self.actor_busy=False
    def phone(self,selector):return self.phones[selector]
    def state_path(self,selector):return self.phone(selector).root/'session.json'
    @contextmanager
    def existing_input_session(self,selector):
        assert self.input_pin in (None,selector)
        previous=self.input_pin;self.input_pin=selector
        try:yield
        finally:self.input_pin=previous
    def normal_feature_runtime(self,selector,*,read_only):
        assert self.input_pin in (None,selector)
        p=self.phone(selector);return p.ui,None,deepcopy(p.binding),p.guard,None
    def _avatar_people_source(self,s,**kwargs):return self.phone(s).source_reader()
    def _avatar_people_controls(self,s,**kwargs):assert self.input_pin==s;return self.phone(s).controls()
    def _avatar_render_observer(self,s,**kwargs):return self.phone(s).viewer_reader()
    def _native_feature_observer(self,s,**kwargs):return self.phone(s).lifecycle()
    def _navigation_marker_input(self,s,request):assert self.input_pin==s;return self.phone(s).marker_input(request)
    def _navigation_marker(self,s,**kwargs):return self.phone(s).marker_reader()
    def _web_runtime_observer(self,s,**kwargs):
        p=self.phone(s);return NativePhoneWebRuntime(p.web.send,p.web.original,p.epoch,p.guard,31,**p.options())
    def _world_render_capture(self,s,**kwargs):return self.phone(s)._world_render_capture(s,**kwargs)
    def _world_model_draws_observer(self,s,**kwargs):return self.phone(s).draws_reader()
    def world_render_store(self,s,*,role):return PrivateFeatureState(self.phone(s).root/('world-'+role+'.json'))
    def _graphics_controls(self,s,intent):
        assert self.input_pin==s
        p=self.phone(s);return TokenGraphicsUI(Qt(p.sdk),intent,**p.options())
    def _graphics_subject_observer(self,s,**kwargs):
        p=self.phone(s);boundary=Subject()
        def send(request):
            from feature_journeys.graphics_fixture import subject_ids
            boundary.source['absentIds']=list(subject_ids(request['runId']).values())
            boundary.epoch=self.epoch();boundary.send(request);boundary.sample.update(instance=p.birth)
            boundary.sample['source'].update(subjectVersion=2,avatarPose=p.viewer()['pose']);boundary.sample['source']['view'].update(mode=p.sdk.mode)
        return NativeGraphicsSubject(send,boundary.original,self.epoch,p.guard,31,**p.options())
    def _login_controls(self,s,intent,run,origin):assert self.input_pin==s;return TokenLoginUI(self.phone(s).login_boundary,intent,run,origin,monotonic=lambda:self.clock,sleep=self.sleep)
    def _account_menu(self,s,intent,run,origin):assert self.input_pin==s;return PhoneAccountMenu(self.phone(s).ui,self.phone(s).lifecycle(),intent,run,origin)
    def flow(self,role='primary'):
        source=AvatarPeopleFixtureReader(self.reader if role=='primary' else self.actor,self.run,epoch_ms=self.epoch,monotonic=lambda:self.clock)
        return PhoneAvatarPeopleFeature(self,'primary',source,self.root,POLICY,role=role,peer_selector='actor' if role=='actor' else None,
            peer_policy=POLICY if role=='actor' else None,monotonic=lambda:self.clock,sleep=self.sleep)
    def connect(self):
        primary,peer=self.phones.values()
        for phone,other in ((primary,peer),(peer,primary)):
            phone.social(REQUEST,dict(user_connection_request=dict(node_id=phone.state['avatar']['sessionId'],proposed_node_id=other.state['avatar']['sessionId'])))
        primary.social(REQUEST+'?'+urlencode(dict(node_id=SESSION,proposed_node_id=PEER)))
        for phone in self.phones.values():phone.consent['phase']='success'
    def add_wearable(self,phone,url):
        id=str(uuid.uuid4());now=self.epoch();self.worn=True
        phone.state['avatarEntityOrigins']['events'].append(dict(eventSequence=1,capturedEpochMs=now,runId=self.run,ticket=url.split('/tickets/')[1].split('/')[0],entityId=id,parentId=SESSION,parentJointIndex=17,treePresent=True,modelUrlSha256=digest(url)))
        for phone in self.phones.values():
            for resource in (url,url.rsplit('/',1)[0]+'/mesh/triangle.bin',url.rsplit('/',1)[0]+'/textures/checker.png'):phone.resource(resource)
            model=dict(modelInstance=('a1' if phone.role=='primary' else 'a2')*16,modelLoads=loads(url,instance='b1'*16),loaded=True,visible=True,addedToScene=True,geometry=dict(instance='b2'*16,url=url,texturesLoaded=True,textures={'checker':url.rsplit('/',1)[0]+'/textures/checker.png'}))
            row=dict(entityId=id,type='Model',host='avatar',parentId=SESSION,parentJointIndex=17,modelUrl=url,visible=True,originalObject=True,localPosition=[0,0,0],localRotation=[0,0,0,1],localDimensions=[1,1,1],model=model)
            phone.state['avatarEntities']=dict(complete=True,entities=[row],absentIds=[],advertisedIds=[id],queriedIds=[id],rememberedIds=[id],retainedIds=[id])
    def remove_wearable(self):
        self.worn=False
        for phone in self.phones.values():
            actual=phone.state['avatarEntities'];actual.update(entities=[],advertisedIds=[],retainedIds=[],absentIds=deepcopy(actual['rememberedIds']))
    def run_journey(self,invoke=None):
        self.actor_enabled=True;reports=[]
        journey=Journey('avatar-people',self.run,self.client.url+'/runs/'+self.run+'/',invoke=invoke or (lambda operation,values:getattr(self.flow(),operation.rsplit('.',1)[1])(values)),
            witness=self.client.observe,activate=self.client.activate,read_artifact=lambda name:read_private_artifact(self.root,name),image_policy={'screen':POLICY['imagePolicy']},
            continuity=lambda *_:None,monotonic=lambda:self.clock,epoch_ms=self.epoch,sleep=self.sleep,report=reports.append)
        return journey.execute(),reports


class AvatarPeopleFeatureTests(unittest.TestCase):
    setUpClass=classmethod(social_tests.AvatarPeopleServiceTests.setUpClass.__func__)
    tearDownClass=classmethod(social_tests.AvatarPeopleServiceTests.tearDownClass.__func__)
    stop=social_tests.AvatarPeopleServiceTests.stop
    def setUp(self):
        social_tests.AvatarPeopleServiceTests.setUp(self);temporary=tempfile.TemporaryDirectory(prefix='phone-avatar-composition-');self.addCleanup(temporary.cleanup)
        self.model=Composite(self,Path(temporary.name));self.provider.epoch_ms=self.model.epoch
        environment=patch.dict(os.environ,OVERTE_DEVICE_ADAPTER_MANIFEST=str(ROOT/'tests/device/adapters/mock/adapter.json'),
            OVERTE_DEVICE_TARGET_SELECTOR='synthetic-host-only',OVERTE_DEVICE_ARTIFACT_DIR=str(self.model.root))
        environment.start();self.addCleanup(environment.stop)
    def http(self,path,body=None,method=None,token=None,form=False):
        raw=None if body is None else urlencode(body).encode() if form else json.dumps(body).encode()
        headers={'Content-Type':'application/x-www-form-urlencoded' if form else 'application/json'}
        if token:headers['Authorization']='Bearer '+token
        request=Request(self.origin+path,data=raw,method=method,headers=headers)
        try:response=self.opener.open(request,timeout=3)
        except HTTPError as error:response=error
        with response:return response.status,response.read(),response.headers.get('X-Overte-Fixture-Response')
    def test_complete_public_common_journey_and_durable_authority_retirement(self):
        self.foundation()
        registered=self.registered_adapter()
        import test_feature_adapters as bound
        from feature_journeys.phase_fixture import PhaseFixtureReader
        def phase_reader(client,run,area):
            return PhaseFixtureReader(client,run,area,epoch_ms=self.model.epoch,monotonic=lambda:self.model.clock)
        with patch.dict(os.environ,self.configuration()),patch.object(registered.adapter,'_avatar_people_feature',side_effect=lambda *_args,**_kwargs:self.model.flow()), \
             patch('overte_phone_feature_dispatch.PhaseFixtureReader',side_effect=phase_reader):
            phases,reports=self.model.run_journey(lambda operation,values:registered.adapter.invoke(bound.SELECTOR,operation,values))
        self.assertEqual(17,len(phases));self.assertTrue(reports[-1]['sequenceCompleted']);self.assertTrue(reports[-1]['cleanupSucceeded'])
        with self.assertRaises(NativeUIError):self.model.flow().finalize_once()
        self.assertIsNotNone(self.model.flow().store.read()) # Active account authority cannot retire journals.
        self.client.close()
        original_discard=PrivateFeatureState.discard;interrupted=[]
        def lost_return(store,previous):
            original_discard(store,previous)
            if store.path.name=='phone-avatar-people-actor-feature.json' and not interrupted:
                interrupted.append(True);raise OSError('Synthetic lost host-file retirement return')
        with patch.object(PrivateFeatureState,'discard',lost_return),self.assertRaises(OSError):self.model.flow().finalize()
        self.assertTrue(interrupted);self.assertIsNotNone(self.model.flow().retirement_store.read())
        resumed=self.model.flow()
        with patch.object(resumed.source,'status',side_effect=AssertionError('Retirement replay must not retime original proof')):
            resumed.finalize()
        self.model.flow().finalize()
        for role,phone in self.model.phones.items():
            self.assertFalse(phone.auth['loggedIn']);self.assertEqual('look at',phone.sdk.mode);self.assertEqual({},phone.bookmarks)
            self.assertIsNone(self.model.world_render_store(role,role=role).read())
        for name in ('feature','primary-feature','actor-feature','retirement'):
            self.assertFalse((self.model.phones['primary'].root/('phone-avatar-people-'+name+'.json')).exists())
        self.assertTrue((self.model.root/('avatar-people-retired-'+self.run+'.json')).exists())
        self.assertTrue(any(role=='actor' and id=='people.ConnectionAccept' for role,id,_ in self.model.inputs))
        self.assertTrue(any(role=='primary' and id=='avatar.dialog.confirm' for role,id,_ in self.model.inputs))

    def registered_adapter(self):
        from test_account_fixture_launch import AccountFixtureLaunchTests
        setup=AccountFixtureLaunchTests();setup.setUp();self.addCleanup(setup.doCleanups);return setup.f

    def configuration(self):
        policy=self.model.root/'avatar-people-policy.json';access=self.model.root/'adapter-fixture-access.json'
        for path,value in ((policy,POLICY),(access,dict(fixtureAdapterAccessVersion=1,fixtureUrl=self.client.url,adapterToken=self.adapter))):
            store=PrivateFeatureState(path)
            if store.read() is None:store.write(value,None)
        return dict(OVERTE_PHONE_FEATURE_AVATAR_PEOPLE='1',OVERTE_PHONE_ACCOUNT_FIXTURE='1',OVERTE_E2E_FEATURE_FIXTURE_URL=self.client.url,
            OVERTE_PHONE_FEATURE_FIXTURE_CONFIG=str(access),OVERTE_PHONE_AVATAR_PEOPLE_IMAGE_POLICY=str(policy),OVERTE_DEVICE_ARTIFACT_DIR=str(self.model.root))

    def foundation(self,fault=None):
        """Execute the existing mandatory multi-user method over a third source."""
        from overte_session import OverteSession
        from feature_journeys.scenarios import FOUNDATIONS
        # This producer models the controlled assignment-client's independent
        # movement observations and departure/reconnect, before Phone setup.
        self.assertIn('multi-user',FOUNDATIONS['avatar-people'])
        source=dict(connected=False,count=0,distance=0.,reconnects=0);proof=[]
        def snapshot(_artifact=None):
            source['count']+=1
            if source['connected'] and fault!='static':source['distance']+=.1
            return dict(domain=dict(connected=source['connected'],serverless=not source['connected'],id=DOMAIN),
                peer=dict(present=source['connected'] and fault!='missing',displayName='OVERTE_E2E_PEER',sessionId=PEER if fault!='replaced' or source['reconnects']<2 else SESSION,
                    observationCount=source['count'],movementDistanceMeters=source['distance']))
        def enter():source['connected']=True;source['reconnects']+=1;return snapshot()
        def leave():source['connected']=False;return snapshot()
        session=object.__new__(OverteSession);session.timeout_seconds=.5;session.poll_seconds=.05;session.snapshot=snapshot
        session.enter_controlled_domain=enter;session.load_controlled_scene=leave
        with patch.dict(os.environ,OVERTE_E2E_DOMAIN_ID=DOMAIN),patch('overte_session.time.monotonic',lambda:self.model.clock),patch('overte_session.time.sleep',self.model.sleep),patch('overte_session.write_json',side_effect=lambda name,value:proof.append((name,deepcopy(value)))):
            before,after=session.assert_controlled_peer_roundtrip()
        self.assertEqual(before['sessionId'],after['sessionId']);self.assertGreater(after['movementDistanceMeters'],before['movementDistanceMeters'])
        self.assertTrue(source['connected']);self.assertEqual(2,source['reconnects']);return proof

    def test_missing_static_or_replaced_multi_user_source_blocks_phone_setup(self):
        from module_support import AssertionFailure
        for fault in ('missing','static','replaced'):
            with self.subTest(fault=fault),self.assertRaises(AssertionFailure):self.foundation(fault)
        self.assertEqual([],self.model.inputs);self.assertIsNone(self.model.flow().store.read())

    def test_registration_is_default_off_and_missing_independent_configuration_is_not_advertised(self):
        registered=self.registered_adapter();config=self.configuration()
        with patch.dict(os.environ,config|dict(OVERTE_PHONE_FEATURE_AVATAR_PEOPLE='0')),patch.object(registered.adapter,'_avatar_people_feature') as factory:
            self.assertFalse(any(op.startswith('feature.avatar-people.') for op in registered.adapter.advertised_capabilities(registered.target)))
            with self.assertRaises(ValueError):registered.adapter.invoke('test-only-appium','feature.avatar-people.observe',dict(contractVersion=VERSION,runId=self.run,afterSequence=0))
            factory.assert_not_called()
        for edit in (dict(OVERTE_PHONE_FEATURE_AVATAR_PEOPLE='yes'),dict(OVERTE_PHONE_ACCOUNT_FIXTURE='0'),dict(OVERTE_PHONE_AVATAR_PEOPLE_IMAGE_POLICY=''),
                     dict(OVERTE_PHONE_FEATURE_FIXTURE_CONFIG=''),dict(OVERTE_E2E_FEATURE_FIXTURE_URL='http://controlled.invalid/feature-fixture/v1')):
            with self.subTest(edit=edit),patch.dict(os.environ,config|edit),self.assertRaises((ValueError,RuntimeError)):
                registered.adapter.advertised_capabilities(registered.target)
        with patch.dict(os.environ,config):
            self.assertTrue(all('feature.avatar-people.'+kind in registered.adapter.advertised_capabilities(registered.target) for kind in ('act','observe','cleanup')))

    def test_actor_configuration_requires_a_second_phone_and_closed_image_policy(self):
        from script_observer import configuration
        path=self.model.root/'avatar-actor.json';store=PrivateFeatureState(path)
        value=dict(featureObserverVersion=4,area='avatar-people',target='primary',peerTarget='actor',peerImagePolicy=POLICY,
            candidateArguments=[],fixtureUrl=self.client.url,actorToken=self.actor,durationSeconds=60)
        store.write(value,None);self.assertEqual(value,configuration(path))
        for change in (dict(featureObserverVersion=3),dict(peerTarget='primary'),dict(peerImagePolicy=POLICY|dict(expectedScale=1.5)),dict(fixtureUrl='http://controlled.invalid/feature-fixture/v1')):
            edited=value|change;store.write(edited,store.read())
            with self.subTest(change=change),self.assertRaises((ValueError,NativeUIError)):configuration(path)

    def test_missing_second_phone_prevents_a_green_baseline_and_preserves_ownership(self):
        with self.assertRaises(PhasePending):self.model.flow().observe(dict(contractVersion=VERSION,runId=self.run,afterSequence=0))
        record=self.model.flow().store.read();self.assertIsNotNone(record)
        self.assertFalse(self.model.phones['actor'].auth['loggedIn']);self.assertEqual([],list(self.model.root.glob('avatar-people-*-actor-*.png')))

    def test_recreated_owner_pins_original_https_service_before_new_native_acquisition(self):
        self.model.flow().prepare();original=self.social.instance;commands=len(self.model.inputs)
        resumed=self.model.flow()
        with resumed.scope():
            resumed.load();self.assertEqual(original,resumed.source.instance)
            self.social.instance='0'*32
            with self.assertRaises(NativeUIError):resumed.source.attach()
        self.assertEqual(commands,len(self.model.inputs));self.assertIsNotNone(resumed.store.read())
        self.social.instance=original

    def test_real_backend_connection_still_requires_original_current_primary_post_consumption(self):
        from overte_phone_avatar_people_measurements import measurement
        self.model.flow().prepare();self.model.actor_flow=self.model.flow('actor');self.model.actor_flow.prepare();self.model.actor_enabled=True
        for verb,inputs in (('connection-request',dict(peer='owned-peer')),('peer-accept',{})):
            ticket=uuid.uuid4().hex;self.client.activate(ticket,verb,inputs)
            self.model.flow().act(dict(contractVersion=VERSION,runId=self.run,ticket=ticket,verb=verb,inputs=inputs,fixtureUrl=self.client.url+'/runs/'+self.run+'/'))
        flow=self.model.flow()
        with flow.scope():
            flow.load();phase=flow.phase();before=flow.native();after=flow.native();baseline=flow.original()['native'];backend=flow.source.status_backend()
            def observe(left,right):return measurement(self.run,left,right,backend,phase['status'],baseline,flow.fixture_url,flow.source.instance,
                pid=31,epoch=self.model.epoch(),after_epoch=math.ceil(phase['afterEpochMs']))
            self.assertEqual('connected',observe(before,after)['connection'])
            bad_before,bad_after=deepcopy(before),deepcopy(after)
            for packet in (bad_before,bad_after):
                packet['source']['peopleReplies']['events']=[row for row in packet['source']['peopleReplies']['events'] if row['method']!='POST']
            with self.assertRaises(NativeUIError):observe(bad_before,bad_after)

    def test_probe_ordinary_wearable_remove_grammar_is_closed(self):
        import subprocess
        text=(ROOT/'tests/device/probe/overte_e2e_probe.js').read_text()
        def function(name):
            start=text.index('    function '+name+'(');end=text.index('\n    }',start)+6;return text[start:end]
        script='\n'.join(function(name) for name in ('objectKeysMatch','phoneFileInteger','validPhoneAvatarPeopleRequest'))
        script+='\nconst assert=require("assert");let n="a".repeat(32);let c={schemaVersion:1,commandId:n,action:"activate",instance:n,generation:n,sequence:1,observedElapsedMs:0,controlId:"avatar.wearable.remove",controlToken:n};assert(validPhoneAvatarPeopleRequest(c));'
        script+='for(const e of [{expectedState:{}},{entityId:n},{controlId:"avatar.wearable.remove-all"},{action:"delete"},{sequence:true}])assert(!validPhoneAvatarPeopleRequest({...c,...e}));'
        subprocess.run(['node','-e',script],check=True,timeout=10)


if __name__=='__main__':unittest.main()
