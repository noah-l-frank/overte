"""Bounded original native Scripts-field/event ownership transport.

These are private native inputs and raw observations, not full lifecycle facts.
The platform retains candidate/PID/source/native-clock binding around every I/O.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import re
import time
import uuid

from adapters.native_feature_observation import decode,exact,fresh,integer,need,number
from adapters.normal_ui import NativeUIError
from adapters.prepared_field_commit import component_url,validate as validate_commit

VERSION=1
FILE='feature-pending-commit-owner.json'
HEX=r'[0-9a-f]{32}'
INPUTS={'focus','type','hold','attempt'}


def command(value,*,ios=False):
    need(type(value) is dict and type(ios) is bool)
    operation=value.get('operation')
    need(type(operation) is str and operation in INPUTS|{'observe','release'})
    fields={'schemaVersion','commandId','action','operation','runId','eventId'}
    if operation!='observe':fields|={'ownerInstance','intentSequence'}
    if operation in INPUTS:fields|={'fieldToken','observationSequence'}
    exact(value,fields)
    need(type(value['schemaVersion']) is int and value['schemaVersion']==1
         and value['action']=='feature-pending-commit-owner'
         and type(value['commandId']) is str and re.fullmatch(('ios-' if ios else '')+HEX,value['commandId'])
         and type(value['runId']) is str and re.fullmatch(HEX,value['runId'])
         and type(value['eventId']) is str)
    event=value['eventId']
    if operation in ('attempt','release'):need(re.fullmatch(HEX,event))
    elif operation=='observe':need(not event or re.fullmatch(HEX,event))
    else:need(event=='')
    if operation!='observe':
        need(type(value['ownerInstance']) is str and re.fullmatch(HEX,value['ownerInstance'])
             and integer(value['intentSequence'],1,1_000_000_000))
    if operation in INPUTS:
        need(type(value['fieldToken']) is str and re.fullmatch(HEX,value['fieldToken'])
             and integer(value['observationSequence'],1,1_000_000_000))
    return value


def validate(value,request,pid,epoch_ms):
    command(request,ios=request['commandId'].startswith('ios-'))
    exact(value,{'pendingCommitOwnerVersion','commandId','operation','runId','instance','sequence','processId',
                 'canonicalComponentUrl','capturedEpochMs','lastIntentSequence','performed','current','commit','resources'})
    need(type(value['pendingCommitOwnerVersion']) is int and value['pendingCommitOwnerVersion']==VERSION
         and all(value[key]==request[key] for key in ('commandId','operation','runId'))
         and integer(pid,1) and integer(value['processId'],1) and value['processId']==pid
         and type(value['instance']) is str and re.fullmatch(HEX,value['instance'])
         and integer(value['sequence'],1) and integer(value['lastIntentSequence']) and type(value['performed']) is bool)
    fresh(value['capturedEpochMs'],epoch_ms)
    canonical=component_url(value['canonicalComponentUrl'])
    if request['operation']=='observe':need(value['performed'] is False)
    else:need(value['instance']==request['ownerInstance'] and value['lastIntentSequence']==request['intentSequence'])
    current=value['current']
    need(type(current) is dict and current.get('status') in ('none','unavailable','ready'))
    if current['status']!='ready':exact(current,{'status'})
    else:
        exact(current,{'status','token','componentUrl','text','focused','frame'})
        need(type(current['token']) is str and re.fullmatch(HEX,current['token'])
             and current['componentUrl']==canonical and type(current['focused']) is bool
             and type(current['text']) is str and current['text'] in ('','retry-'+request['runId'],'Overte ä Ω 東京 '+request['runId'])
             and type(current['frame']) is list and len(current['frame'])==4
             and all(number(item,0,16384) for item in current['frame'])
             and min(current['frame'][2:])>0)
    resources=value['resources']
    exact(resources,{'pendingRuns','archivedEvents'})
    need(type(resources['pendingRuns']) is list and len(resources['pendingRuns'])<=1
         and all(type(run) is str and re.fullmatch(HEX,run) for run in resources['pendingRuns'])
         and integer(resources['archivedEvents'],0,32))
    commit=value['commit'];need(type(commit) is dict)
    if commit:
        exact(commit,{'captureCommandId','fieldToken','observation'})
        need(type(commit['captureCommandId']) is str and re.fullmatch(r'(?:ios-)?'+HEX,commit['captureCommandId'])
             and type(commit['fieldToken']) is str and re.fullmatch(HEX,commit['fieldToken'])
             and resources['archivedEvents']>=1)
        validate_commit(commit['observation'],request['commandId'],request['runId'],pid,epoch_ms,original_component_url=canonical)
        need(commit['observation']['capturedEpochMs']<=value['capturedEpochMs']
             and commit['observation']['pending']==(request['runId'] in resources['pendingRuns']))
        if request['eventId']:need(commit['observation']['eventId']==request['eventId'])
    else:need(not request['eventId'] and request['runId'] not in resources['pendingRuns'])
    if value['performed'] and request['operation']=='hold':
        need(bool(commit) and commit['captureCommandId']==request['commandId'] and commit['observation']['pending'])
    if value['performed'] and request['operation'] in ('attempt','release'):
        need(bool(commit) and commit['observation']['pending'] is False)
    return value


class NativePendingCommitOwner:
    def __init__(self,send,original,clock_ms,guard,pid,*,ios=False,intent=None,monotonic=time.monotonic,sleep=time.sleep):
        need(all(callable(f) for f in (send,original,clock_ms,guard,monotonic,sleep))
             and integer(pid,1) and type(ios) is bool and (intent is None or callable(intent)))
        self.send,self.original,self.clock_ms,self.guard,self.pid=send,original,clock_ms,guard,pid
        self.ios,self.intent,self.monotonic,self.sleep=ios,intent,monotonic,sleep
        self.last=None

    def exchange(self,request):
        command(request,ios=self.ios)
        try:
            need(self.guard() is not False)
            started=self.monotonic();need(number(started,0,1e15));previous=started
            if request['operation']!='observe':
                need(self.intent is not None)
                need(self.intent(deepcopy(request)) is not False) # Durable owner intent precedes the one actual send.
                need(self.guard() is not False)
            self.send(deepcopy(request))
            for attempt in range(51):
                now=self.monotonic();need(number(now,0,1e15) and previous<=now and now-started<5)
                need(self.guard() is not False)
                raw=self.original()
                need(not raw or len(raw)<=32768)
                try:value=decode(raw) if raw else None
                except ValueError:value=None
                if type(value) is dict and value.get('commandId')==request['commandId']:
                    validate(value,request,self.pid,self.clock_ms())
                    if self.last is not None:
                        old=self.last
                        need(value['instance']==old['instance'] and value['sequence']>old['sequence']
                             and value['capturedEpochMs']>=old['capturedEpochMs']
                             and value['canonicalComponentUrl']==old['canonicalComponentUrl']
                             and value['lastIntentSequence']>=old['lastIntentSequence'])
                        if old['runId']==value['runId'] and old['commit']:
                            need(bool(value['commit']) and all(value['commit'][key]==old['commit'][key] for key in ('captureCommandId','fieldToken')))
                            a,b=old['commit']['observation'],value['commit']['observation']
                            need(all(a[key]==b[key] for key in ('instance','eventId','processId','createdEpochMs','source'))
                                 and b['sequence']>a['sequence'] and b['capturedEpochMs']>=a['capturedEpochMs']
                                 and b['elapsedMs']>=a['elapsedMs'] and len(b['events'])>=len(a['events'])
                                 and b['events'][:len(a['events'])]==a['events'])
                    now=self.monotonic();need(number(now,0,1e15) and previous<=now and now-started<5 and self.guard() is not False)
                    self.last=deepcopy(value);return value
                now=self.monotonic();need(number(now,0,1e15) and previous<=now);previous=now
                if now-started>=5 or attempt==50:break
                self.sleep(min(.1,5-(now-started)))
        except Exception:raise NativeUIError('Original native pending commit owner failed') from None
        raise NativeUIError('Original native pending commit owner failed')

    def read(self,run,event_id=''):
        return self.exchange(dict(schemaVersion=1,commandId=('ios-' if self.ios else '')+uuid.uuid4().hex,
            action='feature-pending-commit-owner',operation='observe',runId=run,eventId=event_id))

    def operate(self,run,operation,*,event_id='',observed=None):
        need(type(operation) is str and operation in INPUTS|{'release'} and self.last is not None and self.last['runId']==run and self.intent is not None)
        before=self.last if observed is None else observed
        need(before['instance']==self.last['instance'] and before['runId']==run)
        request=dict(schemaVersion=1,commandId=('ios-' if self.ios else '')+uuid.uuid4().hex,
            action='feature-pending-commit-owner',operation=operation,runId=run,eventId=event_id,
            ownerInstance=self.last['instance'],intentSequence=self.last['lastIntentSequence']+1)
        if operation in INPUTS:
            need(before['current']['status']=='ready')
            request.update(fieldToken=before['current']['token'],observationSequence=before['sequence'])
        return self.exchange(request)

    def _effect(self,run,token,predicate):
        started=self.monotonic();previous=started
        for _attempt in range(51):
            now=self.monotonic();need(number(now,0,1e15) and previous<=now and now-started<5);previous=now
            value=self.read(run)
            now=self.monotonic();need(number(now,0,1e15) and previous<=now and now-started<5);previous=now
            current=value['current']
            need(current['status']=='ready' and current['token']==token)
            if predicate(current):return value
            now=self.monotonic();need(number(now,0,1e15) and previous<=now);previous=now
            if now-started>=5:break
            self.sleep(min(.1,5-(now-started)))
        raise NativeUIError('Original native Scripts field effect is missing')

    def focus(self,run):
        before=self.read(run);need(before['current']['status']=='ready')
        result=self.operate(run,'focus');need(result['performed'])
        return self._effect(run,before['current']['token'],lambda field:field['focused'])

    def type_owned(self,run):
        before=self.read(run);need(before['current']['status']=='ready' and before['current']['focused'])
        result=self.operate(run,'type');need(result['performed'])
        return self._effect(run,before['current']['token'],lambda field:field['text']=='retry-'+run)

    def hold(self,run):
        before=self.read(run);need(before['current']['status']=='ready' and before['current']['focused']
                                   and before['current']['text']=='retry-'+run and not before['commit'])
        value=self.operate(run,'hold');need(value['performed'] and value['commit']['fieldToken']==before['current']['token'])
        return value

    def attempt_retired(self,run,event_id):
        before=self.read(run,event_id)
        need(before['current']['status']=='ready' and bool(before['commit'])
             and before['commit']['observation']['pending']
             and before['current']['token']!=before['commit']['fieldToken'])
        value=self.operate(run,'attempt',event_id=event_id);need(value['performed'])
        event=value['commit']['observation']['events'][-1]
        need(event['kind']=='rejected' and event['reason']=='context-retired')
        return self._effect(run,before['current']['token'],lambda field:field['text']=='' and not field['focused'])

    def release_owned(self,run,event_id):
        self.read(run,event_id)
        value=self.operate(run,'release',event_id=event_id)
        need(value['performed'] and value['commit']['observation']['pending'] is False
             and run not in value['resources']['pendingRuns'])
        return self.read(run,event_id)
