"""Original Assets page/context and shared tablet loader/window observations."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
import math
import time
import uuid
from urllib.parse import urlsplit
from adapters.authentication_journey.login_source import qml_loads,accept_loads
from adapters.native_feature_observation import LIMIT,decode,exact,fresh,integer,need,number
from adapters.script_journey.history import canonical,MAX_RAW,MAX_FRAMES
from adapters.script_journey.files import nonce

VERSION=1
FILE='assets-pages.json'
COMMAND='files/overte-e2e/assets-pages-command.json'
IDENTITIES=('id','pageId','contextId','windowId','loaderId','componentSource','firstObservedEpochMs')
LIVENESS=('pageAlive','contextAlive','windowAlive','loaderAlive','contextValid')


def validate(value,request,pid,epoch):
    exact(request,{'schemaVersion','commandId','action'})
    need(type(request['schemaVersion']) is int and request['schemaVersion']==1 and nonce(request['commandId']) and request['action']=='observe')
    exact(value,{'schemaVersion','commandId','action','instance','generation','sourceSequence','lastCommandSequence',
        'elapsedMs','capturedEpochMs','processId','assetsPagesVersion','source'})
    need(type(value['schemaVersion']) is int and value['schemaVersion']==1 and value['commandId']==request['commandId']
        and value['action']=='observe' and nonce(value['instance']) and value['generation']==value['instance']
        and integer(value['sourceSequence'],1) and type(value['lastCommandSequence']) is int and value['lastCommandSequence']==0
        and integer(value['elapsedMs']) and type(value['processId']) is int and value['processId']==pid
        and type(value['assetsPagesVersion']) is int and value['assetsPagesVersion']==VERSION)
    fresh(value['capturedEpochMs'],epoch);source=value['source']
    exact(source,{'complete','tabletShown','onHomeScreen','pages','qmlLoads'})
    need(source['complete'] is True and all(type(source[key]) is bool for key in ('tabletShown','onHomeScreen'))
        and type(source['pages']) is list and len(source['pages'])<=64)
    qml_loads(source['qmlLoads']);ids=set();visible=[]
    for row in source['pages']:
        exact(row,set(IDENTITIES)|set(LIVENESS)|{'inCurrentTree','visible'})
        need(all(nonce(row[key]) for key in ('id','pageId','contextId','windowId','loaderId')) and row['id'] not in ids
            and integer(row['firstObservedEpochMs'],1,value['capturedEpochMs'])
            and all(type(row[key]) is bool for key in (*LIVENESS,'inCurrentTree','visible'))
            and type(row['componentSource']) is str and 1<=len(row['componentSource'])<=4096)
        url=urlsplit(row['componentSource']);need(url.scheme in ('file','qrc') and not url.netloc and not url.query
            and not url.fragment and url.path.endswith('/hifi/dialogs/TabletAssetServer.qml'))
        need(not row['contextValid'] or row['contextAlive'])
        need(row['pageAlive'] or not row['inCurrentTree'] and not row['visible'])
        if row['visible'] and row['inCurrentTree']:visible.append(row['id'])
        ids.add(row['id'])
    need(len(visible)<=1 and (not source['onHomeScreen'] or not visible));return value


def accept(previous,current):
    if previous is None:return
    need(current['instance']==previous['instance'] and current['sourceSequence']>previous['sourceSequence']
        and current['elapsedMs']>=previous['elapsedMs'] and current['capturedEpochMs']>=previous['capturedEpochMs'])
    old,new=previous['source'],current['source'];need(len(new['pages'])>=len(old['pages']))
    for before,after in zip(old['pages'],new['pages']):
        need(all(after[key]==before[key] for key in IDENTITIES) and all(before[key] or not after[key] for key in LIVENESS))
    accept_loads(old['qmlLoads'],new['qmlLoads'])


class PicoAssetsPages:
    def __init__(self,send,original,clock_ms,guard,pid,*,source_lock=None,monotonic=time.monotonic,sleep=time.sleep):
        from adapters.script_journey.lock import ScriptSourceLock
        need(all(callable(item) for item in (send,original,clock_ms,guard,monotonic,sleep)) and integer(pid,1)
            and (source_lock is None or isinstance(source_lock,ScriptSourceLock)))
        self.send,self.original,self.clock_ms,self.guard,self.pid=send,original,clock_ms,guard,pid
        self.source_lock,self.monotonic,self.sleep=source_lock,monotonic,sleep
        self.history=[];self.last=self.last_raw=self.last_sha256=None
    def restore(self,history):
        need(not self.history and self.last is None and type(history) is list and len(history)<=128)
        previous=None;seen=set()
        for frame in history:
            exact(frame,{'command','raw','sha256'});need(type(frame['raw']) is str and len(frame['raw'].encode())<=LIMIT
                and hashlib.sha256(frame['raw'].encode()).hexdigest()==frame['sha256'])
            value=decode(frame['raw']);validate(value,frame['command'],self.pid,value['capturedEpochMs'])
            need(value['commandId'] not in seen);seen.add(value['commandId']);accept(previous,value);previous=value
        need(len(history)<=MAX_FRAMES and len(canonical(history))<=MAX_RAW)
        self.history=deepcopy(history);self.last=deepcopy(previous)
        if history:self.last_raw,self.last_sha256=history[-1]['raw'],history[-1]['sha256']
    def capture(self):
        if self.source_lock is not None:
            with self.source_lock.held():return self._capture()
        return self._capture() # Explicit host boundary, never product discovery.
    def _capture(self):
        need(len(self.history)<128 and self.guard() is not False)
        request=dict(schemaVersion=1,commandId=uuid.uuid4().hex,action='observe')
        started=previous=self.monotonic();requested=self.clock_ms();need(number(started,0,1e15) and integer(requested,1))
        self.send(request)
        for attempt in range(51):
            need(self.guard() is not False);raw=self.original();need(type(raw) is str and len(raw.encode())<=LIMIT)
            try:value=decode(raw) if raw else None
            except json.JSONDecodeError:value=None
            now=self.monotonic();need(number(now,previous,1e15) and now-started<5);previous=now
            if type(value) is dict and value.get('commandId')==request['commandId']:
                validate(value,request,self.pid,self.clock_ms());need(value['capturedEpochMs']>=requested);accept(self.last,value)
                result=deepcopy(value);retained=deepcopy(value);digest=hashlib.sha256(raw.encode()).hexdigest()
                history=deepcopy(self.history)+[dict(command=deepcopy(request),raw=raw,sha256=digest)]
                need(len(history)<=MAX_FRAMES and len(canonical(history))<=MAX_RAW)
                need(self.guard() is not False);epoch=self.clock_ms();ended=self.monotonic()
                need(number(ended,previous,1e15) and ended-started<5)
                fresh(value['capturedEpochMs'],max(epoch,requested+math.ceil((ended-started)*1000)))
                self.last,self.last_raw,self.last_sha256,self.history=retained,raw,digest,history
                return result
            if attempt<50:self.sleep(.1)
        need(False)


def bind_source(adapter,target,native,*,source_lock=None):
    lock=adapter._script_journey()._lock(target,source_lock)
    def guard():lock.assert_held();native.guard()
    def send(request):
        guard();adapter.adb.write_debug_app_file(target,'org.overte.pico',COMMAND,json.dumps(request,separators=(',',':'))+'\n');guard()
    return PicoAssetsPages(send,lambda:adapter.adb.read_debug_app_file(target,'org.overte.pico','files/overte-e2e/'+FILE,attempts=1),
        native.clock_ms,guard,native.pid,source_lock=lock,monotonic=native.monotonic,sleep=native.sleep)
