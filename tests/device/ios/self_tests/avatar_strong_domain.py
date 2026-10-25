"""Current native DTO producers driven by full original Pal/People/request JS.

Host Node supplies real executed source locations and callback returns. Engine
IDs, Qt workers/timers and native HTTP/renderer boundaries remain explicit host
models. No legacy native packet or callerChain is promoted to a V8 original.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request
import uuid

from ios.self_tests.avatar_final_domain import FinalDomain,RUN
from ios.self_tests.avatar_people_node import PeopleNode

ROOT=Path(__file__).resolve().parents[4]


def wire(raw):return dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),contentBase64=base64.b64encode(raw).decode())


class StrongDomain(FinalDomain):
    node_type=PeopleNode
    def __init__(self,test):
        self.compiled={role:{} for role in ('primary','actor')};self.caller_tables={role:{key:[] for key in ('avatar','uiWork','http')} for role in self.compiled}
        self.vms={role:uuid.uuid4().hex for role in self.compiled};self.produced={role:[] for role in self.compiled}
        super().__init__(test)
        for role,scene in self.scenes.items():
            # Fresh producer generation is fixed before its first source read.
            # Existing legacy fixture constructors remain separate/unmodified.
            f=scene.f;script=f.prototypes['scripts'];script['iosAvatarScriptsVersion']=2
            worker=script['source']['workers'][0];worker['avatar']=dict(avatarScriptVersion=2,instance=worker['avatar']['instance'],
                complete=True,code=worker['avatar']['code'],events=[],callerStacks=[])
            worker['uiWork']=dict(avatarUiWorkVersion=2,instance=worker['uiWork']['instance'],complete=True,timers=[],callerStacks=[])
            f.prototypes['http']=dict(f.prototypes['http'],iosAvatarSocialHttpVersion=2,callerStacks=[])
            old=f.mutate
            def mutate(name,value,role=role,old=old):
                old(name,value)
                if name=='scripts':
                    worker=value['source']['workers'][0]
                    worker['avatar']['callerStacks']=deepcopy(self.caller_tables[role]['avatar'])
                    worker['uiWork']['callerStacks']=deepcopy(self.caller_tables[role]['uiWork'])
                    worker['uiWork']['timers']=self.timer_rows(role)
                elif name=='http':value['callerStacks']=deepcopy(self.caller_tables[role]['http'])
            f.mutate=mutate

    def actual_stack(self,role,rows,epoch):
        frames=[];modules=[]
        for index,row in enumerate(rows):
            url=row['url'];suffix=url.removeprefix('qrc:/scripts');assert url=='qrc:/scripts'+suffix and suffix.startswith('/')
            compiled=self.compiled[role].get(url)
            if compiled is None:
                raw=(ROOT/'scripts'/suffix[1:]).read_text().encode('utf-16-le')
                compiled=dict(urlSha256=hashlib.sha256(url.encode()).hexdigest(),encoding='utf-16le-code-units',codeUnits=len(raw)//2,
                    sha256=hashlib.sha256(raw).hexdigest(),firstObservedEpochMs=epoch)
                self.compiled[role][url]=compiled
            assert compiled['firstObservedEpochMs']<=epoch
            frames.append(dict(scriptId=list(self.compiled[role]).index(url)+1,line=row['line'],column=row['column'],
                sourceUrlSha256=compiled['urlSha256'],compiled=deepcopy(compiled),isEval=row['isEval'],isConstructor=row['isConstructor']))
            modules.append(dict(frame=index,url=url))
        assert frames
        return dict(emitStackVersion=1,instance=self.vms[role],complete=True,frames=frames),modules

    def retain(self,role,kind,actual,modules):
        rows=self.caller_tables[role][kind]
        for row in rows:
            if row['callerStack']==actual and row['callerModules']==modules:return row['id']
        value=dict(id=uuid.uuid4().hex,callerStack=deepcopy(actual),callerModules=deepcopy(modules));rows.append(value);return value['id']

    def update(self,value):
        # This receives actual native-boundary events emitted by full Pal JS,
        # not a preexisting legacy native DTO. Construct generation 2 directly.
        for role,events in value['timers'].items():
            for event in events[len(self.produced[role]):]:
                current=deepcopy(event)
                if current['kind']=='created':
                    rows=current['details'].pop('callerFrames');actual,modules=self.actual_stack(role,rows,current['capturedEpochMs'])
                    current['details']['callerStackId']=self.retain(role,'avatar',actual,modules)
                    self.retain(role,'uiWork',actual,modules)
                self.produced[role].append(current)
        value=deepcopy(value);value['timers']=deepcopy(self.produced);super().update(value)

    def timer_rows(self,role):
        rows={}
        for event in self.produced[role]:
            id_=event['timerId'];kind=event['kind'];at=event['capturedEpochMs'];details=event['details']
            if kind=='created':
                original=next(row for row in self.caller_tables[role]['avatar'] if row['id']==details['callerStackId'])
                caller=self.retain(role,'uiWork',original['callerStack'],original['callerModules'])
                rows[id_]=dict(timerId=id_,handle=details['handle'],callerStackId=caller,createdEpochMs=at,singleShot=details['singleShot'],
                    intervalMs=details['intervalMs'],activeAtBirth=details['active'],remainingAtBirthMs=details['remainingMs'],destroyedEpochMs=None,
                    fired=0,entered=0,left=0,depth=0,pendingDispatch=0,lastFiredEpochMs=None,lastCallbackEpochMs=None,lastDispatchEpochMs=None)
            elif kind=='destroyed':rows[id_]['destroyedEpochMs']=at
            elif kind=='fired':rows[id_].update(fired=rows[id_]['fired']+1,lastFiredEpochMs=at)
            elif kind=='callback-enter':rows[id_].update(entered=rows[id_]['entered']+1,depth=1,pendingDispatch=1,lastCallbackEpochMs=at)
            elif kind=='callback-leave':rows[id_].update(left=rows[id_]['left']+1,depth=0,pendingDispatch=0,lastCallbackEpochMs=at,lastDispatchEpochMs=at)
            else:raise AssertionError('Unknown actual timer event')
        return sorted(rows.values(),key=lambda row:row['timerId'])

    def complete_requests(self,value):
        self.update(value);requests=list(value['requests']);answers=[]
        for row in requests:
            role=row['role'];n=self.natives[role];options=row['options'];url=options['uri'];method=options.get('method','GET')
            raw=json.dumps(options['body'],separators=(',',':')).encode() if options.get('body') is not None else b''
            epoch=n.epoch();actual,modules=self.actual_stack(role,row['openStack'],epoch)
            worker=self.scenes[role].f.prototypes['scripts']['source']['workers'][0]
            created=dict(callerStackId=self.retain(role,'http',actual,modules),engine=deepcopy(worker['membership']),submitted=deepcopy(worker['code']),
                requestUrl=url,method=method,protocolSignature='cHBwcHBwcHBwcHBwcHBwcA==')
            xhr,reply=uuid.uuid4().hex,uuid.uuid4().hex;events=self.http_events[role]
            def add(kind,details):events.append(dict(sequence=len(events)+1,eventId=uuid.uuid4().hex,xhrId=xhr,kind=kind,
                clock=dict(epochMs=n.epoch(),monotonicMs=round(self.clock[0]*1000)),details=details))
            add('created',created);add('sent',dict(replyId=reply,url=url,method=method,body=wire(raw),authorizationAttached=True,contentType='application/json'))
            request=Request(url,data=raw if method in ('POST','DELETE') else None,
                headers={'Authorization':'Bearer '+n.token,'Content-Type':'application/json'},method=method)
            try:response=self.opener.open(request,timeout=5)
            except HTTPError as error:response=error
            with response:status=response.code;data=response.read(65537);identity=response.headers.get('X-Overte-Fixture-Response')
            add('reply-finished',dict(replyId=reply,httpStatus=status,networkError=0,responseId=identity,body=wire(data)))
            value=self.node.request('reply',id=row['id'],raw=data.decode(),config=self.identities());self.update(value)
            calls=[call for call in value['nativeCalls'] if call['role']==role and call['id']==row['id'] and call['kind']=='text-read'];assert len(calls)==1
            actual,modules=self.actual_stack(role,calls[0]['stack'],n.epoch());add('callback-enter',dict(callback='readystatechange',readyState=4))
            add('text-read',dict(replyId=reply,scriptSource=modules[0]['url'],sha256=wire(data)['sha256'],callerStackId=self.retain(role,'http',actual,modules)))
            add('callback-leave',dict(callback='readystatechange',readyState=4));add('callbacks-released',{});add('timer-destroyed',{});add('xhr-destroyed',{});add('reply-destroyed',dict(replyId=reply))
            requests.extend(value['requests']);answers.append(json.loads(data))
            assert len(requests)<=64
        return answers

    def exchange(self,op,**fields):
        value=self.node.request(op,config=self.identities(),**fields);self.complete_requests(value)
        self.clock[0]+=.21;value=self.node.request('tick',config=self.identities());self.complete_requests(value);return value

    def remove_connection(self,role,peer):
        # Execute the original Pal handler and request module, constructing
        # source2 from their actual native-boundary frames. The legacy
        # response() producer must never inject callerChain rows into source2.
        value=self.node.request('remove',role=role,peer=peer,config=self.identities())
        self.complete_requests(value);self.directory(role)

    def directory(self,role):
        # Normal QML-to-request-service callback, preserving its actual stack.
        value=self.node.request('qml-request',role=role,options=dict(uri=self.origin+'/api/v1/users/connections?page=1&per_page=1000&sort=username%2CASC'),config=self.identities())
        result=self.complete_requests(value);assert result
        self.tables[role]=self.node.request('page',data=result[0]['data'])['rows'];return self.tables[role]
