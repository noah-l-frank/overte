"""Closed dedicated peer stimuli and original native pose/input measurements.

A consumed peer send is never a delivery observation. NativeChatObservation
must independently acquire actual primary and peer messageReceived events.
"""
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
HEX='[0-9a-f]{32}';SHA='[0-9a-f]{64}'
OPERATIONS={'inspect','lease','send-domain-reply','send-domain-hidden','send-local-reply','send-local-distant','restore'}


def command(value):
    exact(value,{'schemaVersion','commandId','action','operation','runId'})
    need(type(value['schemaVersion']) is int and value['schemaVersion']==1 and value['action']=='feature-chat-peer'
         and type(value['operation']) is str and value['operation'] in OPERATIONS
         and all(type(value[k]) is str and re.fullmatch(HEX,value[k]) for k in ('commandId','runId')))
    return value


def pose(value):
    exact(value,{'x','y','z'});need(all(number(v,-1000000,1000000) for v in value.values()));return value


def validate(value,request,pid,epoch):
    command(request)
    exact(value,{'chatPeerVersion','commandId','runId','operation','instance','sequence','processId','capturedEpochMs','source'})
    need(type(value['chatPeerVersion']) is int and value['chatPeerVersion']==VERSION
         and all(value[k]==request[k] for k in ('commandId','runId','operation'))
         and type(value['instance']) is str and re.fullmatch(HEX,value['instance'])
         and integer(value['sequence'],1) and integer(value['processId'],1) and value['processId']==pid)
    fresh(value['capturedEpochMs'],epoch);source=value['source']
    exact(source,{'selfSha256','mixerPresent','mixerSha256','leasePresent','admitted','restored','position',
                  'originalPosition','inputSequence','lastInput','handback'})
    need(type(source['selfSha256']) is str and re.fullmatch(SHA,source['selfSha256'])
         and all(type(source[k]) is bool for k in ('mixerPresent','leasePresent','admitted','restored'))
         and type(source['mixerSha256']) is str and (bool(re.fullmatch(SHA,source['mixerSha256'])) if source['mixerPresent'] else source['mixerSha256']=='')
         and integer(source['inputSequence'],0,64) and (not source['restored'] or source['admitted'] and not source['leasePresent'])
         and (not source['admitted'] or source['leasePresent'] or source['restored']))
    pose(source['position'])
    if source['admitted']:pose(source['originalPosition'])
    else:need(source['originalPosition']=={} and source['inputSequence']==0 and source['lastInput']=={} and source['handback']=={})
    if source['inputSequence']:
        event=source['lastInput'];exact(event,{'sequence','operation','capturedEpochMs','position','payloadSha256'})
        need(integer(event['sequence'],1,64) and event['sequence']==source['inputSequence']
             and event['operation'] in OPERATIONS-{'inspect','lease','restore'}
             and integer(event['capturedEpochMs'],1) and event['capturedEpochMs']<=value['capturedEpochMs']
             and type(event['payloadSha256']) is str and re.fullmatch(SHA,event['payloadSha256']))
        pose(event['position'])
    else:need(source['lastInput']=={})
    if source['restored']:
        handback=source['handback'];exact(handback,{'capturedEpochMs','position','inputSequence'})
        need(integer(handback['capturedEpochMs'],1) and handback['capturedEpochMs']<=value['capturedEpochMs']
             and handback['inputSequence']==source['inputSequence'] and handback['position']==source['originalPosition'])
        pose(handback['position'])
    else:need(source['handback']=={})
    if request['operation']=='lease':need(source['leasePresent'] and not source['restored'])
    if request['operation']=='restore':need(source['restored'] and not source['leasePresent'])
    if request['operation'].startswith('send-'):
        need(source['admitted'] and source['leasePresent'] and source['mixerPresent']
             and source['lastInput']['operation']==request['operation'])
    return value


class NativeChatPeer:
    def __init__(self,send,read,clock_ms,guard,pid,*,monotonic=time.monotonic,sleep=time.sleep):
        need(all(callable(v) for v in (send,read,clock_ms,guard,monotonic,sleep)) and integer(pid,1))
        self.send,self.original,self.clock_ms,self.guard,self.pid=send,read,clock_ms,guard,pid
        self.monotonic,self.sleep=monotonic,sleep;self.last=None

    def restore_source(self,value):
        request=dict(schemaVersion=1,action='feature-chat-peer',**{k:value[k] for k in ('commandId','operation','runId')})
        validate(value,request,self.pid,value['capturedEpochMs']);need(self.last is None);self.last=deepcopy(value)

    def perform(self,run,operation):
        try:
            request=dict(schemaVersion=1,commandId=uuid.uuid4().hex,action='feature-chat-peer',operation=operation,runId=run)
            command(request);need(self.guard() is not False)
            if operation.startswith('send-') or operation=='restore':
                need(self.last is not None and self.last['runId']==run and self.last['source']['admitted'])
            started=prior=self.monotonic();need(number(started,0,1e15));requested=self.clock_ms();need(integer(requested,1))
            self.send(request)
            for attempt in range(51):
                need(self.guard() is not False);raw=self.original()
                try:value=decode(raw) if raw else None
                except json.JSONDecodeError:value=None
                if type(value) is dict and value.get('commandId')==request['commandId']:
                    validate(value,request,self.pid,self.clock_ms());need(value['capturedEpochMs']>=requested)
                    if self.last is not None:
                        old=self.last;current=value['source'];previous=old['source']
                        need(value['runId']==old['runId'] and value['instance']==old['instance'] and value['sequence']>old['sequence']
                             and value['capturedEpochMs']>=old['capturedEpochMs'] and current['selfSha256']==previous['selfSha256']
                             and current['inputSequence']>=previous['inputSequence']
                             and (not previous['admitted'] or current['admitted'] and current['originalPosition']==previous['originalPosition'])
                             and (not previous['restored'] or current['restored'] and current['handback']==previous['handback']))
                        if current['inputSequence']==previous['inputSequence']:need(current['lastInput']==previous['lastInput'])
                        if operation.startswith('send-'):
                            need(current['inputSequence']==previous['inputSequence']+1 and current['lastInput']['capturedEpochMs']>=requested)
                        if operation=='restore' and not previous['restored']:
                            need(current['handback']['capturedEpochMs']>=requested)
                    elif operation.startswith('send-') or operation=='restore':need(False)
                    now=self.monotonic();need(number(now,0,1e15) and prior<=now and now-started<5 and self.guard() is not False)
                    self.last=deepcopy(value);return value
                now=self.monotonic();need(number(now,0,1e15) and prior<=now);prior=now
                if now-started>=5 or attempt==50:break
                self.sleep(min(.1,5-(now-started)))
        except Exception:raise NativeUIError('Original dedicated Chat peer source failed') from None
        raise NativeUIError('Original dedicated Chat peer source is unavailable')
