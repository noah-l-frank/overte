"""Independent current native DTO producers; Qt/V8 boundaries are modeled."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import base64
import hashlib
from pathlib import Path
from ios.adapters.avatar_call_stack import SUFFIXES

ROOT=Path(__file__).resolve().parents[4]
EPOCH=1700000000000


def original(suffixes,epoch=EPOCH):
    code=[];frames=[];modules=[]
    for index,suffix in enumerate(suffixes):
        raw=(ROOT/'scripts'/suffix[1:]).read_text().encode('utf-16-le');url='qrc:/scripts'+suffix
        sha=hashlib.sha256(raw).hexdigest();url_sha=hashlib.sha256(url.encode()).hexdigest()
        code.append(dict(sequence=index+1,url=url,submittedEpochMs=epoch-100,encoding='utf-16le-code-units',
            codeUnits=len(raw)//2,sha256=sha))
        frames.append(dict(scriptId=SUFFIXES.index(suffix)+1,line=78 if suffix=='/modules/request.js' else 63,column=1,
            sourceUrlSha256=url_sha,compiled=dict(urlSha256=url_sha,encoding='utf-16le-code-units',codeUnits=len(raw)//2,
                sha256=sha,firstObservedEpochMs=epoch-50),isEval=False,isConstructor=False))
        modules.append(dict(frame=index,url=url))
    return dict(emitStackVersion=1,instance='a'*32,complete=True,frames=frames),modules,code


def scripts2(epoch=EPOCH,*,run='2'*32,capture_offset=100,sequence=1,request='ios-'+'1'*32):
    _stack,_modules,code=original(SUFFIXES,epoch);raw=(ROOT/'scripts/defaultScripts.js').read_text().encode('utf-16-le')
    worker=dict(membership=dict(instance='b'*32,assigned=True,url='qrc:/scripts/defaultScripts.js',loadGeneration=1,assignedEpochMs=epoch-120),
        code=dict(submitted=True,encoding='utf-16le-code-units',codeUnits=len(raw)//2,sha256=hashlib.sha256(raw).hexdigest(),submittedEpochMs=epoch-110),
        running=True,stopping=False,finished=False,done=False,
        avatar=dict(avatarScriptVersion=2,instance='e'*32,complete=True,code=code,events=[],callerStacks=[]),
        uiWork=dict(avatarUiWorkVersion=2,instance='f'*32,complete=True,timers=[],callerStacks=[]))
    return dict(iosAvatarScriptsVersion=2,requestId=request,runId=run,instance='3'*32,sequence=sequence,processId=42,
        clockDomain='native-main-avatar-scripts',clockBefore=dict(epochMs=epoch+capture_offset,monotonicMs=capture_offset),
        clockAfter=dict(epochMs=epoch+capture_offset+10,monotonicMs=capture_offset+10),source=dict(complete=True,revision=1,workers=[worker]))


def timer2(value,epoch=EPOCH,*,created_epoch=None):
    stack,modules,_code=original(('/system/pal.js','/system/libraries/peopleConnection.js'),epoch)
    worker=value['source']['workers'][0];created_epoch=epoch-20 if created_epoch is None else created_epoch
    worker['avatar']['callerStacks'].append(dict(id='a1'*16,callerStack=stack,callerModules=modules))
    worker['uiWork']['callerStacks'].append(dict(id='a2'*16,callerStack=deepcopy(stack),callerModules=deepcopy(modules)))
    detail=dict(handle=1,callerStackId='a1'*16,active=True,singleShot=True,intervalMs=250,remainingMs=250)
    worker['avatar']['events'].append(dict(sequence=1,timerId='c'*32,kind='created',capturedEpochMs=created_epoch,details=detail))
    worker['uiWork']['timers'].append(dict(timerId='d'*32,handle=1,callerStackId='a2'*16,
        createdEpochMs=created_epoch,singleShot=True,intervalMs=250,activeAtBirth=True,remainingAtBirthMs=250,destroyedEpochMs=None,
        fired=0,entered=0,left=0,depth=0,pendingDispatch=0,lastFiredEpochMs=None,lastCallbackEpochMs=None,lastDispatchEpochMs=None))
    return detail


def wire(raw):
    return dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),contentBase64=base64.b64encode(raw).decode())


def http2(*,epoch=EPOCH,raw=b'{}',response_id='4'*32,run='2'*32,origin='https://owned.invalid'):
    scripts=scripts2(epoch);worker=scripts['source']['workers'][0]
    stack,modules,_code=original(('/modules/request.js','/system/pal.js'),epoch)
    source=dict(callerStackId='a3'*16,engine=deepcopy(worker['membership']),submitted=deepcopy(worker['code']),
        requestUrl=origin+'/api/v1/users?filter=connections',method='GET',protocolSignature=base64.b64encode(b'p'*16).decode())
    value=dict(iosAvatarSocialHttpVersion=2,requestId='ios-'+'5'*32,runId=run,instance='6'*32,sequence=1,processId=42,
        clockDomain='native-process-avatar-social-http',clockBefore=dict(epochMs=epoch+100,monotonicMs=100),
        clockAfter=dict(epochMs=epoch+110,monotonicMs=110),events=[],
        callerStacks=[dict(id='a3'*16,callerStack=stack,callerModules=modules)])
    def add(kind,details):
        index=len(value['events'])+1;value['events'].append(dict(sequence=index,eventId=f'{index:032x}',xhrId='7'*32,kind=kind,
            clock=dict(epochMs=epoch-20+index,monotonicMs=index),details=details))
    reply='8'*32
    add('created',source)
    add('sent',dict(replyId=reply,url=source['requestUrl'],method='GET',body=wire(b''),authorizationAttached=True,contentType=''))
    add('reply-finished',dict(replyId=reply,httpStatus=200,networkError=0,responseId=response_id,body=wire(raw)))
    add('callback-enter',dict(callback='readystatechange',readyState=4))
    read_stack,read_modules,_code=original(('/modules/request.js',),epoch)
    read_stack['frames'][0]['line']=30
    value['callerStacks'].append(dict(id='a4'*16,callerStack=read_stack,callerModules=read_modules))
    add('text-read',dict(replyId=reply,scriptSource=read_modules[0]['url'],sha256=wire(raw)['sha256'],callerStackId='a4'*16))
    add('callback-leave',dict(callback='readystatechange',readyState=4))
    return value


def timer_history2(count=120):
    """Actual packet grammar at 120 repeat timer births; no native execution."""
    value=scripts2(capture_offset=250*count+300,sequence=2,request='ios-'+'9'*32);timer2(value);worker=value['source']['workers'][0]
    created=deepcopy(worker['avatar']['events'][0]['details']);ui=deepcopy(worker['uiWork']['timers'][0])
    worker['avatar']['events']=[];worker['uiWork']['timers']=[]
    for index in range(count):
        at=EPOCH+130+250*index;timer_id=f'{2*index+1:032x}'
        for offset,(kind,details) in enumerate((('created',deepcopy(created)),('fired',dict(active=False,remainingMs=-1)),
                ('destroyed',{}),('callback-enter',{}),('callback-leave',{}))):
            worker['avatar']['events'].append(dict(sequence=len(worker['avatar']['events'])+1,timerId=timer_id,kind=kind,
                capturedEpochMs=at+offset,details=details))
        row=deepcopy(ui);row.update(timerId=f'{2*index+2:032x}',createdEpochMs=at,destroyedEpochMs=at+2,fired=1,entered=1,left=1,
            lastFiredEpochMs=at+1,lastCallbackEpochMs=at+4,lastDispatchEpochMs=at+5)
        worker['uiWork']['timers'].append(row)
    return value
