"""Exact original readonly request cancellation/retirement, never another read."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
import time
import uuid
from adapters.native_feature_observation import decode,exact,fresh,integer,need,number
from adapters.normal_ui import NativeUIError
from adapters.pico4.assets_source import command,nonce,effective_epoch

FILE='feature-pico-assets-read-retirement.json'


def validate(value,request,pid,epoch):
    exact(request,{'schemaVersion','commandId','action','original'});original=command(request['original'])
    need(type(request['schemaVersion']) is int and request['schemaVersion']==1 and nonce(request['commandId'])
        and request['action']=='feature-pico-assets-read-retire')
    exact(value,{'schemaVersion','requestId','runId','instance','sequence','processId','requestedEpochMs','capturedEpochMs','source'})
    need(type(value['schemaVersion']) is int and value['schemaVersion']==1 and value['requestId']==request['commandId']
        and value['runId']==original['runId'] and nonce(value['instance']) and integer(value['sequence'],1,512)
        and type(value['processId']) is int and value['processId']==pid
        and integer(value['requestedEpochMs'],1) and integer(value['capturedEpochMs'],value['requestedEpochMs'])
        and value['capturedEpochMs']-value['requestedEpochMs']<5000)
    fresh(value['capturedEpochMs'],epoch);source=value['source']
    flags={'requestAlive','finishedConnected','destroyedConnected','finishedCaptureAlive','destroyedCaptureAlive','cancellationAlive'}
    exact(source,{'picoAssetsReadRetirementVersion','originalRequestId','runId','retired','originalRequestedEpochMs',
        'originalCapturedEpochMs','originalDestroyedEpochMs','retiredEpochMs'}|flags)
    need(type(source['picoAssetsReadRetirementVersion']) is int and source['picoAssetsReadRetirementVersion']==1
        and source['originalRequestId']==original['commandId'] and source['runId']==original['runId']
        and source['retired'] is True and all(source[key] is False for key in flags)
        and integer(source['originalRequestedEpochMs'],1)
        and integer(source['originalCapturedEpochMs'],source['originalRequestedEpochMs'])
        and integer(source['originalDestroyedEpochMs'],source['originalCapturedEpochMs'])
        and integer(source['retiredEpochMs'],source['originalDestroyedEpochMs'],value['capturedEpochMs']))
    return value


class AssetsReadRetirement:
    def __init__(self,send,read,clock_ms,guard,pid,*,monotonic=time.monotonic,sleep=time.sleep):
        need(all(callable(item) for item in (send,read,clock_ms,guard,monotonic,sleep)) and integer(pid,1))
        self.send,self.original,self.clock_ms,self.guard,self.pid=send,read,clock_ms,guard,pid
        self.monotonic,self.sleep=monotonic,sleep;self.last=self.last_raw=self.last_sha256=None;self.history=[]
    def read(self,original):
        try:
            command(original);request=dict(schemaVersion=1,commandId=uuid.uuid4().hex,action='feature-pico-assets-read-retire',original=deepcopy(original))
            need(len(self.history)<128 and self.guard() is not False)
            started=previous=self.monotonic();need(number(started,0,1e15));requested=self.clock_ms();need(integer(requested,1));self.send(request)
            for attempt in range(51):
                need(self.guard() is not False);raw=self.original();need(type(raw) is str and len(raw.encode())<=262144)
                try:value=decode(raw) if raw else None
                except json.JSONDecodeError:value=None
                need(self.guard() is not False);current=self.monotonic();need(number(current,previous,1e15) and current-started<5);previous=current
                if type(value) is dict and value.get('requestId')==request['commandId']:
                    validate(value,request,self.pid,effective_epoch(self.clock_ms,requested,started,current));need(value['requestedEpochMs']>=requested)
                    if self.last is not None:need(value['instance']==self.last['instance'] and value['sequence']>self.last['sequence'] and value['capturedEpochMs']>=self.last['capturedEpochMs'])
                    need(self.guard() is not False);current=self.monotonic();need(number(current,previous,1e15) and current-started<5)
                    fresh(value['capturedEpochMs'],effective_epoch(self.clock_ms,requested,started,current))
                    self.last=deepcopy(value);self.last_raw=raw;self.last_sha256=hashlib.sha256(raw.encode()).hexdigest()
                    self.history.append(dict(command=deepcopy(request),raw=raw,sha256=self.last_sha256));return deepcopy(value)
                if attempt<50:self.sleep(.1)
        except Exception:raise NativeUIError('Original Pico Assets readonly resources remain unresolved') from None
        raise NativeUIError('Original Pico Assets readonly resources remain pending')
