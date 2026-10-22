"""Original Qt gesture deliveries and separately sampled actual avatar input."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import time
import uuid
from adapters.native_feature_observation import exact,need,integer,number,decode,fresh
from adapters.normal_ui import NativeUIError
from overte_phone_snapshot_readbacks import nonce

FILE='phone-lifecycle-world-input.json'


def command(value):
    exact(value,{'schemaVersion','commandId','action','operation','runId','gestureId'})
    need(type(value['schemaVersion']) is int and value['schemaVersion']==1 and nonce(value['commandId']) and nonce(value['runId'])
        and value['action']=='phone-lifecycle-world-input' and value['operation'] in ('observe','hold','release'))
    need(nonce(value['gestureId']) if value['operation']=='release' else value['gestureId']=='')
    return value


def validate(value,request,pid,epoch):
    command(request);exact(value,{'schemaVersion','requestId','runId','instance','sequence','processId','requestedEpochMs','capturedEpochMs','source','motion'})
    need(type(value['schemaVersion']) is int and value['schemaVersion']==1 and value['requestId']==request['commandId'] and value['runId']==request['runId']
        and nonce(value['instance']) and integer(value['sequence'],1) and type(value['processId']) is int and value['processId']==pid
        and integer(value['requestedEpochMs'],1) and integer(value['capturedEpochMs'],value['requestedEpochMs'])
        and value['capturedEpochMs']-value['requestedEpochMs']<1500);fresh(value['capturedEpochMs'],epoch)
    source=value['source'];exact(source,{'phoneLifecycleWorldInputVersion','instance','sequence','commandId','runId','capturedEpochMs','performed',
        'pending','pendingRun','pendingGesture','elapsedMs','timerActive','gestures'})
    need(type(source['phoneLifecycleWorldInputVersion']) is int and source['phoneLifecycleWorldInputVersion']==1 and nonce(source['instance']) and integer(source['sequence'],1)
        and source['commandId']==request['commandId'] and source['runId']==request['runId'] and integer(source['capturedEpochMs'],value['requestedEpochMs'],value['capturedEpochMs'])
        and all(type(source[key]) is bool for key in ('performed','pending','timerActive')) and (request['operation']!='observe' or source['performed'] is False)
        and integer(source['elapsedMs'],0,10000) and type(source['gestures']) is list and len(source['gestures'])<=32)
    ids=set();commands=set();pending=[]
    for row in source['gestures']:
        exact(row,{'gestureId','runId','commandId','createdEpochMs','pressEpochMs','releaseEpochMs','releaseReason','pressObserved','releaseObserved'})
        need(nonce(row['gestureId']) and row['gestureId'] not in ids and nonce(row['runId']) and nonce(row['commandId']) and row['commandId'] not in commands
            and integer(row['createdEpochMs'],1,source['capturedEpochMs']) and all(type(row[key]) is bool for key in ('pressObserved','releaseObserved'))
            and integer(row['pressEpochMs'],0,source['capturedEpochMs']) and integer(row['releaseEpochMs'],0,source['capturedEpochMs']))
        ids.add(row['gestureId']);commands.add(row['commandId'])
        if row['pressObserved']:need(row['pressEpochMs']>=row['createdEpochMs'])
        else:need(row['pressEpochMs']==0)
        if row['releaseObserved']:
            need(row['releaseReason'] in ('explicit','hold-deadline','focus-lost','owner-destroyed') and row['releaseEpochMs']>=max(row['createdEpochMs'],row['pressEpochMs']))
        else:need(row['releaseReason']=='' and row['releaseEpochMs']==0);pending.append(row)
    if source['pending']:
        need(len(pending)==1 and source['timerActive'] and source['elapsedMs']<10000 and source['pendingRun']==pending[0]['runId']
            and source['pendingGesture']==pending[0]['gestureId'])
    else:need(not pending and source['pendingRun']==source['pendingGesture']=='' and source['elapsedMs']==0 and not source['timerActive'])
    motion=value['motion'];exact(motion,{'phoneLifecycleMotionVersion','instance','sequence','capturedEpochMs','keyboardPluginActive','upChannel','upPressed',
        'feetPosition','effectiveDrive','rawDrive','grounded'})
    need(type(motion['phoneLifecycleMotionVersion']) is int and motion['phoneLifecycleMotionVersion']==1 and nonce(motion['instance']) and integer(motion['sequence'],1)
        and integer(motion['capturedEpochMs'],1,value['capturedEpochMs']) and type(motion['keyboardPluginActive']) is bool and integer(motion['upChannel'],0,65535)
        and number(motion['upPressed'],0,1) and type(motion['grounded']) is bool)
    fresh(motion['capturedEpochMs'],epoch)
    for key,bound in (('feetPosition',1e6),('effectiveDrive',1e3),('rawDrive',1e3)):
        need(type(motion[key]) is list and len(motion[key])==3 and all(number(item,-bound,bound) for item in motion[key]))
    return value


def advance(before,after):
    need(all(after[key]==before[key] for key in ('runId','instance','processId')) and after['sequence']>before['sequence']
        and after['capturedEpochMs']>=before['capturedEpochMs'])
    a,b=before['source'],after['source'];need(a['instance']==b['instance'] and b['sequence']>a['sequence'] and b['capturedEpochMs']>=a['capturedEpochMs'])
    need(len(b['gestures'])>=len(a['gestures']))
    for old,new in zip(a['gestures'],b['gestures']):
        need(all(old[key]==new[key] for key in ('gestureId','runId','commandId','createdEpochMs')))
        if old['pressObserved']:need(new['pressObserved'] and new['pressEpochMs']==old['pressEpochMs'])
        if old['releaseObserved']:need(new==old)
    a,b=before['motion'],after['motion'];need(a['instance']==b['instance'] and a['upChannel']==b['upChannel'] and b['sequence']>=a['sequence']
        and b['capturedEpochMs']>=a['capturedEpochMs'])
    if a['sequence']==b['sequence']:need(a==b)


class PhoneLifecycleWorldSource:
    def __init__(self,send,read,clock_ms,guard,pid,*,intent=None,monotonic=time.monotonic,sleep=time.sleep):
        need(all(callable(fn) for fn in (send,read,clock_ms,guard,monotonic,sleep)) and integer(pid,1) and (intent is None or callable(intent)))
        self.send,self.read,self.clock_ms,self.guard,self.pid=send,read,clock_ms,guard,pid
        self.intent,self.monotonic,self.sleep,self.last=intent,monotonic,sleep,None
    def restore(self,frames):
        need(self.last is None and type(frames) is list and 0<len(frames)<=256)
        for frame in frames:
            request=dict(schemaVersion=1,commandId=frame['requestId'],runId=frame['runId'],action='phone-lifecycle-world-input',operation='observe',gestureId='')
            validate(frame,request,self.pid,frame['capturedEpochMs'])
            if self.last is not None:advance(self.last,frame)
            self.last=deepcopy(frame)
    def request(self,run,operation='observe',gesture_id=''):
        try:
            request=command(dict(schemaVersion=1,commandId=uuid.uuid4().hex,action='phone-lifecycle-world-input',operation=operation,runId=run,gestureId=gesture_id))
            need(self.guard() is not False);previous=started=self.monotonic();requested=self.clock_ms();need(integer(requested,1))
            if operation!='observe':need(self.intent is not None and self.intent(deepcopy(request)) is not False and self.guard() is not False)
            self.send(request)
            for attempt in range(51):
                need(self.guard() is not False);raw=self.read();need(type(raw) is str and len(raw.encode())<=65536)
                try:value=decode(raw) if raw else None
                except json.JSONDecodeError:value=None
                now=self.monotonic();need(number(now,previous,1e15) and now-started<5);previous=now
                if type(value) is dict and value.get('requestId')==request['commandId']:
                    validate(value,request,self.pid,self.clock_ms());need(value['requestedEpochMs']>=requested)
                    if self.last is not None:advance(self.last,value)
                    now=self.monotonic();need(number(now,previous,1e15) and now-started<5 and self.guard() is not False)
                    fresh(value['capturedEpochMs'],self.clock_ms());fresh(value['motion']['capturedEpochMs'],self.clock_ms())
                    self.last=deepcopy(value);return deepcopy(value)
                if attempt<50:self.sleep(.1)
        except Exception:raise NativeUIError('Original Phone lifecycle gesture or motion source is unavailable') from None
        raise NativeUIError('Original Phone lifecycle world source did not produce this request')
