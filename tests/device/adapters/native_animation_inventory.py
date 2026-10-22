"""Passive actual animation-cache resources; no requested URL/name or prefetch."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import re
import time
import uuid

from adapters.native_animation_source import digest,model,nonce
from adapters.native_feature_observation import decode,exact,fresh,integer,need,number
from adapters.normal_ui import NativeUIError

VERSION=1
FILE='feature-animation-inventory.json'
LIMIT=262144


def command(value,*,ios=False):
    exact(value,{'schemaVersion','commandId','action'})
    need(type(ios) is bool and type(value['schemaVersion']) is int and value['schemaVersion']==1
        and value['action']=='feature-animation-inventory-observe' and type(value['commandId']) is str
        and re.fullmatch(('ios-' if ios else '')+'[0-9a-f]{32}',value['commandId']))
    return value


def validate(value,request,pid,epoch,*,previous=None):
    need(type(request) is dict and type(request.get('commandId')) is str)
    command(request,ios=request['commandId'].startswith('ios-'))
    exact(value,{'animationInventoryVersion','commandId','instance','sequence','processId','requestedEpochMs','capturedEpochMs','source'})
    need(type(value['animationInventoryVersion']) is int and value['animationInventoryVersion']==VERSION
        and value['commandId']==request['commandId'] and integer(pid,1) and integer(value['processId'],1) and value['processId']==pid
        and nonce(value['instance']) and integer(value['sequence'],1,1000000000) and integer(value['requestedEpochMs'],1)
        and integer(value['capturedEpochMs'],value['requestedEpochMs'],value['requestedEpochMs']+1500))
    fresh(value['capturedEpochMs'],epoch)
    source=value['source'];exact(source,{'complete','registrySlots','expiredSlots','resources'})
    need(source['complete'] is True and integer(source['registrySlots'],0,1024)
        and integer(source['expiredSlots'],0,source['registrySlots']) and type(source['resources']) is list and len(source['resources'])<=256)
    ids=[];models={};slots=source['expiredSlots']
    for row in source['resources']:
        exact(row,{'resourceInstance','urlSha256','loaded','failed','registrySlots','model'})
        need(nonce(row['resourceInstance']) and digest(row['urlSha256']) and type(row['loaded']) is bool and type(row['failed']) is bool
            and not (row['loaded'] and row['failed']) and integer(row['registrySlots'],1,1024))
        slots+=row['registrySlots'];ids.append(row['resourceInstance'])
        if row['model'] is not None:
            original=model(row['model'],value['capturedEpochMs']);key=original['instance']
            need(key not in models or models[key]==original);models[key]=original
    need(ids==sorted(set(ids)) and slots==source['registrySlots'])
    if previous is not None:
        old_request=dict(schemaVersion=1,commandId=previous['commandId'],action='feature-animation-inventory-observe')
        validate(previous,old_request,pid,previous['capturedEpochMs'])
        need(previous['instance']==value['instance'] and value['sequence']>previous['sequence'] and value['commandId']!=previous['commandId']
            and value['requestedEpochMs']>=previous['capturedEpochMs'])
    return value


class NativeAnimationInventory:
    def __init__(self,send,original,clock_ms,guard,pid,*,ios=False,monotonic=time.monotonic,sleep=time.sleep):
        need(all(callable(fn) for fn in (send,original,clock_ms,guard,monotonic,sleep)) and integer(pid,1) and type(ios) is bool)
        self.send,self.original,self.clock_ms,self.guard,self.pid=send,original,clock_ms,guard,pid
        self.ios,self.monotonic,self.sleep=ios,monotonic,sleep;self.last=None;self.models={};self.urls={}

    def accept(self,value):
        models,urls=deepcopy(self.models),deepcopy(self.urls)
        for row in value['source']['resources']:
            key=row['resourceInstance'];need(key not in urls or urls[key]==row['urlSha256']);urls[key]=row['urlSha256']
            if row['model'] is not None:
                original=row['model'];key=original['instance'];need(key not in models or models[key]==original);models[key]=deepcopy(original)
        need(len(models)<=1024 and len(urls)<=1024)
        return models,urls

    def restore(self,original):
        need(self.last is None and type(original) is dict and 'commandId' in original and 'capturedEpochMs' in original)
        request=dict(schemaVersion=1,commandId=original['commandId'],action='feature-animation-inventory-observe')
        command(request,ios=self.ios);validate(original,request,self.pid,original['capturedEpochMs'])
        models,urls=self.accept(original);self.models,self.urls,self.last=models,urls,deepcopy(original)

    def read(self,after_sequence):
        try:
            need(integer(after_sequence,0,1000000000) and (self.last is None or after_sequence>=self.last['sequence']) and self.guard() is not False)
            started=previous=self.monotonic();need(number(started,0,1e15));barrier=self.clock_ms();need(integer(barrier,1))
            request=dict(schemaVersion=1,commandId=('ios-' if self.ios else '')+uuid.uuid4().hex,action='feature-animation-inventory-observe')
            command(request,ios=self.ios);self.send(deepcopy(request))
            for attempt in range(51):
                need(self.guard() is not False);raw=self.original();need(type(raw) is str and len(raw.encode())<=LIMIT)
                try:value=decode(raw) if raw else None
                except json.JSONDecodeError:value=None
                now=self.monotonic();need(number(now,previous,1e15) and now-started<5 and self.guard() is not False);previous=now
                if type(value) is dict and value.get('commandId')==request['commandId']:
                    epoch=self.clock_ms();need(integer(epoch,barrier));validate(value,request,self.pid,epoch,previous=self.last)
                    need(value['sequence']>after_sequence and value['requestedEpochMs']>=barrier)
                    models,urls=self.accept(value);result=deepcopy(value);retained=deepcopy(result);need(self.guard() is not False)
                    final=self.monotonic();need(number(final,previous,1e15) and final-started<5)
                    need(max(epoch-value['capturedEpochMs'],barrier-value['capturedEpochMs']+(final-started)*1000)<=1500)
                    self.models,self.urls,self.last=models,urls,retained;return result
                if attempt<50:self.sleep(.1)
        except Exception:raise NativeUIError('Original animation cache inventory is unavailable or invalid') from None
        raise NativeUIError('Original animation cache inventory did not produce this acquisition')
