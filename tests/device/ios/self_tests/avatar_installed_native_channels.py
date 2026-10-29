"""Declared host native query/AFC and ordinary Qt producer profile.

No Feature/Runtime factory, original decoder, publication, end verifier or
returned product result is replaced. Raw getters reuse the existing declared
Strong/TerminalDomain producers; all normal owners use their real transports.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import hashlib
import json
import math
import time
import threading
import uuid
from adapters.native_feature_observation import need
from ios.adapters import avatar_state,avatar_renderers,avatar_social_http,people_model,avatar_scripts,avatar_entities
from ios.adapters import avatar_world,emote_world,pointer_state,script_dialogs,web_closures,avatar_inputs,uikit_input,world_web_keys
from ios.adapters import create_entities
from ios.adapters.view_controls import LABELS,MODES
from ios.adapters.avatar_peer import session_sha
from ios.self_tests.avatar_prepare_fixture import SESSIONS
from self_tests.test_native_avatar_receive import record as receive_record
from self_tests.test_native_graphics_subject import Boundary as GraphicsSubject
from feature_journeys.graphics_fixture import subject_ids


class RealtimeProducerClock:
    """Host clock chosen before binding; assignments are minimum wait targets.

    Existing boundary constructors request their initial local clock or restore
    a previously read value. These lower bounds cannot move this real clock
    backward. Only future targets wait, so genuine quiet durations remain real.
    This never reads, changes or retimes an already emitted original packet.
    """
    def __init__(self):self.epoch=time.time();self.started=time.monotonic()
    def __getitem__(self,index):
        need(index==0);return self.epoch+time.monotonic()-self.started-1700000000
    def __setitem__(self,index,target):
        need(index==0 and type(target) in (int,float) and math.isfinite(target) and 0<=target<=1e15);delay=target-self[0]
        if delay>0:time.sleep(delay)


class NativeHTTPReply:
    """One original raw HTTP response, independent of the next native request."""
    def __init__(self,status,body):
        need(type(body) is bytes);self.status,self.body=status,body
    def __enter__(self):return self
    def __exit__(self,*_args):return False
    def read(self,limit):return self.body[:limit]


class AvatarNativeChannels:
    PROFILE='ordinary-installed-avatar-host-v1'
    FAMILIES=(('state',avatar_state),('renderers',avatar_renderers),('http',avatar_social_http),
        ('people',people_model),('scripts',avatar_scripts),('entities',avatar_entities))
    def __init__(self,domain,role,native):
        need(role in ('primary','actor') and not hasattr(native,'avatar_channels'))
        self.domain,self.role,self.native=domain,role,native
        self.readers={};self.originals={};self.requests=[];self.view_stage=None;self.subject=GraphicsSubject()
        self.profile=self.PROFILE;self.http_lock=threading.RLock();native.avatar_channels=self
        self.scene.domain.io.qt.menu=True
        self.old_post,self.old_execute,self.old_observed,self.old_call=native.post,native.execute,native.observed,native.call
        native.post=self.post;native.execute=self.execute;native.observed=self.observed;native.call=self.call
    def bound(self):
        n=self.native;need(n.avatar_channels is self and self.profile==self.PROFILE and n.state['targetFingerprint']==n.fingerprint())
    @property
    def scene(self):return self.domain.scenes[self.role]
    def emit(self,filename,value):
        # First raw response for THIS real request. This is not a retained DTO.
        self.originals[filename]=json.dumps(value,separators=(',',':'))
    def raw_reader(self,key):
        if key not in self.readers:
            if key=='entity-tree':reader=self.scene.entity.reader
            elif key=='gpu':
                def no_intent(*_args):raise AssertionError('Only the OUTER real image owner may admit an intent')
                reader=self.scene.vulkan(no_intent,None)
            else:
                family=next((name,module) for name,module in self.FAMILIES if name==key)
                reader=self.scene.f.reader(key,getattr(family[1],{'state':'IOSAvatarState','renderers':'IOSAvatarRenderers',
                    'http':'IOSAvatarSocialHttp','people':'IOSPeopleModel','scripts':'IOSAvatarScripts','entities':'IOSAvatarEntities'}[key]))
            self.readers[key]=reader
        return self.readers[key]
    def read_source(self,key,filename,query):
        reader=self.raw_reader(key);reader.send(deepcopy(query));raw=reader.original()
        need(type(raw) is str);self.originals[filename]=raw
    def packet(self,query):
        d=self.domain;n=self.native;scene=self.scene;world=scene.domain;action=query['action']
        for name,module in self.FAMILIES:
            if action==module.ACTION:
                module.command(query);self.read_source(name,module.FILE,query);return True
        direct={create_entities.ACTION:('entity-tree',create_entities.FILE),'feature-vulkan-world-frame':('gpu','feature-vulkan-world-frame.json')}
        if action in direct:
            key,filename=direct[action];self.read_source(key,filename,query);return True
        if action==pointer_state.ACTION:
            scene.pointer.send(query);scene.pointer.packet['processId']=n.pid;self.emit(pointer_state.FILE,scene.pointer.packet);return True
        if action==world_web_keys.ACTION:
            value=d.keys[self.role].packet();value.update(requestId=query['commandId'],runId=query['runId'],processId=n.pid)
            for name in ('clockBefore','clockAfter'):value[name]['monotonicMs']=round(d.clock[0]*1000)
            key=d.keys[self.role];value['source'].update(bornEpochMs=key.born_epoch,startup=dict(observed=True,
                epochMs=key.started_epoch,monotonicMs=1000,windowCount=0,modifiers=0))
            self.emit(world_web_keys.FILE,value);return True
        if action==uikit_input.ACTION:self.emit(uikit_input.FILE,d.uikit[self.role].packet(query));return True
        if action=='native-geometry-snapshot':
            channel=d.geometry[self.role];d.clock[0]+=.001;channel['sequence']+=1
            keyboard=n.login.dialog and n.login.focused is not None
            value=dict(schemaVersion=1,commandId=query['commandId'],observation=dict(schemaVersion=1,
                sampleEpochMs=n.epoch(),sampleSequence=channel['sequence'],nativeUi=dict(valid=True,surfaceWidth=1024,surfaceHeight=768,
                    safeInsetLeft=0,safeInsetTop=20,safeInsetRight=0,safeInsetBottom=20,keyboardVisible=keyboard,
                    imeInsetBottom=250 if keyboard else 0),window=dict(width=1024,height=728)))
            channel['current']=value;self.emit('ios-ui-request-result.json',value);return True
        if action=='feature-script-files':
            scene.file.send(query);scene.file.sample.update(requestedEpochMs=n.epoch(),capturedEpochMs=n.epoch())
            self.originals['feature-script-files.json']=scene.file.read();return True
        if action=='feature-avatar-receive-observe':
            other='actor' if self.role=='primary' else 'primary';receiver=d.receivers[self.role]
            d.clock[0]+=.001;mesh=d.mesh(other);index=len(receiver.records)+1;row=receive_record(index,0.)
            body=json.dumps(dict(sessionId=SESSIONS[other],url=mesh['requested'],scale=mesh['scale'],
                joints=[[0,0,0,1,0,0,0] for _ in range(3)]),sort_keys=True).encode()
            row.update(capturedEpochMs=n.epoch(),avatarSha256=session_sha(SESSIONS[other]),mixerSha256='c'*64,
                recordSha256=hashlib.sha256(body).hexdigest(),recordBytes=len(body),jointCount=3,
                joints=[dict(index=i,rotation=[0,0,0,1],translation=[0,0,0]) for i in range(3)],
                advertisedModelUrl=mesh['requested'],targetScale=mesh['scale'])
            receiver.records.append(row);receiver.send(query);value=receiver.current
            value.update(processId=n.pid,requestedEpochMs=n.epoch(),capturedEpochMs=n.epoch())
            value['source'].update(processId=n.pid,selfSha256=session_sha(SESSIONS[self.role]),
                droppedRecords=max(0,len(receiver.records)-32),records=deepcopy(receiver.records[-32:]))
            self.emit('feature-avatar-receive.json',value);return True
        if action in (avatar_world.ACTION,emote_world.ACTION):
            (avatar_world if action==avatar_world.ACTION else emote_world).command(query)
            value=world.world(query['runId']) if action==avatar_world.ACTION else d.peer_world(self.role,query['runId'])
            value['requestId']=query['commandId'];self.emit((avatar_world if action==avatar_world.ACTION else emote_world).FILE,value);return True
        if action=='feature-script-terminal-observe':
            value=world.terminal(0);value['commandId']=query['commandId'];self.emit('feature-script-terminal.json',value);return True
        if action=='feature-script-work-observe':
            value=world.work(query['managerInstance'],0);value['requestId']=query['commandId']
            value['source']['work']['requestId']=query['commandId'];self.emit('feature-script-work.json',value);return True
        if action==script_dialogs.ACTION:
            script_dialogs.command(query);value=world.dialogs(query['runId']);value['requestId']=query['commandId'];self.emit(script_dialogs.FILE,value);return True
        if action=='feature-ios-web-closures':
            web_closures.command(query);need(query['fixtureUrl']==world.scope.fixture_url)
            d.worldless_web_queries[self.role].append(deepcopy(query));value=world.web(query['runId'],query['fixtureUrl'])
            if world.running and world.context is None:world.paint();value=world.web(query['runId'],query['fixtureUrl'])
            value['commandId']=query['commandId'];self.emit(web_closures.FILE,value);return True
        if action==avatar_inputs.ACTION:
            avatar_inputs.command(query);ledger=d.input_packets[self.role];d.clock[0]+=.001;ledger['sequence']+=1
            value=dict(iosNormalInputsVersion=1,profile='avatar',requestId=query['commandId'],runId=query['runId'],
                instance='e'*32,sequence=ledger['sequence'],processId=n.pid,clockDomain='native-process-normal-inputs',
                clockBefore=dict(epochMs=n.epoch(),monotonicMs=round(d.clock[0]*1000)),
                clockAfter=dict(epochMs=n.epoch(),monotonicMs=round(d.clock[0]*1000)),source=dict(complete=True,events=deepcopy(ledger['events'])))
            ledger['current']=value;self.emit(avatar_inputs.FILE,value);return True
        if action=='normal-feature-observe':
            value,_epoch=world.io.observe(0);value['requestId']=query['commandId'];self.emit('normal-feature-observation.json',value);return True
        if action=='feature-graphics-subject-observe':
            def source(value):
                current=world.world(query['runId'])['source'];view=current['view'];avatar=current['avatar']
                value.update(processId=n.pid,requestedEpochMs=n.epoch(),capturedEpochMs=n.epoch())
                tree_ids={row['id'] for row in current['tree']['entities']}
                value['source'].update(subjectVersion=2,absentIds=[key for key in subject_ids(query['runId']).values() if key not in tree_ids],
                    view={key:deepcopy(view[key]) for key in value['source']['view']},
                    avatarPose={key:deepcopy(avatar[key]) for key in ('feetPosition','orientation','modelScale')})
            self.subject.edit=source;self.subject.send(query);self.originals['feature-graphics-subject.json']=self.subject.original();return True
        return False
    def http_reply(self,produce):
        # A real HTTP response body cannot turn into another request's echo.
        # Snapshot the actual producer body/status, never the expected command.
        # AFC remains the original current-file path with all request-ID guards.
        with self.http_lock:
            response=produce()
            if type(response) is NativeHTTPReply:return response
            need(response is self.native)
            return NativeHTTPReply(response.status,response.echo)
    def post(self,request,timeout):
        return self.http_reply(lambda:self.post_original(request,timeout))
    def post_original(self,request,timeout):
        self.bound();query=json.loads(request.data)
        if self.packet(query):
            self.requests.append(deepcopy(query));self.native.commands.append(deepcopy(query));self.native.echo=json.dumps(query).encode();return self.native
        if query['action']=='normal-ui-input' and query['operation']=='edit':
            item=query['input'];rows=[row for row in self.native.observed()['controls'] if row['token']==item['fieldToken']]
            if len(rows)==1 and rows[0]['id'] in ('script-file.folder','script-file.primary'):
                row=rows[0];n=self.native;need(item['instance']==n.instance and item['sequence']==n.sequence+1 and row['enabled'])
                if item['operation']=='replace':self.scene.domain.io.replace(row['id'],item['text'])
                elif item['operation']=='submit':self.scene.domain.io.submit(row['id'])
                elif item['operation']=='select-index':self.scene.domain.io.select_index(row['id'],item['index'])
                else:raise AssertionError('Unsupported ordinary Script picker edit')
                n.sequence=item['sequence'];n.input_log.append(row['id']+':'+item['operation'])
                n.ui_receipt=dict(schemaVersion=1,commandId=query['commandId'],status=dict(schemaVersion=1,commandId=item['commandId'],
                    instance=n.instance,sequence=n.sequence,performed=True,processId=n.pid,sampleEpochMs=n.epoch()))
                n.echo=json.dumps(query).encode();n.commands.append(deepcopy(query));return n
        return self.old_post(request,timeout)
    def execute(self,session,operation,values):
        if operation=='mobile: pullFile':
            self.bound();filename=values['remotePath'].rsplit('/',1)[-1]
            expected='@'+self.native.target['appId']+':documents/'+self.native.target['testBuild']['resultsDirectory']+'/'+filename
            if filename in self.originals:
                need(session==self.native.state['sessionId'] and values==dict(remotePath=expected))
                return base64.b64encode(self.originals[filename].encode()).decode()
        return self.old_execute(session,operation,values)
    def observed(self):
        value=self.old_observed();n=self.native
        if hasattr(n,'scene') and not n.login.dialog:
            world=self.scene.domain
            if world.io.qt.page not in ('avatar','people'):
                if self.view_stage is None:rows=deepcopy(world.io.capture()['controls'])
                else:
                    ids=['view.menu'] if self.view_stage=='menu' else list(MODES.values())
                    rows=[dict(id=key,viewMenuSourceVersion=1,sourceType=2 if key=='view.menu' else 1,
                        labelSha256=hashlib.sha256(LABELS[key].encode()).hexdigest(),checked=None if key=='view.menu' else MODES[world.world_template['source']['view']['mode']]==key) for key in ids]
                for row in rows:
                    row['token']=str(uuid.uuid5(uuid.NAMESPACE_URL,row['id']+n.generation+str(row.get('sourceUrl',''))))
                    row.setdefault('focused',True);row.setdefault('enabled',True);row['frame']=dict(x=10,y=20,width=100,height=48)
                if world.io.qt.page=='menu' and self.view_stage is None:
                    key='view.menu';rows.append(dict(id=key,token=str(uuid.uuid5(uuid.NAMESPACE_URL,key+n.generation)),enabled=True,focused=False,
                        frame=dict(x=10,y=20,width=100,height=48),viewMenuSourceVersion=1,sourceType=2,labelSha256=hashlib.sha256(b'View').hexdigest(),checked=None))
                identifiers={row['id'] for row in rows};value['controls']=rows+[row for row in value['controls'] if row['id'] not in identifiers]
        value.update(graphicsControlsVersion=1,viewMenuControlsVersion=1,generation=n.generation)
        return value
    def call(self,method,path,body=None):
        n=self.native
        if method=='POST' and '/element/' in path and path.endswith('/click'):
            identifier,token=n.references[path.split('/element/')[1].split('/')[0]];name=identifier.removeprefix('OverteNavigation.')
            if not n.login.dialog and (name.startswith(('scripts.','script-file.','view.')) or name=='tablet.home'):
                rows=[row for row in n.observed()['controls'] if row['id']==name];need(len(rows)==1 and rows[0]['token']==token)
                world=self.scene.domain
                if name=='scripts.menu':world.io.activate(name);n.menu='root';self.view_stage=None
                elif name=='view.menu':self.view_stage='view'
                elif name in MODES.values():
                    world.world_template['source']['view']['mode']=next(mode for mode,key in MODES.items() if key==name);world.io.qt.page='home';n.menu='home';self.view_stage=None
                else:world.io.activate(name,source=rows[0].get('sourceUrl'))
                n.input_log.append(name);n.sequence+=1;return None
        return self.old_call(method,path,body)
