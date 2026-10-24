"""Original bounded native Qt-state/Chat/VR-keyboard history; no lifecycle input."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
import time
import uuid
from adapters.native_feature_observation import LIMIT,decode,exact,fresh,integer,need,number
from adapters.normal_ui import NativeUIError
from adapters.pico4 import lifecycle_source as ui
from adapters.script_journey.lock import ScriptSourceLock

VERSION=1
FILE='lifecycle-background-observation.json'
COMMAND='files/overte-e2e/lifecycle-background-command.json'


def command(value):
    need(type(value) is dict);operation=value.get('operation')
    need(operation in ('observe','arm','release'))
    fields={'schemaVersion','commandId','action','operation','runId'}
    if operation!='observe':fields|={'ownerInstance','intentSequence'}
    exact(value,fields);need(type(value['schemaVersion']) is int and value['schemaVersion']==1
        and value['action']=='feature-lifecycle-background' and ui.nonce(value['commandId']) and ui.nonce(value['runId']))
    if operation!='observe':need(ui.nonce(value['ownerInstance']) and integer(value['intentSequence'],1))


def validate(value,request,pid,epoch):
    command(request)
    exact(value,{'lifecycleBackgroundVersion','commandId','runId','instance','sequence','processId','capturedEpochMs',
        'lastIntentSequence','performed','available','active','timerActive','released','expired','ownerRunId',
        'originalId','armedEpochMs','armCommandId','releaseCommandId','frames'})
    need(type(value['lifecycleBackgroundVersion']) is int and value['lifecycleBackgroundVersion']==VERSION
        and value['commandId']==request['commandId'] and value['runId']==request['runId'] and ui.nonce(value['instance'])
        and value['processId']==pid and integer(value['processId'],1) and integer(value['sequence'],1)
        and integer(value['lastIntentSequence']) and all(type(value[key]) is bool for key in ('performed','available','active','timerActive','released','expired')))
    fresh(value['capturedEpochMs'],epoch)
    if request['operation']=='observe':need(not value['performed'])
    else:need(value['instance']==request['ownerInstance'] and value['lastIntentSequence']==request['intentSequence'])
    if value['performed']:
        need(value['ownerRunId']==request['runId'])
        if request['operation']=='arm':need(value['armCommandId']==request['commandId'] and value['active'] and value['timerActive'])
        else:need(value['releaseCommandId']==request['commandId'] and value['released'] and not value['active'] and not value['timerActive'])
    need(type(value['frames']) is list and len(value['frames'])<=96 and type(value['originalId']) is str
        and (not value['originalId'] or ui.nonce(value['originalId'])) and integer(value['armedEpochMs']))
    if value['ownerRunId']=='':
        need(not value['frames'] and not value['originalId'] and value['armedEpochMs']==0 and value['armCommandId']==value['releaseCommandId']==''
            and not any(value[key] for key in ('active','timerActive','released','expired')))
        return value
    need(value['ownerRunId']==request['runId'] and value['armedEpochMs']>0 and ui.nonce(value['armCommandId'])
        and (ui.nonce(value['releaseCommandId']) if value['released'] else value['releaseCommandId']==''))
    need(value['active']==value['timerActive'] and (not value['released'] or not value['active'])
        and (not value['expired'] or not value['available'] and not value['active'])
        and (not value['active'] or value['available']))
    if value['available']:need(value['frames'] and value['originalId'])
    previous=None;seen=set()
    for index,frame in enumerate(value['frames']):
        exact(frame,{'frameId','sequence','capturedEpochMs','elapsedMs','cause','applicationState','signalSequence',
            'uiInstance','uiSequence','uiCapturedEpochMs','tabletShown','onHomeScreen','currentId','focusedEditors','editor','keyboard'})
        need(ui.nonce(frame['frameId']) and frame['frameId'] not in seen and integer(frame['sequence'],1) and frame['sequence']==index+1
            and integer(frame['capturedEpochMs'],value['armedEpochMs'],value['capturedEpochMs']) and integer(frame['elapsedMs'])
            and frame['cause'] in ('arm','timer','query','application-state','release')
            and frame['applicationState'] in ('active','inactive','hidden','suspended') and integer(frame['signalSequence'])
            and ui.nonce(frame['uiInstance']) and integer(frame['uiSequence'],1)
            and integer(frame['uiCapturedEpochMs'],value['armedEpochMs'],frame['capturedEpochMs'])
            and frame['capturedEpochMs']-frame['uiCapturedEpochMs']<=1500
            and all(type(frame[key]) is bool for key in ('tabletShown','onHomeScreen'))
            and type(frame['currentId']) is str and (not frame['currentId'] or ui.nonce(frame['currentId']))
            and integer(frame['focusedEditors'],0,64))
        seen.add(frame['frameId']);row=frame['editor'];ui.editors([row],request['runId'],frame['uiCapturedEpochMs'])
        need(row['id']==value['originalId'] and row['kind']=='chat' and row['current']==(frame['currentId']==row['id'])
            and frame['focusedEditors']>=int(row['focused']) and (not row['current'] or frame['tabletShown'] and not frame['onHomeScreen']))
        keyboard=frame['keyboard'];exact(keyboard,{'instance','sequence','created','enabled','visible','raised','keyCount','pressedKeys'})
        need(ui.nonce(keyboard['instance']) and integer(keyboard['sequence'],1)
            and all(type(keyboard[key]) is bool for key in ('created','enabled','visible','raised'))
            and integer(keyboard['keyCount'],0,1021) and integer(keyboard['pressedKeys'],0,keyboard['keyCount']))
        if previous is None:
            need(frame['cause']=='arm' and frame['applicationState']=='active' and row['current'] and row['visible'])
        else:
            need(frame['cause']!='arm' and all(row[key]==previous['editor'][key] for key in ui.IDENTITIES)
                and all(previous['editor'][key] or not row[key] for key in ui.LIVENESS)
                and frame['capturedEpochMs']>=previous['capturedEpochMs'] and frame['elapsedMs']>=previous['elapsedMs']
                and frame['elapsedMs']-value['frames'][0]['elapsedMs']<=20000
                and frame['uiInstance']==previous['uiInstance'] and frame['uiSequence']>previous['uiSequence']
                and frame['uiCapturedEpochMs']>=previous['uiCapturedEpochMs']
                and keyboard['instance']==previous['keyboard']['instance'] and keyboard['sequence']>previous['keyboard']['sequence']
                and frame['signalSequence']==previous['signalSequence']+(frame['cause']=='application-state'))
        previous=frame
    return value


def accept(previous,current):
    if previous is None:return
    need(current['instance']==previous['instance'] and current['processId']==previous['processId']
        and current['runId']==previous['runId'] and current['sequence']>previous['sequence']
        and current['capturedEpochMs']>=previous['capturedEpochMs'] and current['lastIntentSequence']>=previous['lastIntentSequence']
        and current['frames'][:len(previous['frames'])]==previous['frames'] and len(current['frames'])>=len(previous['frames'])
        and (not previous['released'] or current['released']) and (not previous['expired'] or current['expired'])
        and (previous['available'] or not current['available']))
    if previous['ownerRunId']:
        need(all(current[key]==previous[key] for key in ('ownerRunId','originalId','armedEpochMs','armCommandId')))
    if previous['released']:need(current['releaseCommandId']==previous['releaseCommandId'])


class NativeLifecycleBackground:
    def __init__(self,send,original,clock_ms,guard,pid,source_lock,*,intent=None,monotonic=time.monotonic,sleep=time.sleep):
        need(all(callable(f) for f in (send,original,clock_ms,guard,monotonic,sleep)) and integer(pid,1)
            and isinstance(source_lock,ScriptSourceLock) and (intent is None or callable(intent)))
        self.send,self.original,self.clock_ms,self.guard,self.pid,self.source_lock=send,original,clock_ms,guard,pid,source_lock
        self.intent,self.monotonic,self.sleep=intent,monotonic,sleep;self.last=self.last_raw=self.last_sha256=None
    def restore(self,raw):
        """Validate original historical bytes; never return them as a fresh read."""
        with self.source_lock.held():
            need(self.last is None and self.guard() is not False and type(raw) is str and len(raw.encode('utf-8'))<=LIMIT)
            value=decode(raw);need(type(value) is dict);operation='observe'
            if value.get('performed'):
                operation='arm' if value.get('commandId')==value.get('armCommandId') else 'release'
            request=dict(schemaVersion=1,commandId=value['commandId'],action='feature-lifecycle-background',operation=operation,runId=value['runId'])
            if operation!='observe':request.update(ownerInstance=value['instance'],intentSequence=value['lastIntentSequence'])
            validate(value,request,self.pid,value['capturedEpochMs']);accepted=deepcopy(value);digest=hashlib.sha256(raw.encode()).hexdigest()
            need(self.guard() is not False);self.last,self.last_raw,self.last_sha256=accepted,raw,digest
    def exchange(self,request):
        command(request)
        try:
            with self.source_lock.held():
                need(self.guard() is not False);started=previous=self.monotonic();requested=self.clock_ms()
                need(number(started,0,1e15) and integer(requested,1))
                if request['operation']!='observe':
                    need(self.intent is not None);self.intent(deepcopy(request));need(self.guard() is not False)
                    fence=getattr(self,'phase_fence',None)
                    if fence is not None:fence.check()
                self.send(deepcopy(request))
                for attempt in range(51):
                    need(self.guard() is not False);raw=self.original();need(type(raw) is str and len(raw.encode('utf-8'))<=LIMIT)
                    try:value=decode(raw) if raw else None
                    except json.JSONDecodeError:value=None
                    now=self.monotonic();need(number(now,0,1e15) and previous<=now and now-started<5);previous=now
                    if type(value) is dict and value.get('commandId')==request['commandId']:
                        epoch=self.clock_ms();validate(value,request,self.pid,epoch);need(value['capturedEpochMs']>=requested);accept(self.last,value)
                        result=deepcopy(value);accepted=deepcopy(value);digest=hashlib.sha256(raw.encode()).hexdigest()
                        need(self.guard() is not False);epoch=self.clock_ms();completed=self.monotonic()
                        need(integer(epoch,1) and number(completed,0,1e15) and previous<=completed and completed-started<5
                            and -250<=epoch-value['capturedEpochMs']
                            and max(epoch-value['capturedEpochMs'],requested-value['capturedEpochMs']+(completed-started)*1000)<=1500)
                        self.last,self.last_raw,self.last_sha256=accepted,raw,digest;return result
                    if attempt<50:self.sleep(.1)
                need(False)
        except Exception:raise NativeUIError('Original Lifecycle background history unavailable; intents retained, none repeated') from None
    def read(self,run):
        return self.exchange(dict(schemaVersion=1,commandId=uuid.uuid4().hex,action='feature-lifecycle-background',operation='observe',runId=run))
    def _operate(self,run,operation):
        need(operation in ('arm','release') and self.last is not None and self.last['runId']==run)
        request=dict(schemaVersion=1,commandId=uuid.uuid4().hex,action='feature-lifecycle-background',operation=operation,runId=run,
            ownerInstance=self.last['instance'],intentSequence=self.last['lastIntentSequence']+1)
        result=self.exchange(request);need(result['performed'])
        return result
    def arm(self,run):
        need(self.last is not None and self.last['ownerRunId']=='' and self.last['available'])
        result=self._operate(run,'arm');need(result['available'] and result['active'] and result['timerActive']);return result
    def release_owned(self,run,original_arm):
        command(original_arm);need(original_arm['operation']=='arm' and original_arm['runId']==run)
        current=self.read(run)
        need(current['ownerRunId']==run and current['instance']==original_arm['ownerInstance']
            and current['armCommandId']==original_arm['commandId'] and current['lastIntentSequence']==original_arm['intentSequence']
            and not current['released'])
        result=self._operate(run,'release');need(result['released'] and not result['active'] and not result['timerActive']);return result


def bind_source(adapter,target,native,*,source_lock=None,intent=None):
    source_lock=adapter._script_journey()._lock(target,source_lock)
    def send(request):
        native.guard()
        fence=getattr(observer,'phase_fence',None)
        if request['operation']!='observe' and fence is not None:
            from adapters.pico4.lifecycle_operations import LifecycleInputFence
            if type(fence) is LifecycleInputFence:fence.check()
        adapter.adb.write_debug_app_file(target,'org.overte.pico',COMMAND,json.dumps(request,separators=(',',':'))+'\n');native.guard()
    observer=NativeLifecycleBackground(send,lambda:adapter.adb.read_debug_app_file(target,'org.overte.pico','files/overte-e2e/'+FILE,attempts=1),
        native.clock_ms,native.guard,native.pid,source_lock,intent=intent,monotonic=native.monotonic,sleep=native.sleep)
    return observer
