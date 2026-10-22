"""Original VR editor/context inventory, with no input or generation requests."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
import re
import time
import uuid
from adapters.native_feature_observation import LIMIT, decode, exact, fresh, integer, need, number
from adapters.native_chat_view import vr_keyboard, measured_keyboard
from feature_journeys.fixtures import context

VERSION=1
FILE='lifecycle-ui-observation.json'
COMMAND='files/overte-e2e/lifecycle-ui-command.json'
LIVENESS=('fieldAlive','pageAlive','contextAlive','windowAlive','loaderAlive')
IDENTITIES=('id','kind','fieldId','pageId','contextId','windowId','loaderId','firstObservedEpochMs')


def nonce(value):return type(value) is str and re.fullmatch('[0-9a-f]{32}',value) is not None


def editors(rows,run,epoch):
    need(type(rows) is list and len(rows)<=64)
    ids=set();current=[]
    for row in rows:
        exact(row,set(IDENTITIES)|set(LIVENESS)|{'alive','attached','visible','focused','current','text'})
        need(row['kind'] in ('create','chat','scripts') and row['id'] not in ids
            and all(nonce(row[key]) for key in ('id','fieldId','pageId','contextId','windowId','loaderId'))
            and integer(row['firstObservedEpochMs'],1,epoch)
            and all(type(row[key]) is bool for key in (*LIVENESS,'alive','attached','visible','focused','current'))
            and type(row['text']) is str and row['text'] in ('',*(context(run)[key] for key in ('unicode','reply','retry'))))
        ids.add(row['id'])
        need(row['alive']==any(row[key] for key in LIVENESS[:3]))
        if not row['fieldAlive']:need(not any(row[key] for key in ('attached','visible','focused','current')))
        if not row['pageAlive'] or not row['loaderAlive']:need(not row['attached'])
        if not row['windowAlive']:need(not row['visible'])
        if row['current']:need(all(row[key] for key in LIVENESS) and row['attached']);current.append(row['id'])
        else:need(row['text']=='')
    need(len(current)<=1)
    return current[0] if current else ''


def validate(value,request,pid,epoch):
    exact(value,{'lifecycleUiVersion','commandId','instance','sequence','processId','capturedEpochMs','runId','source'})
    need(type(value['lifecycleUiVersion']) is int and value['lifecycleUiVersion']==VERSION
        and value['commandId']==request['commandId'] and nonce(value['commandId'])
        and value['runId']==request['runId'] and nonce(value['runId']) and nonce(value['instance'])
        and integer(value['sequence'],1) and integer(value['processId'],1) and value['processId']==pid)
    fresh(value['capturedEpochMs'],epoch)
    source=value['source'];exact(source,{'complete','tabletShown','onHomeScreen','current','editors','keyboard'})
    need(source['complete'] is True and all(type(source[key]) is bool for key in ('tabletShown','onHomeScreen'))
        and type(source['current']) is str)
    current=editors(source['editors'],value['runId'],value['capturedEpochMs'])
    need(source['current']==current and (source['tabletShown'] or not current)
        and (not source['onHomeScreen'] or not current))
    vr_keyboard(source['keyboard'])
    return value


def summary(packet):
    value=packet['source'];keyboard=value['keyboard']
    return dict(lifecycleSourceStateVersion=1,runId=packet['runId'],instance=packet['instance'],
        sequence=packet['sequence'],capturedEpochMs=packet['capturedEpochMs'],
        editors=deepcopy(value['editors']),keyboardInstance=keyboard['instance'],keyboardSequence=keyboard['sequence'])


def validate_summary(value,run):
    exact(value,{'lifecycleSourceStateVersion','runId','instance','sequence','capturedEpochMs',
        'editors','keyboardInstance','keyboardSequence'})
    need(type(value['lifecycleSourceStateVersion']) is int and value['lifecycleSourceStateVersion']==1
        and value['runId']==run and nonce(run) and nonce(value['instance']) and integer(value['sequence'],1)
        and integer(value['capturedEpochMs'],1) and nonce(value['keyboardInstance']) and integer(value['keyboardSequence'],1))
    editors(value['editors'],run,value['capturedEpochMs']);return value


def accept(previous,current):
    validate_summary(current,current['runId'])
    if previous is not None:
        validate_summary(previous,current['runId'])
        need(current['instance']==previous['instance'] and current['sequence']>previous['sequence']
            and current['capturedEpochMs']>=previous['capturedEpochMs']
            and current['keyboardInstance']==previous['keyboardInstance']
            and current['keyboardSequence']>previous['keyboardSequence']
            and len(current['editors'])>=len(previous['editors']))
        for old,new in zip(previous['editors'],current['editors']):
            need(all(new[key]==old[key] for key in IDENTITIES)
                and all(old[key] or not new[key] for key in LIVENESS))
    return deepcopy(current)


def current_editor(packet):
    source=packet['source']
    return next((deepcopy(row) for row in source['editors'] if row['id']==source['current']),None)


class PicoLifecycleSource:
    def __init__(self,send,original,clock_ms,guard,pid,*,monotonic=time.monotonic,sleep=time.sleep,source_lock=None):
        need(all(callable(value) for value in (send,original,clock_ms,guard,monotonic,sleep)) and integer(pid,1))
        self.send,self.original,self.clock_ms,self.guard,self.pid=send,original,clock_ms,guard,pid
        from adapters.script_journey.lock import ScriptSourceLock
        need(source_lock is None or isinstance(source_lock,ScriptSourceLock));self.source_lock=source_lock
        self.monotonic,self.sleep=monotonic,sleep
        self.previous,self.last_raw,self.last_sha256=None,None,None

    def restore(self,previous):
        validate_summary(previous,previous['runId']);need(self.guard() is not False)
        if self.previous is not None:need(self.previous==previous)
        self.previous=deepcopy(previous)

    def capture(self,run):
        if self.source_lock is not None:
            with self.source_lock.held():return self._capture(run)
        return self._capture(run)  # Explicit unbound host/native boundary only.

    def _capture(self,run):
        need(nonce(run) and self.guard() is not False)
        request=dict(schemaVersion=1,commandId=uuid.uuid4().hex,action='observe',runId=run)
        started=previous=self.monotonic();requested=self.clock_ms();need(number(started,0,1e15) and integer(requested,1))
        self.send(request) # Only one original query; never resend the nonce.
        for attempt in range(51):
            need(self.guard() is not False)
            raw=self.original();need(type(raw) is str and len(raw.encode('utf-8'))<=LIMIT)
            try:value=decode(raw) if raw else None
            except json.JSONDecodeError:value=None
            now=self.monotonic();need(number(now,0,1e15) and previous<=now and now-started<5);previous=now
            need(self.guard() is not False)
            if type(value) is dict and value.get('commandId')==request['commandId']:
                epoch=self.clock_ms();validate(value,request,self.pid,epoch)
                need(value['capturedEpochMs']>=requested)
                current=accept(self.previous,summary(value))
                need(self.guard() is not False)
                completed=self.monotonic();need(number(completed,0,1e15) and previous<=completed and completed-started<5
                    and max(epoch-value['capturedEpochMs'],
                        requested-value['capturedEpochMs']+(completed-started)*1000)<=1500)
                self.previous,self.last_raw,self.last_sha256=current,raw,hashlib.sha256(raw.encode()).hexdigest()
                return deepcopy(value)
            if attempt<50:self.sleep(.1)
        need(False)


def bind_source(adapter,target,native,*,source_lock=None):
    source_lock=adapter._script_journey()._lock(target,source_lock)
    def send(request):
        native.guard();adapter.adb.write_debug_app_file(target,'org.overte.pico',COMMAND,json.dumps(request,separators=(',',':'))+'\n');native.guard()
    return PicoLifecycleSource(send,lambda:adapter.adb.read_debug_app_file(target,'org.overte.pico',
        'files/overte-e2e/'+FILE,attempts=1),native.clock_ms,native.guard,native.pid,monotonic=native.monotonic,sleep=native.sleep,source_lock=source_lock)
