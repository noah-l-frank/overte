"""Owned actual Places HTTP inputs; server receipts are not client observations."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from contextlib import contextmanager
from copy import deepcopy
import hashlib
import json
import re
import secrets
import threading
import time
from .contract import exact,identifier,number
from .fixtures import context
from navigation_observation import viewpoint_urls

VERSION=1
DIRECTORY_MARKER_VERSION=1
DIRECTORY_MARKER='overte-directory-v1:'
DIRECTORY='/api/v1/places'
QUERY='status=online&per_page=1000'


def configuration(value):
    exact(value,{'protocolSignature','sourceRevision','sceneUrl'},'owned navigation input configuration')
    signature=value['protocolSignature'];revision=value['sourceRevision']
    if (type(signature) is not str or len(signature)!=24 or type(revision) is not str
            or re.fullmatch('[0-9a-f]{40}',revision) is None):raise ValueError('Original navigation build inputs are required')
    try:raw=base64.b64decode(signature,validate=True)
    except Exception:raise ValueError('Invalid original protocol signature input') from None
    if len(raw)!=16 or base64.b64encode(raw).decode()!=signature:raise ValueError('Noncanonical protocol signature input')
    urls=viewpoint_urls(value['sceneUrl'])
    if value['sceneUrl']!=value['sceneUrl'].split('?')[0]:raise ValueError('Navigation scene input cannot select a viewpoint')
    return deepcopy(value),urls


class NavigationResources:
    def __init__(self,inputs,*,clock_ms=lambda:int(time.time()*1000)):
        self.inputs,self.urls=configuration(inputs)
        if not callable(clock_ms):raise ValueError('Original server clock is required')
        self.clock_ms=clock_ms;self.lock=threading.RLock();self.runs={};self.instance=secrets.token_hex(16)
        self.last_epoch=0;self.failed=0;self.valid=True

    def epoch(self):
        now=self.clock_ms()
        if type(now) is not int or now<=0 or now<self.last_epoch:
            self.valid=False;raise ValueError('Navigation fixture clock is unavailable')
        self.last_epoch=now;return now

    def ready(self):
        with self.lock:
            return dict(navigationProviderVersion=VERSION,instance=self.instance,inputs=deepcopy(self.inputs),
                capturedEpochMs=self.epoch(),ready=self.valid and not self.failed and len(self.runs)<32,
                activeRuns=sum(row['active'] for row in self.runs.values()),failedResponses=self.failed)

    def provision(self,run):
        identifier(run)
        with self.lock:
            if (not self.valid or self.failed or run in self.runs or len(self.runs)>=32
                    or any(row['active'] for row in self.runs.values())):
                raise ValueError('Navigation provider ownership is unavailable')
            self.runs[run]=dict(active=True,ticket=None,responses=[],epoch=self.epoch())

    def activate(self,run,ticket):
        identifier(ticket)
        with self.lock:
            row=self.runs[identifier(run)]
            if not row['active']:raise ValueError('Navigation run is retired')
            row['ticket']=ticket

    def snapshot(self,run):
        with self.lock:
            row=self.runs[identifier(run)]
            return dict(navigationProviderVersion=VERSION,instance=self.instance,runId=run,inputs=deepcopy(self.inputs),
                capturedEpochMs=self.epoch(),active=row['active'],ticket=row['ticket'],responses=deepcopy(row['responses']),
                failedResponses=self.failed)

    def retire(self,run):
        with self.lock:
            self.runs[identifier(run)]['active']=False
            self.runs[run]['ticket']=None

    @contextmanager
    def response(self,path,query):
        # Hold the same source lock through the actual bounded socket write.
        # Retirement cannot claim absence while one owned response is in flight.
        with self.lock:
            active=[(run,row) for run,row in self.runs.items() if row['active']]
            if len(active)!=1 or not self.valid or self.failed:
                yield None;return
            run,row=active[0];ctx=context(run);response_id=secrets.token_hex(16)
            if path==DIRECTORY and query==QUERY:
                kind,status='directory',200
                # A fresh real directory field must survive native parsing and
                # QML materialization. Reusing a previous response's model is
                # distinguishable even while the destination/name stay stable.
                record=dict(id=ctx['destination'],name=ctx['name'],address=self.urls['B'],description=DIRECTORY_MARKER+response_id,
                    maturity='everyone',visibility='open',tags=[],managers=[],thumbnail='',path='/2,0,4',
                    domain=dict(id=run[:8]+'-'+run[8:12]+'-'+run[12:16]+'-'+run[16:20]+'-'+run[20:],
                        name=ctx['name'],protocol_version=self.inputs['protocolSignature'],num_users=0,capacity=8))
                document=dict(status='success',data=dict(places=[record]))
            elif path==DIRECTORY+'/'+ctx['hidden'] and not query:
                kind,status='missing-name',404
                document=dict(status='fail',data=dict(message='Owned place is unavailable'))
            else:
                yield None;return
            if row['ticket'] is None or len(row['responses'])>=256:
                yield None;return
            body=json.dumps(document,separators=(',',':'),ensure_ascii=False).encode()
            ticket=row['ticket']
            try:
                yield status,body,response_id
            except BaseException:
                self.failed+=1;raise
            else:
                row['responses'].append(dict(sequence=len(row['responses'])+1,responseId=response_id,ticket=ticket,
                    kind=kind,status=status,bytes=len(body),sha256=hashlib.sha256(body).hexdigest(),completedEpochMs=self.epoch()))


def validate_status(value,*,instance,run,inputs,previous=None):
    exact(value,{'navigationProviderVersion','instance','runId','inputs','capturedEpochMs','active','ticket',
                 'responses','failedResponses'},'original navigation provider status')
    if (type(value['navigationProviderVersion']) is not int or value['navigationProviderVersion']!=VERSION
            or value['instance']!=instance or value['runId']!=run or value['inputs']!=inputs
            or type(value['active']) is not bool or type(value['failedResponses']) is not int or value['failedResponses']!=0
            or type(value['responses']) is not list or len(value['responses'])>256):raise ValueError('Navigation source changed or failed')
    number(value['capturedEpochMs'],1)
    if value['ticket'] is not None:identifier(value['ticket'])
    if not value['active'] and value['ticket'] is not None:raise ValueError('Retired navigation source retained its challenge')
    ids=set();epoch=0
    for sequence,row in enumerate(value['responses'],1):
        exact(row,{'sequence','responseId','ticket','kind','status','bytes','sha256','completedEpochMs'},'original HTTP response receipt')
        identifier(row['responseId']);identifier(row['ticket'])
        if (type(row['sequence']) is not int or row['sequence']!=sequence or row['responseId'] in ids
                or row['kind'] not in ('directory','missing-name')
                or type(row['status']) is not int or row['status']!=(200 if row['kind']=='directory' else 404)
                or type(row['bytes']) is not int or not 1<=row['bytes']<=4096
                or type(row['sha256']) is not str or re.fullmatch('[0-9a-f]{64}',row['sha256']) is None):raise ValueError('Invalid actual HTTP response receipt')
        number(row['completedEpochMs'],1)
        if not epoch<=row['completedEpochMs']<=value['capturedEpochMs']:raise ValueError('Original navigation response clock regressed')
        ids.add(row['responseId']);epoch=row['completedEpochMs']
    if previous is not None:
        old=previous['responses']
        if (value['capturedEpochMs']<previous['capturedEpochMs'] or len(value['responses'])<len(old)
                or value['responses'][:len(old)]!=old or not previous['active'] and value['active']):
            raise ValueError('Original navigation history changed or resurrected')
    return value
