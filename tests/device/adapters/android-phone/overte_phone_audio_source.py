"""Closed original Phone PCM-input/HTTP/codec source; no UI/effect commands."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import re
import time
import uuid
from adapters.native_feature_observation import decode,exact,fresh,integer,need,number
from adapters.recorded_preview_history import validate_history
from feature_journeys.contract import identifier
from feature_journeys.audio_resources import RESOURCE,fixture_url

FILE='phone-audio-fixture.json'


def command(value):
    exact(value,{'schemaVersion','commandId','action','request'})
    identifier(value['commandId']);request=value['request'];need(value['schemaVersion']==1 and type(value['schemaVersion']) is int and value['action']=='phone-audio-fixture' and type(request) is dict)
    extra={'runId','ticket','url'} if request.get('operation')=='arm' else set()
    exact(request,{'schemaVersion','commandId','operation'}|extra)
    need(type(request['schemaVersion']) is int and request['schemaVersion']==1 and request['commandId']==value['commandId'] and request['operation'] in ('arm','observe','release'))
    if extra:
        run,ticket=identifier(request['runId']),identifier(request['ticket'])
        suffix='/runs/'+run+'/tickets/'+ticket+'/'+RESOURCE
        need(type(request['url']) is str and request['url'].endswith(suffix));fixture_url(request['url'][:-len(suffix)])
        need(request['url'].startswith('http://'))
    return value


def receipt(value):
    exact(value,{'runId','ticket','url','responseId','status','bytes','sha256','startedEpochMs','completedEpochMs'})
    identifier(value['runId']);identifier(value['ticket']);identifier(value['responseId'])
    command(dict(schemaVersion=1,commandId='f'*32,action='phone-audio-fixture',request=dict(schemaVersion=1,commandId='f'*32,operation='arm',runId=value['runId'],ticket=value['ticket'],url=value['url'])))
    need(type(value['status']) is int and value['status']==200 and type(value['bytes']) is int and value['bytes']==144000 and type(value['sha256']) is str and re.fullmatch('[0-9a-f]{64}',value['sha256']) and integer(value['startedEpochMs'],1) and integer(value['completedEpochMs'],value['startedEpochMs']) and value['completedEpochMs']-value['startedEpochMs']<5000)
    return value


def validate(value,request,pid,epoch,previous=None):
    exact(value,{'schemaVersion','requestId','instance','sequence','capturedEpochMs','processId','pending','error','receipt','source','pendingBytes','revision'})
    need(type(value['schemaVersion']) is int and value['schemaVersion']==1 and value['requestId']==request and value['processId']==pid and integer(value['processId'],1) and integer(value['sequence'],1) and type(value['pending']) is bool and integer(value['pendingBytes'],0,144001) and integer(value['revision']) and type(value['error']) is str and value['error'] in ('','oversized-input','native-input-unavailable','original-http-input-unavailable','input-timeout'))
    identifier(value['instance']);fresh(value['capturedEpochMs'],epoch)
    if value['receipt']:receipt(value['receipt']);need(value['receipt']['completedEpochMs']<=value['capturedEpochMs'])
    source=value['source']
    exact(source,{'inputVersion','armed','receipt','pcmBytes','pcmSha256','complete','cycle','callbacks','inputFrames','inputRate','inputChannels','firstInputEpochMs','lastInputEpochMs','packetEmits','silentEmits','encodedBytes','codec','inputAvailable','lifecycleRunning','paused','muted','preview'})
    need(type(source['inputVersion']) is int and source['inputVersion']==1 and all(type(source[k]) is bool for k in ('armed','complete','inputAvailable','lifecycleRunning','paused','muted')) and all(integer(source[k]) for k in ('cycle','callbacks','inputFrames','packetEmits','silentEmits','encodedBytes','inputRate','inputChannels','firstInputEpochMs','lastInputEpochMs')) and source['silentEmits']<=source['packetEmits']<=4096 and type(source['codec']) is str and len(source['codec'])<=128 and all(ord(c)>=32 for c in source['codec']))
    need(integer(source['pcmBytes'],0,144000) and type(source['pcmSha256']) is str and re.fullmatch('[0-9a-f]{64}',source['pcmSha256']))
    if source['armed']:
        receipt(source['receipt']);need(source['pcmBytes']==144000 and source['pcmSha256']==source['receipt']['sha256'] and source['receipt']==value['receipt'] and source['complete'])
        if source['callbacks']:need(8000<=source['inputRate']<=48000 and source['inputChannels'] in (1,2))
        if source['inputFrames']:need(source['cycle']>0 and 0<source['firstInputEpochMs']<=source['lastInputEpochMs']<=value['capturedEpochMs'])
    else:need(source['pcmBytes']==0 and source['receipt']=={} and source['pcmSha256']==hashlib.sha256(b'').hexdigest())
    validate_history(source['preview'],value['capturedEpochMs'])
    if previous is not None:
        need(value['instance']==previous['instance'] and value['sequence']>previous['sequence'] and value['capturedEpochMs']>=previous['capturedEpochMs'] and value['revision']>=previous['revision'])
        if value['revision']==previous['revision'] and source['armed'] and previous['source']['armed']:
            need(source['receipt']==previous['source']['receipt'] and all(source[k]>=previous['source'][k] for k in ('callbacks','inputFrames','packetEmits','silentEmits','encodedBytes')))
    return value


class PhoneAudioSource:
    def __init__(self,native,original,*,read_only=False,monotonic=time.monotonic,sleep=time.sleep):
        need(type(read_only) is bool and callable(original));self.native,self.original,self.read_only=native,original,read_only
        self.monotonic,self.sleep=monotonic,sleep;self.previous=None

    def query(self,operation='observe',**fields):
        need(not self.read_only or operation=='observe');request=uuid.uuid4().hex
        call=command(dict(schemaVersion=1,commandId=request,action='phone-audio-fixture',request=dict(schemaVersion=1,commandId=request,operation=operation,**fields)))
        self.native.guard();started=last=self.monotonic();self.native.send(call)
        for attempt in range(51):
            self.native.guard();raw=self.original()
            try:value=decode(raw) if raw else None
            except ValueError:value=None
            now=self.monotonic();need(number(now,last,1e15) and now-started<5);last=now
            if type(value) is dict and value.get('requestId')==request:
                validate(value,request,self.native.pid,self.native.clock_ms(),self.previous)
                self.native.guard();self.previous=deepcopy(value);return value
            if attempt<50:self.sleep(.1)
        need(False)

    def release(self):
        self.query('release');value=self.query()
        need(not value['pending'] and value['pendingBytes']==0 and not value['source']['armed'] and value['source']['pcmBytes']==0 and value['source']['receipt']=={})
        return value
