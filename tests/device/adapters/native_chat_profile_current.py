"""Passive actual current Chat settings, without adopting a new profile owner."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import math
import time
import uuid

from adapters.native_chat_profile import fingerprints,hex_value
from adapters.native_feature_observation import decode,exact,fresh,integer,need,number
from adapters.normal_ui import NativeUIError

VERSION=1
FILE='feature-chat-profile-current.json'
LIMIT=32768


def command(value):
    exact(value,{'schemaVersion','commandId','runId','action'})
    need(type(value['schemaVersion']) is int and value['schemaVersion']==1
        and value['action']=='feature-chat-profile-current' and hex_value(value['commandId']) and hex_value(value['runId']))
    return value


def validate(value,request,pid,epoch):
    command(request)
    exact(value,{'chatProfileCurrentVersion','commandId','runId','instance','sequence','processId','capturedEpochMs',
        'current','settings','view'})
    need(type(value['chatProfileCurrentVersion']) is int and value['chatProfileCurrentVersion']==VERSION
        and all(value[key]==request[key] for key in ('commandId','runId')) and hex_value(value['instance'])
        and integer(value['sequence'],1) and integer(pid,1) and value['processId']==pid and integer(value['processId'],1))
    fingerprints(value['current']);need(value['current']['cache']==value['current']['worker']
        and value['current']['physical']['ArmoredChat-Messages']['empty'])
    exact(value['settings'],{'instance','writerInstance','mutationSequence','capturedEpochMs'})
    exact(value['view'],{'instance','sequence','capturedEpochMs'})
    need(all(hex_value(value['settings'][key]) for key in ('instance','writerInstance'))
        and integer(value['settings']['mutationSequence']) and hex_value(value['view']['instance']) and integer(value['view']['sequence'],1))
    for source in (value,value['settings'],value['view']):
        fresh(source['capturedEpochMs'],epoch);need(source['capturedEpochMs']<=value['capturedEpochMs'])
    return value


class NativeChatProfileCurrent:
    def __init__(self,send,original,clock_ms,guard,pid,*,monotonic=time.monotonic,sleep=time.sleep):
        need(all(callable(item) for item in (send,original,clock_ms,guard,monotonic,sleep)) and integer(pid,1))
        self.send,self.original,self.clock_ms,self.guard,self.pid=send,original,clock_ms,guard,pid
        self.monotonic,self.sleep=monotonic,sleep;self.last=self.last_raw=self.last_sha256=None

    def read(self,run):
        request=command(dict(schemaVersion=1,commandId=uuid.uuid4().hex,action='feature-chat-profile-current',runId=run))
        try:
            started=previous=self.monotonic();need(number(started,0,1e15) and self.guard() is not False)
            need(self.last is None or self.last['runId']==run)
            requested=self.clock_ms();need(integer(requested,1));self.send(deepcopy(request))
            for _attempt in range(51):
                need(self.guard() is not False);raw=self.original()
                need(type(raw) is str and len(raw.encode('utf-8'))<=LIMIT)
                value=decode(raw) if raw else None
                now=self.monotonic();need(number(now,previous,started+1.5));previous=now
                if type(value) is dict and value.get('commandId')==request['commandId']:
                    epoch=self.clock_ms();need(integer(epoch,requested));validate(value,request,self.pid,epoch)
                    need(min(value['settings']['capturedEpochMs'],value['view']['capturedEpochMs'])>=requested)
                    if self.last is not None:
                        old=self.last;need(value['runId']==old['runId'] and value['instance']==old['instance']
                            and value['sequence']>old['sequence'] and value['capturedEpochMs']>=old['capturedEpochMs']
                            and all(value['settings'][key]==old['settings'][key] for key in ('instance','writerInstance'))
                            and value['settings']['mutationSequence']>=old['settings']['mutationSequence']
                            and value['settings']['capturedEpochMs']>=old['settings']['capturedEpochMs']
                            and value['view']['instance']==old['view']['instance'] and value['view']['sequence']>old['view']['sequence']
                            and value['view']['capturedEpochMs']>=old['view']['capturedEpochMs'])
                    result,next_last=deepcopy(value),deepcopy(value);next_raw=raw.encode('utf-8');next_sha=hashlib.sha256(next_raw).hexdigest()
                    need(self.guard() is not False);measured=self.monotonic();final_epoch=self.clock_ms();ended=self.monotonic()
                    oldest=min(value[key]['capturedEpochMs'] for key in ('settings','view'))
                    need(number(measured,previous,started+1.5) and number(ended,measured,started+1.5) and integer(final_epoch,epoch))
                    fresh(oldest,final_epoch);need(final_epoch-oldest+math.ceil((ended-measured)*1000)<=1500)
                    self.last,self.last_raw,self.last_sha256=next_last,next_raw,next_sha;return result
                self.sleep(.05)
            need(False)
        except Exception:raise NativeUIError('Original current Chat profile is unavailable; no original ownership is adopted') from None
