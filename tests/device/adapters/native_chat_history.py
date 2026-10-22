"""Original empty-history cleanup lease; no desired settings in commands."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import re
import time
import uuid
from adapters.native_feature_observation import decode,exact,fresh,integer,need,number
from adapters.normal_ui import NativeUIError
VERSION=1
FILE='feature-chat-history.json'


def command(value):
    exact(value,{'schemaVersion','commandId','action','operation','runId'})
    need(type(value['schemaVersion']) is int and value['schemaVersion']==1 and value['action']=='feature-chat-history'
         and value['operation'] in ('inspect','capture','restore','retire')
         and all(type(value[k]) is str and re.fullmatch('[0-9a-f]{32}',value[k]) for k in ('commandId','runId')))
    return value


def validate(value,request,pid,epoch):
    command(request)
    exact(value,{'chatHistoryVersion','commandId','runId','operation','instance','sequence','processId','capturedEpochMs','source'})
    need(type(value['chatHistoryVersion']) is int and value['chatHistoryVersion']==VERSION
         and all(value[k]==request[k] for k in ('commandId','runId','operation'))
         and type(value['instance']) is str and re.fullmatch('[0-9a-f]{32}',value['instance'])
         and integer(value['sequence'],1) and integer(value['processId'],1) and value['processId']==pid)
    fresh(value['capturedEpochMs'],epoch);source=value['source']
    exact(source,{'scopePresent','retired','restored','originalKind','originalSha256','currentSha256','configSha256','openedEpochMs','handbackEpochMs','closed'})
    need(all(type(source[k]) is bool for k in ('scopePresent','retired','restored','closed'))
         and all(type(source[k]) is str and re.fullmatch('[0-9a-f]{64}',source[k]) for k in ('currentSha256','configSha256'))
         and integer(source['openedEpochMs']) and integer(source['handbackEpochMs'])
         and not (source['scopePresent'] and source['retired']) and (not source['retired'] or source['restored']))
    if source['scopePresent'] or source['retired']:
        need(source['originalKind'] in ('unset','null','empty-string','array','string-list')
             and type(source['originalSha256']) is str and re.fullmatch('[0-9a-f]{64}',source['originalSha256'])
             and 0<source['openedEpochMs']<=value['capturedEpochMs'])
    else:need(source['originalKind']==source['originalSha256']=='' and source['openedEpochMs']==0 and not source['restored'])
    if source['restored']:
        need(source['openedEpochMs']<=source['handbackEpochMs']<=value['capturedEpochMs'] and source['currentSha256']==source['originalSha256'])
    else:need(source['handbackEpochMs']==0)
    if request['operation']=='capture':need(source['scopePresent'] and source['closed'] and not source['retired'] and not source['restored'])
    if request['operation']=='restore':need(source['scopePresent'] and source['restored'] and source['closed'])
    if request['operation']=='retire':need(source['retired'] and source['closed'])
    return value


class NativeChatHistory:
    def __init__(self,send,read,clock_ms,guard,pid,*,monotonic=time.monotonic,sleep=time.sleep):
        need(all(callable(v) for v in (send,read,clock_ms,guard,monotonic,sleep)) and integer(pid,1))
        self.send,self.original,self.clock_ms,self.guard,self.pid=send,read,clock_ms,guard,pid
        self.monotonic,self.sleep=monotonic,sleep;self.last=None

    def restore_source(self,value):
        request=dict(schemaVersion=1,action='feature-chat-history',**{k:value[k] for k in ('commandId','operation','runId')})
        validate(value,request,self.pid,value['capturedEpochMs']);need(self.last is None);self.last=deepcopy(value)

    def perform(self,run,operation):
        try:
            request=dict(schemaVersion=1,commandId=uuid.uuid4().hex,action='feature-chat-history',operation=operation,runId=run)
            command(request);need(self.guard() is not False)
            if operation in ('restore','retire'):
                need(self.last is not None and self.last['runId']==run and (self.last['source']['scopePresent'] or self.last['source']['retired']))
            started=prior=self.monotonic();need(number(started,0,1e15));requested=self.clock_ms();need(integer(requested,1));self.send(request)
            for attempt in range(51):
                need(self.guard() is not False);raw=self.original()
                try:value=decode(raw) if raw else None
                except json.JSONDecodeError:value=None
                if type(value) is dict and value.get('commandId')==request['commandId']:
                    validate(value,request,self.pid,self.clock_ms());need(value['capturedEpochMs']>=requested)
                    if self.last is not None:
                        old=self.last;before=old['source'];actual=value['source']
                        need(value['runId']==old['runId'] and value['instance']==old['instance'] and value['sequence']>old['sequence']
                             and value['capturedEpochMs']>=old['capturedEpochMs'] and actual['configSha256']==before['configSha256'])
                        if before['scopePresent'] or before['retired']:
                            need(all(actual[k]==before[k] for k in ('originalKind','originalSha256','openedEpochMs')))
                        if before['restored']:need(actual['restored'] and actual['handbackEpochMs']==before['handbackEpochMs'])
                        if before['retired']:need(actual['retired'])
                    now=self.monotonic();need(number(now,0,1e15) and prior<=now and now-started<5 and self.guard() is not False)
                    self.last=deepcopy(value);return value
                now=self.monotonic();need(number(now,0,1e15) and prior<=now);prior=now
                if now-started>=5 or attempt==50:break
                self.sleep(min(.1,5-(now-started)))
        except Exception:raise NativeUIError('Original Chat empty-history ownership failed') from None
        raise NativeUIError('Original Chat empty-history ownership is unavailable')
