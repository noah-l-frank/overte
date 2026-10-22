"""Immutable original Pico left-stick publication history and layer provenance.

No command/ACK counts as a gesture. Native started/neutral events plus their
original intercepted-query status must join the same durable session envelope.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
import re
import time
import uuid
from adapters.native_feature_observation import LIMIT,decode,exact,fresh,integer,need,number
from adapters.pico4.lifecycle_source import nonce
from openxr_input.android_transport import validate_native_status,TransportError

VERSION=1
FILE='feature-lifecycle-gesture.json'
ACTION='feature-lifecycle-gesture-observe'
CAUSES={'axis-transition','first-observed-active','action-published','axis-change','action-not-published',
    'focus-out','deactivated','display-inactive','not-registered','no-session','init-failed','sync-failed','vector-query-failed'}
KINDS={'started','changed','neutral','unavailable','resumed'}


def sample(value):
    exact(value,{'actionActive','raw','mapped','mappedValid','changedSinceLastSync','lastChangeTimeNs'})
    need(all(type(value[key]) is bool for key in ('actionActive','mappedValid','changedSinceLastSync')))
    for key in ('raw','mapped'):
        need(type(value[key]) is list and len(value[key])==2 and all(number(v,-1,1) for v in value[key]))
    stamp=value['lastChangeTimeNs'];need(type(stamp) is str and re.fullmatch(r'-?(?:0|[1-9][0-9]{0,18})',stamp)
        and -(2**63)<=int(stamp)<2**63)
    return value


def known(value):
    return value['actionActive'] and value['mappedValid'] and abs(value['raw'][0]-value['mapped'][0])<=1e-6 and abs(value['raw'][1]+value['mapped'][1])<=1e-6


def nonzero(value):return any(abs(v)>=.01 for v in value['raw'])


def stream(value,epoch):
    need(type(value) is dict)
    if not value:return None
    exact(value,{'raw','sha256'});need(type(value['raw']) is str and len(value['raw'].encode())<=16384
        and value['sha256']==hashlib.sha256(value['raw'].encode()).hexdigest())
    original=decode(value['raw']);need(type(original.get('schemaVersion')) is int and original['schemaVersion']==1)
    try:validate_native_status(original)
    except TransportError:need(False)
    need(integer(original['acceptedSequence'],1,4294967295) and original['acceptedNonce']
        and original['updatedEpochMs']<=epoch+250)
    return original


def validate(value,request,pid,epoch):
    exact(value,{'gestureObservationVersion','commandId','runId','instance','sequence','processId','capturedEpochMs','source'})
    need(type(value['gestureObservationVersion']) is int and value['gestureObservationVersion']==VERSION
        and nonce(value['commandId']) and value['commandId']==request['commandId']
        and nonce(value['runId']) and value['runId']==request['runId'] and nonce(value['instance'])
        and integer(value['sequence'],1) and integer(value['processId'],1) and value['processId']==pid)
    fresh(value['capturedEpochMs'],epoch)
    source=value['source'];exact(source,{'backend','createdEpochMs','frameSequence','frameEpochMs','frameElapsedMs','known','current','activeGesture','events'})
    need(source['backend']=='pico-openxr-left-thumbstick-publication' and integer(source['createdEpochMs'],1,value['capturedEpochMs'])
        and integer(source['frameSequence'],1) and integer(source['frameEpochMs'],source['createdEpochMs'],value['capturedEpochMs'])
        and integer(source['frameElapsedMs']) and type(source['known']) is bool and type(source['activeGesture']) is str
        and (source['activeGesture']=='' or nonce(source['activeGesture'])) and type(source['events']) is list
        and 1<=len(source['events'])<=512)
    sample(source['current']);active='';ids=set();gestures=set();prior=None;last_known=False
    for index,event in enumerate(source['events'],1):
        exact(event,{'id','eventSequence','kind','gestureId','cause','frameSequence','occurredEpochMs','elapsedMs','sample','stream'})
        need(nonce(event['id']) and event['id'] not in ids and integer(event['eventSequence'],index,index)
            and event['kind'] in KINDS and event['cause'] in CAUSES and type(event['gestureId']) is str
            and (event['gestureId']=='' or nonce(event['gestureId']))
            and integer(event['frameSequence'],1,source['frameSequence'])
            and integer(event['occurredEpochMs'],source['createdEpochMs'],source['frameEpochMs'])
            and integer(event['elapsedMs'],0,source['frameElapsedMs']))
        ids.add(event['id']);sample(event['sample']);stream(event['stream'],event['occurredEpochMs'])
        if prior is not None:
            need(event['frameSequence']>prior['frameSequence'] and event['occurredEpochMs']>=prior['occurredEpochMs'] and event['elapsedMs']>=prior['elapsedMs'])
        if event['kind']=='unavailable':need(event['gestureId']==active);last_known=False
        else:
            need(known(event['sample']))
            if event['kind']=='started':
                need(active=='' and nonce(event['gestureId']) and event['gestureId'] not in gestures and nonzero(event['sample']))
                active=event['gestureId'];gestures.add(active)
            elif event['kind']=='neutral':
                need(event['gestureId']==active and not nonzero(event['sample']));active=''
            else:
                need(active and event['gestureId']==active and nonzero(event['sample']))
                if event['kind']=='resumed':need(not last_known)
                else:need(last_known and prior is not None and event['sample']['raw']!=prior['sample']['raw'])
            last_known=True
        prior=event
    need(source['activeGesture']==active)
    if source['known']:
        need(known(source['current']) and last_known and bool(active)==nonzero(source['current']))
    else:need(not last_known)
    return value


def accept(previous,current):
    if previous is not None:
        need(current['instance']==previous['instance'] and current['runId']==previous['runId'] and current['processId']==previous['processId']
            and current['sequence']>previous['sequence'] and current['commandId']!=previous['commandId']
            and current['capturedEpochMs']>=previous['capturedEpochMs'])
        old,new=previous['source'],current['source']
        need(new['createdEpochMs']==old['createdEpochMs'] and new['frameSequence']>=old['frameSequence']
            and new['frameEpochMs']>=old['frameEpochMs'] and new['frameElapsedMs']>=old['frameElapsedMs']
            and len(new['events'])>=len(old['events']) and new['events'][:len(old['events'])]==old['events'])
        if new['frameSequence']==old['frameSequence']:need(new==old)
    return deepcopy(current)


def consumed(event,envelope):
    """Original intercepted-query receipt, not acceptedSequence/ACK alone."""
    native=stream(event['stream'],event['occurredEpochMs']);need(native is not None and event['kind']=='started')
    need(native['acceptedNonce']==envelope['sessionNonce'] and native['acceptedSequence']==envelope['sequence']
        and native['activeCommandId']==envelope['commands'][0]['id'] and native['vectorAppliedSequence']==envelope['sequence']
        and native['state']=='active' and native['enabled'] is True and native['detail']=='vector-consumed'
        and 0<=event['occurredEpochMs']-native['updatedEpochMs']<=1500
        and abs(native['leftThumbstickAppliedX']-event['sample']['raw'][0])<=1e-6
        and abs(native['leftThumbstickAppliedY']-event['sample']['raw'][1])<=1e-6)
    return native


class PicoLifecycleGesture:
    def __init__(self,send,original,clock_ms,guard,pid,*,monotonic=time.monotonic,sleep=time.sleep,source_lock=None):
        need(all(callable(f) for f in (send,original,clock_ms,guard,monotonic,sleep)) and integer(pid,1))
        self.send,self.original,self.clock_ms,self.guard,self.pid=send,original,clock_ms,guard,pid
        from adapters.script_journey.lock import ScriptSourceLock
        need(source_lock is None or isinstance(source_lock,ScriptSourceLock));self.source_lock=source_lock
        self.monotonic,self.sleep=monotonic,sleep;self.previous,self.last_raw,self.last_sha256=None,None,None
    def restore(self,original):
        validate(original,original,self.pid,original['capturedEpochMs']);need(self.guard() is not False)
        need(self.previous is None or self.previous==original);self.previous=deepcopy(original)
    def capture(self,run):
        if self.source_lock is not None:
            with self.source_lock.held():return self._capture(run)
        return self._capture(run)  # Explicit unbound host/native boundary only.

    def _capture(self,run):
        need(nonce(run) and self.guard() is not False)
        request=dict(schemaVersion=1,commandId=uuid.uuid4().hex,action=ACTION,runId=run)
        started=previous=self.monotonic();requested=self.clock_ms();need(number(started,0,1e15) and integer(requested,1))
        self.send(request)
        for attempt in range(51):
            need(self.guard() is not False);raw=self.original();need(type(raw) is str and len(raw.encode())<=LIMIT)
            try:value=decode(raw) if raw else None
            except json.JSONDecodeError:value=None
            now=self.monotonic();need(number(now,0,1e15) and previous<=now and now-started<5);previous=now
            need(self.guard() is not False)
            if type(value) is dict and value.get('commandId')==request['commandId']:
                epoch=self.clock_ms();validate(value,request,self.pid,epoch);need(value['capturedEpochMs']>=requested)
                accepted=accept(self.previous,value);need(self.guard() is not False)
                completed=self.monotonic();need(number(completed,0,1e15) and previous<=completed and completed-started<5
                    and max(epoch-value['capturedEpochMs'],requested-value['capturedEpochMs']+(completed-started)*1000)<=1500)
                if value['source']['known']:
                    frame=value['source']['frameEpochMs'];need(max(epoch-frame,requested-frame+(completed-started)*1000)<=1500)
                self.previous,self.last_raw,self.last_sha256=accepted,raw,hashlib.sha256(raw.encode()).hexdigest();return deepcopy(value)
            if attempt<50:self.sleep(.1)
        need(False)
