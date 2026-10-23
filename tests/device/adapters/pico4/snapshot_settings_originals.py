"""Original thirteen-key map/cache reads without initialization or setters."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import hashlib
import secrets
import time
from adapters.native_feature_observation import decode,exact,integer,need,number
from adapters.script_journey.lock import ScriptSourceLock
from adapters.pico4.snapshot_originals import nonce

VERSION=1
FILE='feature-pico-snapshot-settings-originals.json'
ACTION='feature-pico-snapshot-settings-originals'
LIMIT=65536
KEYS=sorted(('alsoTakeAnimatedSnapshot','snapshotFormat','previousSnapshotHref','previousSnapshotDomainID',
    'previousStillSnapPath','previousStillSnapStoryID','previousStillSnapBlastingDisabled','previousStillSnapHifiSharingDisabled','previousStillSnapUrl',
    'previousAnimatedSnapPath','previousAnimatedSnapStoryID','previousAnimatedSnapBlastingDisabled','previousAnimatedSnapHifiSharingDisabled'))


def validate(value,run,request,pid,epoch):
    exact(value,{'snapshotSettingsOriginalsVersion','commandId','runId','pid','sequence','capturedEpochMs','source'})
    need(type(value['snapshotSettingsOriginalsVersion']) is int and value['snapshotSettingsOriginalsVersion']==VERSION
        and nonce(run) and value['runId']==run and nonce(request) and value['commandId']==request and integer(value['pid'],1) and value['pid']==pid
        and integer(value['sequence'],1) and integer(value['capturedEpochMs'],1) and number(epoch,1,1e15) and -250<=epoch-value['capturedEpochMs']<=1500)
    source=value['source'];exact(source,{'snapshotInstance','managerInstance','entriesEpochMs','entries','formatCache','typedSerializedBase64','typedSha256'})
    need(nonce(source['snapshotInstance']) and nonce(source['managerInstance']) and integer(source['entriesEpochMs'],1,value['capturedEpochMs'])
        and value['capturedEpochMs']-source['entriesEpochMs']<=1500);exact(source['entries'],set(KEYS))
    for entry in source['entries'].values():
        exact(entry,{'present','value'});need(type(entry['present']) is bool and type(entry['value']) in (type(None),bool,str)
            and (entry['present'] or entry['value'] is None))
        if type(entry['value']) is str:need(len(entry['value'])<=4096 and '\0' not in entry['value'])
    cache=source['formatCache'];exact(cache,{'initialized','set','value','defaultValue'})
    need(type(cache['initialized']) is bool and type(cache['set']) is bool
        and all(type(cache[key]) is str and len(cache[key])<=4096 and '\0' not in cache[key] for key in ('value','defaultValue')))
    encoded=source['typedSerializedBase64'];need(type(encoded) is str and 0<len(encoded)<=43692)
    try:raw=base64.b64decode(encoded,validate=True)
    except Exception:need(False)
    need(0<len(raw)<=32768 and base64.b64encode(raw).decode()==encoded and type(source['typedSha256']) is str
        and hashlib.sha256(raw).hexdigest()==source['typedSha256'])
    return value


def accept(previous,current):
    validate(current,current['runId'],current['commandId'],current['pid'],current['capturedEpochMs'])
    if previous is not None:
        validate(previous,previous['runId'],previous['commandId'],previous['pid'],previous['capturedEpochMs'])
        need(current['runId']==previous['runId'] and current['pid']==previous['pid'] and current['commandId']!=previous['commandId']
            and current['sequence']>previous['sequence'] and current['capturedEpochMs']>=previous['capturedEpochMs']
            and all(current['source'][key]==previous['source'][key] for key in ('snapshotInstance','managerInstance'))
            and current['source']['entriesEpochMs']>=previous['source']['entriesEpochMs'])
    return deepcopy(current)


class PicoSnapshotSettingsOriginals:
    def __init__(self,send,read,clock_ms,guard,pid,source_lock,*,monotonic=time.monotonic,sleep=time.sleep):
        need(isinstance(source_lock,ScriptSourceLock) and integer(pid,1) and all(callable(value) for value in (send,read,clock_ms,guard,monotonic,sleep)))
        self.send,self.read,self.clock_ms,self.guard,self.pid,self.lock=send,read,clock_ms,guard,pid,source_lock
        self.monotonic,self.sleep=monotonic,sleep;self.previous=self.last_raw=self.last_sha256=self.anchor=None

    def restore(self,value):
        validate(value,value['runId'],value['commandId'],self.pid,value['capturedEpochMs']);need(self.previous is None or self.previous==value);self.previous=deepcopy(value)

    def capture(self,run):
        need(nonce(run))
        with self.lock.held():
            started=self.monotonic();requested=self.clock_ms();need(number(started,0,1e15) and integer(requested,1) and self.guard() is not False)
            command=secrets.token_hex(16);self.send(dict(schemaVersion=1,commandId=command,runId=run,action=ACTION))
            for attempt in range(31):
                raw=self.read();need(raw is None or type(raw) is str and len(raw.encode())<=LIMIT)
                if raw:
                    value=decode(raw)
                    if value.get('commandId')==command:
                        epoch=self.clock_ms();validate(value,run,command,self.pid,epoch);need(value['capturedEpochMs']>=requested)
                        current=accept(self.previous,value);need(self.guard() is not False);epoch=self.clock_ms();finished=self.monotonic()
                        oldest=min(value['capturedEpochMs'],value['source']['entriesEpochMs'])
                        need(number(finished,started,1e15) and -250<=epoch-oldest and max(epoch-oldest,requested-oldest+(finished-started)*1000)<=1500)
                        self.previous=current;self.last_raw=raw;self.last_sha256=hashlib.sha256(raw.encode()).hexdigest();self.anchor=dict(hostMonotonic=started,nativeEpochMs=requested)
                        return deepcopy(value)
                self.sleep(.05)
            need(False)

    def original(self):
        need(self.last_raw is not None and hashlib.sha256(self.last_raw.encode()).hexdigest()==self.last_sha256)
        return dict(raw=self.last_raw,sha256=self.last_sha256,anchor=deepcopy(self.anchor))
