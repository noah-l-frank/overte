"""Read-only original Snapshot VM event source; no capture/cancel authority."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import secrets
import time
from adapters.native_feature_observation import decode,exact,integer,need,number
from adapters.script_journey.lock import ScriptSourceLock
from adapters.pico4.snapshot_originals import nonce
from adapters.pico4.snapshot_script_history import validate as history,continuity

VERSION=2
READS=(1,2)
FILE='feature-snapshot-script-originals.json'
ACTION='feature-snapshot-script-originals'
LIMIT=65536


def validate(value,run,request,pid,epoch):
    need(type(value) is dict)
    exact(value,{'snapshotScriptOriginalsVersion','commandId','runId','sequence','pid','capturedEpochMs','history'}
        | ({'activeUploads'} if value.get('snapshotScriptOriginalsVersion')==2 else set()))
    need(type(value['snapshotScriptOriginalsVersion']) is int and value['snapshotScriptOriginalsVersion'] in READS
        and nonce(run) and value['runId']==run and nonce(request) and value['commandId']==request
        and integer(value['pid'],1) and value['pid']==pid and integer(value['sequence'],1)
        and integer(value['capturedEpochMs'],1) and number(epoch,1,1e15) and -250<=epoch-value['capturedEpochMs']<=1500)
    if value['snapshotScriptOriginalsVersion']==2:need(integer(value['activeUploads'],0,256))
    history(value['history'],value['capturedEpochMs'])
    return value


def accept(previous,current):
    validate(current,current['runId'],current['commandId'],current['pid'],current['capturedEpochMs'])
    if previous is not None:
        validate(previous,previous['runId'],previous['commandId'],previous['pid'],previous['capturedEpochMs'])
        need(current['snapshotScriptOriginalsVersion']==previous['snapshotScriptOriginalsVersion']
            and current['runId']==previous['runId'] and current['pid']==previous['pid']
            and current['sequence']>previous['sequence'] and current['commandId']!=previous['commandId']
            and current['capturedEpochMs']>=previous['capturedEpochMs'])
        continuity(previous['history'],current['history'])
    return deepcopy(current)


class PicoSnapshotScriptOriginals:
    def __init__(self,send,read,clock_ms,guard,pid,source_lock,*,monotonic=time.monotonic,sleep=time.sleep):
        need(isinstance(source_lock,ScriptSourceLock) and integer(pid,1) and all(callable(f) for f in (send,read,clock_ms,guard,monotonic,sleep)))
        self.send,self.read,self.clock_ms,self.guard,self.pid,self.lock=send,read,clock_ms,guard,pid,source_lock
        self.monotonic,self.sleep=monotonic,sleep;self.previous=self.last_raw=None
    def restore(self,value):
        validate(value,value['runId'],value['commandId'],self.pid,value['capturedEpochMs'])
        need(self.previous is None or self.previous==value)
        self.previous=deepcopy(value)
    def capture(self,run,operation='read'):
        need(nonce(run) and operation=='read')
        with self.lock.held():
            started=self.monotonic();requested=self.clock_ms();need(number(started,0,1e15) and integer(requested,1) and self.guard() is not False)
            request=secrets.token_hex(16);self.send(dict(schemaVersion=1,commandId=request,runId=run,action=ACTION))
            for attempt in range(31):
                raw=self.read();need(raw is None or type(raw) is str and len(raw.encode())<=LIMIT)
                if raw:
                    value=decode(raw)
                    if value.get('commandId')==request:
                        epoch=self.clock_ms();validate(value,run,request,self.pid,epoch)
                        need(value['capturedEpochMs']>=requested);accepted=accept(self.previous,value)
                        result=deepcopy(accepted);saved=deepcopy(accepted)
                        need(self.guard() is not False);final=self.clock_ms();completed=self.monotonic()
                        need(number(completed,started,1e15) and number(final,epoch,1e15) and -250<=final-value['capturedEpochMs']
                            and max(final-value['capturedEpochMs'],requested-value['capturedEpochMs']+(completed-started)*1000)<=1500)
                        self.previous,self.last_raw=saved,raw;return result
                need(self.monotonic()-started<5 and attempt<30);self.sleep(.1)
            need(False)
    def original(self):
        need(self.last_raw is not None)
        return dict(raw=self.last_raw,sha256=hashlib.sha256(self.last_raw.encode()).hexdigest())
