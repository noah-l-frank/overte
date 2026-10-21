"""Owned Graphics scene HTTP input; socket receipts are never client evidence."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from copy import deepcopy
import hashlib
import json
import secrets
import threading
import time
from urllib.parse import urlsplit

from .contract import exact,identifier,typed_equal
from .graphics_fixture import scene
from .script_fixture import authority

VERSION=1
RESOURCE='graphics-scene.v1.json'


def fixture_url(value):
    if (type(value) is not str or not value.isascii() or not 0<len(value)<=512
            or any(ord(c)<=32 or ord(c)==127 for c in value) or any(c in value for c in '%?#\\')):
        raise ValueError('A canonical actual Graphics fixture URL is required')
    parsed=urlsplit(value)
    if (parsed.scheme not in ('http','https') or parsed.path!='/feature-fixture/v1'
            or parsed.netloc!=parsed.netloc.lower() or parsed.geturl()!=value):
        raise ValueError('A canonical actual Graphics fixture URL is required')
    authority(parsed.netloc)
    return value


class GraphicsResources:
    def __init__(self,url,*,clock_ms=lambda:int(time.time()*1000)):
        self.url=fixture_url(url)
        if not callable(clock_ms):raise ValueError('Original Graphics fixture clock is required')
        self.clock_ms,self.instance=clock_ms,secrets.token_hex(16)
        self.lock,self.runs=threading.RLock(),{}
        self.last_epoch,self.failed,self.valid=0,0,True

    def epoch(self):
        now=self.clock_ms()
        if type(now) is not int or now<=0 or now<self.last_epoch:
            self.valid=False;raise ValueError('Original Graphics fixture clock regressed')
        self.last_epoch=now;return now

    def ready(self):
        with self.lock:
            return dict(graphicsProviderVersion=VERSION,instance=self.instance,fixtureUrl=self.url,
                capturedEpochMs=self.epoch(),ready=self.valid and not self.failed and len(self.runs)<32,
                activeRuns=sum(row['active'] for row in self.runs.values()),failedResponses=self.failed)

    def has_run(self,run):
        with self.lock:return run in self.runs

    def provision(self,run):
        identifier(run)
        with self.lock:
            if (not self.valid or self.failed or run in self.runs or len(self.runs)>=32
                    or any(row['active'] for row in self.runs.values())):
                raise ValueError('Graphics scene ownership is unavailable')
            self.epoch()
            self.runs[run]=dict(active=True,ticket=None,sceneTicket=None,activations=[],responses=[])

    def activate(self,run,ticket):
        identifier(ticket)
        with self.lock:
            row=self.runs[identifier(run)]
            if (not self.valid or self.failed or not row['active'] or len(row['activations'])>=256
                    or any(item['ticket']==ticket for item in row['activations'])):
                raise ValueError('Graphics fixture challenge is unavailable')
            epoch=self.epoch()
            row['activations'].append(dict(sequence=len(row['activations'])+1,ticket=ticket,activatedEpochMs=epoch))
            row['ticket']=ticket
            if row['sceneTicket'] is None:row['sceneTicket']=ticket

    def snapshot(self,run,request):
        identifier(request)
        with self.lock:
            row=self.runs[identifier(run)]
            return dict(graphicsProviderVersion=VERSION,instance=self.instance,fixtureUrl=self.url,
                runId=run,requestId=request,capturedEpochMs=self.epoch(),healthy=self.valid and not self.failed,
                failedResponses=self.failed,**deepcopy(row))

    def retire(self,run):
        with self.lock:
            row=self.runs[identifier(run)];self.epoch();row.update(active=False,ticket=None)

    @contextmanager
    def response(self,run,ticket,*,request_authority,request_scheme):
        identifier(run);identifier(ticket);authority(request_authority)
        parsed=urlsplit(self.url)
        if request_authority!=parsed.netloc or request_scheme!=parsed.scheme:
            raise ValueError('Graphics scene request differs from its actual fixture origin')
        # Hold ownership through the original bounded socket write. Retirement
        # cannot overtake an in-flight scene response and later report absence.
        with self.lock:
            row=self.runs.get(run)
            if (row is None or not row['active'] or not self.valid or self.failed
                    or row['sceneTicket']!=ticket):
                yield None;return
            if len(row['responses'])>=256:
                self.valid=False;yield None;return
            body=json.dumps(scene(run,ticket,self.url+'/runs/'+run+'/'),sort_keys=True,separators=(',',':')).encode()
            started,response_id=self.epoch(),secrets.token_hex(16)
            writes=[]
            def actual_write(value):
                exact(value,{'responseId','status','bytes','sha256'},'original Graphics socket write')
                if (writes or value['responseId']!=response_id or type(value['status']) is not int
                        or not 100<=value['status']<=599 or type(value['bytes']) is not int
                        or value['bytes']!=len(body) or value['sha256']!=hashlib.sha256(body).hexdigest()):
                    raise ValueError('Original Graphics scene write is unavailable or changed')
                writes.append(deepcopy(value))
            try:
                yield 200,body,response_id,actual_write
                if len(writes)!=1:raise ValueError('Original Graphics scene write was not observed')
                completed=self.epoch()
            except BaseException:
                self.failed+=1;raise
            else:
                row['responses'].append(dict(sequence=len(row['responses'])+1,ticket=ticket,
                    activeTicket=row['ticket'],resource=RESOURCE,requestAuthority=request_authority,
                    requestScheme=request_scheme,startedEpochMs=started,completedEpochMs=completed,**writes[0]))


def validate_status(value,*,instance,run,url,request,previous=None):
    identifier(instance);identifier(run);identifier(request);fixture_url(url)
    exact(value,{'graphicsProviderVersion','instance','fixtureUrl','runId','requestId','capturedEpochMs','healthy',
        'failedResponses','active','ticket','sceneTicket','activations','responses'},'original Graphics provider status')
    if (type(value['graphicsProviderVersion']) is not int or value['graphicsProviderVersion']!=VERSION
            or value['instance']!=instance or value['fixtureUrl']!=url or value['runId']!=run or value['requestId']!=request
            or type(value['capturedEpochMs']) is not int or value['capturedEpochMs']<=0 or value['healthy'] is not True
            or type(value['failedResponses']) is not int or value['failedResponses']!=0 or type(value['active']) is not bool
            or any(type(value[k]) is not list or len(value[k])>256 for k in ('activations','responses'))):
        raise ValueError('Original Graphics provider is unavailable or changed')
    tickets={};last=0
    for sequence,row in enumerate(value['activations'],1):
        exact(row,{'sequence','ticket','activatedEpochMs'},'original Graphics activation')
        ticket=identifier(row['ticket'])
        if (type(row['sequence']) is not int or row['sequence']!=sequence or ticket in tickets
                or type(row['activatedEpochMs']) is not int or not last<=(row['activatedEpochMs'])<=value['capturedEpochMs']
                or row['activatedEpochMs']<=0):raise ValueError('Graphics activation provenance is invalid')
        tickets[ticket]=row['activatedEpochMs'];last=row['activatedEpochMs']
    scene_ticket=value['activations'][0]['ticket'] if value['activations'] else None
    active_ticket=value['activations'][-1]['ticket'] if value['active'] and value['activations'] else None
    if value['sceneTicket']!=scene_ticket or value['ticket']!=active_ticket:
        raise ValueError('Graphics original scene or active challenge was relabeled')
    response_ids=set();last=0;parsed=urlsplit(url)
    body=(json.dumps(scene(run,scene_ticket,url+'/runs/'+run+'/'),sort_keys=True,separators=(',',':')).encode()
        if scene_ticket is not None else None)
    for sequence,row in enumerate(value['responses'],1):
        exact(row,{'sequence','ticket','activeTicket','resource','requestAuthority','requestScheme','startedEpochMs',
            'completedEpochMs','responseId','status','bytes','sha256'},'original Graphics response')
        response=identifier(row['responseId'])
        if (type(row['sequence']) is not int or row['sequence']!=sequence or response in response_ids or body is None
                or row['ticket']!=scene_ticket or row['activeTicket'] not in tickets or row['resource']!=RESOURCE
                or row['requestAuthority']!=parsed.netloc or row['requestScheme']!=parsed.scheme
                or type(row['status']) is not int or not 100<=row['status']<=599
                or type(row['bytes']) is not int or row['bytes']!=len(body) or row['sha256']!=hashlib.sha256(body).hexdigest()
                or type(row['startedEpochMs']) is not int or type(row['completedEpochMs']) is not int
                or not max(last,tickets[row['activeTicket']])<=row['startedEpochMs']<=row['completedEpochMs']<=value['capturedEpochMs']):
            raise ValueError('Original Graphics scene response provenance is invalid')
        response_ids.add(response);last=row['completedEpochMs']
    if previous is not None:
        validate_status(previous,instance=instance,run=run,url=url,request=previous['requestId'])
        if (value['requestId']==previous['requestId'] or value['capturedEpochMs']<previous['capturedEpochMs']
                or (not previous['active'] and value['active'])
                or any(not typed_equal(value[k][:len(previous[k])],previous[k]) for k in ('activations','responses'))
                or previous['sceneTicket'] not in (None,value['sceneTicket'])):
            raise ValueError('Original Graphics provider history regressed or changed')
    return value
