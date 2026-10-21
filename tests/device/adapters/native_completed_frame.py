"""Original fence-completed Vulkan frame and retained native consumer reads.

Metadata only: independent original pixels and feature effects are mandatory.
Every command requires caller-owned persisted intent before one HTTP delivery.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import re
import time
from adapters.native_feature_observation import decode,exact,fresh,integer,need,number
from adapters.normal_ui import NativeUIError
from adapters.render_view import recorded_view

VERSION=1
TRACE_VERSION=1
STORAGE_VERSION=1
FILE='feature-completed-frame.json'
LIMIT=65536


def nonce(value):return type(value) is str and re.fullmatch('ios-[0-9a-f]{32}',value) is not None


def command(value):
    exact(value,{'schemaVersion','commandId','action','requestId','operation'})
    need(type(value['schemaVersion']) is int and value['schemaVersion']==1 and value['action']=='feature-completed-frame'
         and nonce(value['commandId']) and nonce(value['requestId']) and value['operation'] in ('read','release','inspect'))
    return value


def extent(value):
    need(type(value) is list and len(value)==2 and all(integer(item,1,4096) for item in value)
         and value[0]*value[1]<=8388608)


def trace(value):
    exact(value,{'completedDrawTraceVersion','frameId','recordedEpochMs','recordedView','begunEpochMs','completedEpochMs',
        'drawSource','renderer','view','forwardBatches','forwardDrawCalls','hazeBatches','hazeDrawCalls','mirrorBatches','mirrorDrawCalls'})
    need(type(value['completedDrawTraceVersion']) is int and value['completedDrawTraceVersion']==TRACE_VERSION
         and type(value['frameId']) is str and re.fullmatch('[0-9a-f]{32}',value['frameId'])
         and value['drawSource']=='vulkan-api-issued' and value['renderer']=='forward' and value['view']=='main-mono')
    recorded_view(value['recordedView'])
    stamps=[value[key] for key in ('recordedEpochMs','begunEpochMs','completedEpochMs')]
    need(all(integer(stamp,1) for stamp in stamps) and stamps==sorted(stamps))
    for kind in ('forward','haze','mirror'):
        batches,draws=value[kind+'Batches'],value[kind+'DrawCalls']
        need(integer(batches,0,65536) and integer(draws,batches,1000000) and (batches==0)==(draws==0))
    need(value['hazeBatches']<=value['forwardBatches'] and value['hazeDrawCalls']<=value['forwardDrawCalls'])
    return value


def validate(value,request,pid,epoch):
    command(request);need(request['operation']=='read')
    return _validate_frame(value,request,pid,epoch,'completedFrameVersion')


def _validate_frame(value,request,pid,epoch,version_key,extra_fields=()):
    exact(value,{version_key,'commandId','requestId','instance','sequence','processId','requestedEpochMs','capturedEpochMs','source'})
    need(type(value[version_key]) is int and value[version_key]==VERSION
         and value['commandId']==request['commandId'] and value['requestId']==request['requestId']
         and type(value['instance']) is str and re.fullmatch('[0-9a-f]{32}',value['instance'])
         and integer(value['sequence'],1,1000000000) and integer(value['processId'],1) and value['processId']==pid
         and integer(value['requestedEpochMs'],1) and integer(value['capturedEpochMs'],value['requestedEpochMs']))
    fresh(value['capturedEpochMs'],epoch)
    source=value['source'];exact(source,{'backend','stage','view','sourceExtent','targetExtent','renderTrace','frameIndex',
        'submittedEpochMs','fenceObservedEpochMs'}|set(extra_fields))
    need(source['backend']=='vulkan' and source['stage']=='tone-map-before-hud' and source['view']=='main-mono'
         and integer(source['frameIndex'],0,2**32-1))
    extent(source['sourceExtent']);extent(source['targetExtent']);trace(source['renderTrace'])
    original=source['renderTrace']
    ordered=[value['requestedEpochMs'],original['recordedEpochMs'],original['begunEpochMs'],original['completedEpochMs'],
        source['submittedEpochMs'],source['fenceObservedEpochMs'],value['capturedEpochMs']]
    need(all(integer(stamp,1) for stamp in ordered) and ordered==sorted(ordered)
         and (bool(extra_fields) or source['fenceObservedEpochMs']==value['capturedEpochMs']) and ordered[-1]-ordered[0]<1500)
    fresh(ordered[0],epoch)
    return value


def storage(value,request,pid,epoch):
    command(request);need(request['operation'] in ('release','inspect'))
    return _validate_storage(value,request,pid,epoch,'frameStorageVersion')


def _validate_storage(value,request,pid,epoch,version_key,extra_fields=()):
    exact(value,{version_key,'commandId','requestId','operation','instance','sequence','processId',
        'requestedEpochMs','capturedEpochMs','source'})
    need(type(value[version_key]) is int and value[version_key]==STORAGE_VERSION
         and all(value[key]==request[key] for key in ('commandId','requestId','operation'))
         and type(value['instance']) is str and re.fullmatch('[0-9a-f]{32}',value['instance'])
         and integer(value['sequence'],1,1000000000) and integer(value['processId'],1) and value['processId']==pid
         and integer(value['requestedEpochMs'],1) and integer(value['capturedEpochMs'],value['requestedEpochMs'])
         and value['capturedEpochMs']-value['requestedEpochMs']<1500)
    fresh(value['capturedEpochMs'],epoch)
    source=value['source'];exact(source,{'retired','present','callbacks','gpuPending','metadataBytes'}
        |({'performed'} if request['operation']=='release' else set())|set(extra_fields))
    need(all(type(source[key]) is bool for key in ('retired','present','gpuPending'))
         and integer(source['callbacks'],0,1) and integer(source['metadataBytes'],0,LIMIT)
         and (not source['retired'] or not source['present']) and (source['present'] or source['metadataBytes']==0)
         and (request['operation']!='release' or type(source['performed']) is bool))
    return value


def absent(value):
    need(type(value) is dict)
    request=dict(schemaVersion=1,action='feature-completed-frame',**{key:value.get(key) for key in ('commandId','requestId','operation')})
    storage(value,request,value.get('processId'),value.get('capturedEpochMs')) # Historical integrity only.
    source=value['source']
    return source.get('retired') is True and source.get('present') is False and source.get('callbacks')==0 \
        and type(source.get('callbacks')) is int and source.get('gpuPending') is False and source.get('metadataBytes')==0 \
        and type(source.get('metadataBytes')) is int


class NativeCompletedFrame:
    command_validator=staticmethod(command)
    frame_validator=staticmethod(validate)
    storage_validator=staticmethod(storage)
    limit=LIMIT
    def __init__(self,send,original,clock_ms,guard,pid,intent,*,monotonic=time.monotonic,sleep=time.sleep):
        need(all(callable(value) for value in (send,original,clock_ms,guard,intent,monotonic,sleep)) and integer(pid,1))
        self.send,self.original,self.clock_ms,self.guard,self.pid,self.intent=send,original,clock_ms,guard,pid,intent
        self.monotonic,self.sleep=monotonic,sleep;self.instance=None;self.sequence=self.epoch=0;self.seen=set();self.last=None

    def perform(self,request):
        try:
            request=deepcopy(self.command_validator(request));need(request['commandId'] not in self.seen and len(self.seen)<2048)
            need(self.guard() is not False)
            started=previous=self.monotonic();need(number(started,0,1e15))
            requested=self.clock_ms();need(integer(requested,1))
            current=self.monotonic();need(number(current,previous,1e15) and current-started<1.5);previous=current
            self.intent(deepcopy(request));self.seen.add(request['commandId'])
            current=self.monotonic();need(number(current,previous,1e15) and current-started<1.5);previous=current
            need(self.guard() is not False);self.send(request)
            for attempt in range(61):
                need(self.guard() is not False)
                raw=self.original();need(type(raw) is str and len(raw.encode())<=self.limit)
                try:value=decode(raw) if raw else None
                except json.JSONDecodeError:value=None
                current=self.monotonic();need(number(current,previous,1e15) and current-started<1.5);previous=current
                if type(value) is dict and value.get('commandId')==request['commandId'] and value.get('pending') is not True:
                    epoch=self.clock_ms();need(integer(epoch,requested))
                    validator=self.frame_validator if request['operation']=='read' else self.storage_validator
                    validator(value,request,self.pid,epoch)
                    need(value['requestedEpochMs']>=requested and value['capturedEpochMs']>=self.epoch
                         and self.instance in (None,value['instance']) and value['sequence']>self.sequence
                         and self.guard() is not False)
                    final=self.clock_ms();need(integer(final,epoch));fresh(value['capturedEpochMs'],final)
                    ended=self.monotonic();need(number(ended,previous,1e15) and ended-started<1.5 and self.guard() is not False)
                    self.instance,self.sequence,self.epoch=value['instance'],value['sequence'],value['capturedEpochMs']
                    self.last=deepcopy(value);return value
                if attempt<60:self.sleep(.025)
        except Exception:raise NativeUIError('Original completed frame source is unavailable; command responsibility is retained') from None
        raise NativeUIError('Original completed frame did not produce this request')
