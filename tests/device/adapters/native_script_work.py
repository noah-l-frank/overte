"""Original queued manager-thread timer/callback inventory, never an ACK verdict."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import re
import time
import uuid

from adapters.native_feature_observation import decode,exact,fresh,integer,need,number
from adapters.native_script_membership import validate as membership,accept as accept_membership
from adapters.native_script_observation import validate_code
from adapters.normal_ui import NativeUIError
from feature_journeys.contract import typed_equal

VERSION=1
FILE='feature-script-work.json'


def command(value,*,ios=False):
    exact(value,{'schemaVersion','commandId','action','managerInstance'})
    need(type(ios) is bool and type(value['schemaVersion']) is int and value['schemaVersion']==1
        and value['action']=='feature-script-work-observe' and type(value['commandId']) is str
        and re.fullmatch(('ios-' if ios else '')+'[0-9a-f]{32}',value['commandId'])
        and type(value['managerInstance']) is str and re.fullmatch('[0-9a-f]{32}',value['managerInstance']))
    return value


def members(source):
    return dict(complete=True,revision=source['revision'],managers=[row['membership'] for row in source['workers']])


def validate(value,request,pid,epoch,*,previous=None):
    need(type(request) is dict and type(request.get('commandId')) is str)
    command(request,ios=request['commandId'].startswith('ios-'))
    exact(value,{'schemaVersion','requestId','instance','sequence','processId','requestedEpochMs','capturedEpochMs','source'})
    need(type(value['schemaVersion']) is int and value['schemaVersion']==1 and value['requestId']==request['commandId']
        and type(value['instance']) is str and re.fullmatch('[0-9a-f]{32}',value['instance'])
        and integer(value['sequence'],1,1_000_000_000) and integer(pid,1) and type(value['processId']) is int and value['processId']==pid
        and integer(value['requestedEpochMs'],1) and integer(value['capturedEpochMs'],value['requestedEpochMs'])
        and value['capturedEpochMs']-value['requestedEpochMs']<5000)
    fresh(value['capturedEpochMs'],epoch)
    source=value['source'];exact(source,{'complete','revision','manager','code','work','workers'})
    need(source['complete'] is True and integer(source['revision']) and type(source['workers']) is list and len(source['workers'])<=128)
    for row in source['workers']:
        exact(row,{'membership','running','stopping','finished','done'})
        need(all(type(row[key]) is bool for key in ('running','stopping','finished','done')))
    membership(members(source),value['capturedEpochMs'])
    selected=source['manager']
    membership(dict(complete=True,revision=1,managers=[selected]),value['capturedEpochMs'])
    need(selected['assigned'] and selected['instance']==request['managerInstance'])
    own=[row for row in source['workers'] if row['membership']['instance']==selected['instance']]
    need(len(own)==1 and typed_equal(own[0]['membership'],selected) and own[0]['running']
        and not any(own[0][key] for key in ('stopping','finished','done')))
    validate_code(source['code'],value['capturedEpochMs']);need(source['code']['submitted'])
    work=source['work']
    exact(work,{'scriptWorkVersion','requestId','sequence','requestedEpochMs','capturedEpochMs',
        'signalCallbacks','timerCallbacks','evaluating','timers'})
    need(type(work['scriptWorkVersion']) is int and work['scriptWorkVersion']==VERSION and work['requestId']==request['commandId']
        and integer(work['sequence'],1,1_000_000_000) and integer(work['requestedEpochMs'],1)
        and integer(work['capturedEpochMs'],1) and work['requestedEpochMs']==value['requestedEpochMs']
        and selected['assignedEpochMs']<=source['code']['submittedEpochMs']<=work['requestedEpochMs']
        <=work['capturedEpochMs']<=value['capturedEpochMs']
        and all(integer(work[key],0,1_000_000_000) for key in ('signalCallbacks','timerCallbacks'))
        and type(work['evaluating']) is bool and type(work['timers']) is list and len(work['timers'])<=256)
    fresh(work['capturedEpochMs'],epoch)
    handles=[]
    for timer in work['timers']:
        exact(timer,{'handle','active','singleShot','intervalMs','remainingMs'})
        need(integer(timer['handle'],1,2**31-1) and type(timer['active']) is bool and type(timer['singleShot']) is bool
            and integer(timer['intervalMs'],-2**31,2**31-1) and integer(timer['remainingMs'],-1,2**31-1)
            and (timer['remainingMs']>=0 if timer['active'] else timer['remainingMs']==-1))
        handles.append(timer['handle'])
    need(handles==sorted(set(handles)))
    if previous is not None:
        old_request=dict(schemaVersion=1,commandId=previous['requestId'],action='feature-script-work-observe',
            managerInstance=previous['source']['manager']['instance'])
        validate(previous,old_request,pid,previous['capturedEpochMs'])
        need(value['instance']==previous['instance'] and value['sequence']>previous['sequence']
            and work['sequence']>previous['source']['work']['sequence'] and value['requestId']!=previous['requestId']
            and value['requestedEpochMs']>=previous['capturedEpochMs']
            and typed_equal(selected,previous['source']['manager']) and typed_equal(source['code'],previous['source']['code']))
        accept_membership(members(previous['source']),members(source),set(),value['capturedEpochMs'])
    return value


class NativeScriptWork:
    def __init__(self,send,original,clock_ms,guard,pid,*,ios=False,monotonic=time.monotonic,sleep=time.sleep):
        need(all(callable(value) for value in (send,original,clock_ms,guard,monotonic,sleep)) and integer(pid,1) and type(ios) is bool)
        self.send,self.original,self.clock_ms,self.guard,self.pid=send,original,clock_ms,guard,pid
        self.ios,self.monotonic,self.sleep=ios,monotonic,sleep;self.last=None;self.retired=set()

    def restore(self,frames):
        need(type(frames) is list and len(frames)<=1024 and self.last is None and not self.retired)
        previous=None;retired=set()
        for frame in frames:
            request=dict(schemaVersion=1,commandId=frame['requestId'],action='feature-script-work-observe',
                managerInstance=frame['source']['manager']['instance'])
            command(request,ios=self.ios);validate(frame,request,self.pid,frame['capturedEpochMs'],previous=previous)
            _members,retired=accept_membership(members(previous['source']) if previous else None,members(frame['source']),retired,frame['capturedEpochMs'])
            previous=deepcopy(frame)
        self.last,self.retired=previous,retired

    def read(self,manager_instance,after_sequence=0):
        try:
            need(integer(after_sequence) and (self.last is None or after_sequence>=self.last['sequence']) and self.guard() is not False)
            started=previous=self.monotonic();need(number(started,0,1e15));barrier=self.clock_ms();need(integer(barrier,1))
            request=dict(schemaVersion=1,commandId=('ios-' if self.ios else '')+uuid.uuid4().hex,
                action='feature-script-work-observe',managerInstance=manager_instance)
            command(request,ios=self.ios);self.send(deepcopy(request))
            for attempt in range(51):
                need(self.guard() is not False);raw=self.original()
                try:value=decode(raw) if raw else None
                except json.JSONDecodeError:value=None
                now=self.monotonic();need(number(now,previous,1e15) and now-started<5 and self.guard() is not False);previous=now
                if type(value) is dict and value.get('requestId')==request['commandId']:
                    epoch=self.clock_ms();need(integer(epoch,barrier));validate(value,request,self.pid,epoch,previous=self.last)
                    need(value['sequence']>after_sequence and value['requestedEpochMs']>=barrier)
                    _members,retired=accept_membership(members(self.last['source']) if self.last else None,members(value['source']),self.retired,value['capturedEpochMs'])
                    accepted,returned=deepcopy(value),deepcopy(value)
                    need(self.guard() is not False)
                    final=self.monotonic();need(number(final,previous,1e15) and final-started<5
                        and max(epoch-value['source']['work']['capturedEpochMs'],
                            barrier-value['source']['work']['capturedEpochMs']+(final-started)*1000)<=1500)
                    self.last,self.retired=accepted,retired;return returned
                if attempt<50:self.sleep(.1)
        except Exception:raise NativeUIError('Original manager-thread Script work is unavailable or invalid') from None
        raise NativeUIError('Original manager-thread Script work did not produce this request')
