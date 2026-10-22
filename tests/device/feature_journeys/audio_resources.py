"""Owned preview microphone INPUT and original completed HTTP socket receipts.

Generated input bytes are never a recording, acoustic capture or product fact.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from copy import deepcopy
import hashlib
import io
import secrets
import threading
import time
import wave
from functools import lru_cache
from urllib.parse import urlsplit
from .contract import exact,identifier,typed_equal
from .fixtures import wav_bytes
from .graphics_resources import fixture_url

RESOURCE='preview-input.v1.pcm16le'
VERSION=1


@lru_cache(maxsize=256)
def pcm_input(run,ticket):
    with wave.open(io.BytesIO(wav_bytes(run,ticket,profile='recorded-preview-v1')),'rb') as source:
        if (source.getnchannels(),source.getsampwidth(),source.getframerate(),source.getnframes())!=(1,2,24000,72000):
            raise ValueError('Controlled preview input format changed')
        return source.readframes(72000)


class AudioResources:
    def __init__(self,url,*,clock_ms=lambda:int(time.time()*1000)):
        self.url=fixture_url(url)
        if urlsplit(url).scheme!='http' or not callable(clock_ms):raise ValueError('Original controlled Audio HTTP input is required')
        self.clock_ms,self.instance=clock_ms,secrets.token_hex(16)
        self.lock,self.runs=threading.RLock(),{}
        self.last_epoch,self.failed,self.valid=0,0,True

    def epoch(self):
        now=self.clock_ms()
        if type(now) is not int or now<=0 or now<self.last_epoch:
            self.valid=False;raise ValueError('Original Audio HTTP clock regressed')
        self.last_epoch=now;return now

    def ready(self):
        with self.lock:return dict(audioProviderVersion=VERSION,instance=self.instance,fixtureUrl=self.url,
            capturedEpochMs=self.epoch(),ready=self.valid and not self.failed and len(self.runs)<32,
            activeRuns=sum(row['active'] for row in self.runs.values()),failedResponses=self.failed)

    def has_run(self,run):
        with self.lock:return run in self.runs

    def provision(self,run):
        identifier(run)
        with self.lock:
            if not self.valid or self.failed or run in self.runs or len(self.runs)>=32 or any(r['active'] for r in self.runs.values()):
                raise ValueError('Audio HTTP ownership is unavailable')
            self.epoch();self.runs[run]=dict(active=True,ticket=None,activations=[],responses=[])

    def activate(self,run,ticket):
        identifier(ticket)
        with self.lock:
            row=self.runs[identifier(run)]
            if not self.valid or self.failed or not row['active'] or len(row['activations'])>=256 or any(a['ticket']==ticket for a in row['activations']):
                raise ValueError('Audio HTTP challenge is unavailable')
            row['activations'].append(dict(sequence=len(row['activations'])+1,ticket=ticket,activatedEpochMs=self.epoch()))
            row['ticket']=ticket

    def snapshot(self,run,request):
        identifier(request)
        with self.lock:return dict(audioProviderVersion=VERSION,instance=self.instance,fixtureUrl=self.url,
            runId=identifier(run),requestId=request,capturedEpochMs=self.epoch(),healthy=self.valid and not self.failed,
            failedResponses=self.failed,**deepcopy(self.runs[run]))

    def retire(self,run):
        with self.lock:self.epoch();self.runs[identifier(run)].update(active=False,ticket=None)

    @contextmanager
    def response(self,run,ticket,*,request_authority,request_scheme):
        identifier(run);identifier(ticket);parsed=urlsplit(self.url)
        if request_authority!=parsed.netloc or request_scheme!=parsed.scheme:raise ValueError('Audio HTTP origin changed')
        # Keep retirement/activation outside this actual socket write.
        with self.lock:
            row=self.runs.get(run)
            if row is None or not row['active'] or not self.valid or self.failed or row['ticket']!=ticket:
                yield None;return
            if len(row['responses'])>=256:self.valid=False;yield None;return
            body=pcm_input(run,ticket);started=self.epoch();response_id=secrets.token_hex(16);writes=[]
            def actual_write(value):
                exact(value,{'responseId','status','bytes','sha256'},'original Audio socket write')
                if writes or value['responseId']!=response_id or type(value['status']) is not int or not 100<=value['status']<=599 or type(value['bytes']) is not int or value['bytes']!=len(body) or value['sha256']!=hashlib.sha256(body).hexdigest():
                    raise ValueError('Original Audio socket write is unavailable or changed')
                writes.append(deepcopy(value))
            try:
                yield 200,body,response_id,actual_write
                if len(writes)!=1:raise ValueError('Original Audio socket write was not observed')
                completed=self.epoch()
            except BaseException:self.failed+=1;raise
            else:row['responses'].append(dict(sequence=len(row['responses'])+1,ticket=ticket,resource=RESOURCE,
                requestAuthority=request_authority,requestScheme=request_scheme,startedEpochMs=started,completedEpochMs=completed,**writes[0]))


def validate_status(value,*,instance,run,url,request,previous=None):
    identifier(instance);identifier(run);identifier(request);fixture_url(url)
    exact(value,{'audioProviderVersion','instance','fixtureUrl','runId','requestId','capturedEpochMs','healthy',
        'failedResponses','active','ticket','activations','responses'},'original Audio HTTP status')
    if type(value['audioProviderVersion']) is not int or value['audioProviderVersion']!=VERSION or value['instance']!=instance or value['fixtureUrl']!=url or value['runId']!=run or value['requestId']!=request or type(value['capturedEpochMs']) is not int or value['capturedEpochMs']<=0 or value['healthy'] is not True or type(value['failedResponses']) is not int or value['failedResponses']!=0 or type(value['active']) is not bool or any(type(value[k]) is not list or len(value[k])>256 for k in ('activations','responses')):
        raise ValueError('Original Audio HTTP source is unavailable or changed')
    tickets={};last=0
    for sequence,row in enumerate(value['activations'],1):
        exact(row,{'sequence','ticket','activatedEpochMs'},'original Audio activation');ticket=identifier(row['ticket'])
        if type(row['sequence']) is not int or row['sequence']!=sequence or ticket in tickets or type(row['activatedEpochMs']) is not int or not 0<row['activatedEpochMs']<=value['capturedEpochMs'] or row['activatedEpochMs']<last:
            raise ValueError('Audio HTTP activation changed')
        tickets[ticket]=last=row['activatedEpochMs']
    if value['ticket']!=(value['activations'][-1]['ticket'] if value['active'] and tickets else None):raise ValueError('Audio current HTTP challenge changed')
    responses=set();last=0;parsed=urlsplit(url)
    for sequence,row in enumerate(value['responses'],1):
        exact(row,{'sequence','ticket','resource','requestAuthority','requestScheme','startedEpochMs','completedEpochMs','responseId','status','bytes','sha256'},'original Audio HTTP response')
        response=identifier(row['responseId']);ticket=identifier(row['ticket']);body=pcm_input(run,ticket)
        if type(row['sequence']) is not int or row['sequence']!=sequence or response in responses or ticket not in tickets or row['resource']!=RESOURCE or row['requestAuthority']!=parsed.netloc or row['requestScheme']!=parsed.scheme or type(row['status']) is not int or not 100<=row['status']<=599 or type(row['bytes']) is not int or row['bytes']!=len(body) or row['sha256']!=hashlib.sha256(body).hexdigest() or type(row['startedEpochMs']) is not int or type(row['completedEpochMs']) is not int or not max(last,tickets[ticket])<=row['startedEpochMs']<=row['completedEpochMs']<=value['capturedEpochMs']:
            raise ValueError('Original Audio HTTP response changed')
        responses.add(response);last=row['completedEpochMs']
    if previous is not None:
        validate_status(previous,instance=instance,run=run,url=url,request=previous['requestId'])
        if value['requestId']==previous['requestId'] or value['capturedEpochMs']<previous['capturedEpochMs'] or not previous['active'] and value['active'] or any(not typed_equal(value[k][:len(previous[k])],previous[k]) for k in ('activations','responses')):
            raise ValueError('Original Audio HTTP history regressed')
    return value
