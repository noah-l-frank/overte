"""Original native Window-to-Script callback resources; never picker effects."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
import math
import time
import uuid

from adapters.native_feature_observation import decode,exact,fresh,integer,need,number
from adapters.native_script_compilations import validate as compilations,accept as accept_compilations
from adapters.native_script_membership import validate as membership,accept as accept_membership
from adapters.token_create_ui import nonce
from adapters.normal_ui import NativeUIError

VERSION=1
FILE='feature-create-callbacks.json'
ACTION='feature-create-callbacks-observe'


def callbacks(value,epoch):
    exact(value,{'callbackSourceVersion','instance','sequence','complete','proxies','callbacks'})
    need(type(value['callbackSourceVersion']) is int and value['callbackSourceVersion']==VERSION
         and nonce(value['instance']) and integer(value['sequence']) and type(value['complete']) is bool
         and type(value['proxies']) is list and len(value['proxies'])<=128
         and type(value['callbacks']) is list and len(value['callbacks'])<=512)
    need(value['complete'] or not value['proxies'] and not value['callbacks'])
    proxies={};ids=[]
    for row in value['proxies']:
        exact(row,{'id','targetClass','signal','createdEpochMs','retiredEpochMs','dispatches'})
        need(nonce(row['id']) and row['id'] not in proxies
             and row['targetClass']=='WindowScriptingInterface' and row['signal'] in ('browseChanged(QString)','saveFileChanged(QString)')
             and integer(row['createdEpochMs'],1,epoch) and integer(row['retiredEpochMs'])
             and (row['retiredEpochMs']==0 or row['createdEpochMs']<=row['retiredEpochMs']<=epoch)
             and integer(row['dispatches'],0,128) and (row['retiredEpochMs']==0 or row['dispatches']==0))
        ids.append(row['id']);proxies[row['id']]=row
    need(ids==sorted(ids));ids=[]
    for row in value['callbacks']:
        exact(row,{'id','proxyId','scriptId','connectedEpochMs','disconnectedEpochMs'})
        need(nonce(row['id']) and row['proxyId'] in proxies and integer(row['scriptId'],1,2147483647)
             and integer(row['connectedEpochMs'],proxies[row['proxyId']]['createdEpochMs'],epoch)
             and integer(row['disconnectedEpochMs'])
             and (row['disconnectedEpochMs']==0 or row['connectedEpochMs']<=row['disconnectedEpochMs']<=epoch))
        retired=proxies[row['proxyId']]['retiredEpochMs']
        need(not retired or row['disconnectedEpochMs']>0 and row['disconnectedEpochMs']<=retired)
        ids.append(row['id'])
    need(ids==sorted(set(ids)))
    return value


def validate(value,request,pid,epoch):
    exact(value,{'schemaVersion','requestId','instance','sequence','requestedEpochMs','capturedEpochMs','processId','source'})
    need(type(value['schemaVersion']) is int and value['schemaVersion']==VERSION and nonce(request)
         and value['requestId']==request and nonce(value['instance']) and integer(value['sequence'],1)
         and integer(pid,1) and integer(value['processId'],1) and value['processId']==pid
         and integer(value['requestedEpochMs'],1) and integer(value['capturedEpochMs'],value['requestedEpochMs'])
         and value['capturedEpochMs']-value['requestedEpochMs']<5000)
    fresh(value['capturedEpochMs'],epoch);epoch=value['capturedEpochMs']
    source=value['source'];exact(source,{'createCallbackSourceVersion','complete','membershipRevision','managers'})
    need(type(source['createCallbackSourceVersion']) is int and source['createCallbackSourceVersion']==VERSION
         and source['complete'] is True and integer(source['membershipRevision'])
         and type(source['managers']) is list and len(source['managers'])<=128)
    for row in source['managers']:exact(row,{'membership','callbacks','compiled'})
    membership(dict(complete=True,revision=source['membershipRevision'],managers=[r['membership'] for r in source['managers']]),epoch)
    identities=set()
    for row in source['managers']:
        exact(row,{'membership','callbacks','compiled'})
        callbacks(row['callbacks'],epoch);need(row['callbacks']['complete'] is True)
        need(row['callbacks']['instance'] not in identities);identities.add(row['callbacks']['instance'])
        compilations(row['compiled'],epoch);need(row['compiled']['complete'] is True)
        code={r['scriptId']:r for r in row['compiled']['compilations']}
        for callback in row['callbacks']['callbacks']:
            need(callback['scriptId'] in code and code[callback['scriptId']]['compiledEpochMs']<=callback['connectedEpochMs'])
    return value


def continuity(previous,value):
    if previous is None:return
    need(value['instance']==previous['instance'] and value['sequence']>previous['sequence']
         and value['capturedEpochMs']>=previous['capturedEpochMs'])
    old=previous['source'];new=value['source']
    accept_membership(dict(complete=True,revision=old['membershipRevision'],managers=[r['membership'] for r in old['managers']]),
        dict(complete=True,revision=new['membershipRevision'],managers=[r['membership'] for r in new['managers']]),set(),value['capturedEpochMs'])
    before={r['membership']['instance']:r for r in old['managers']}
    current={r['membership']['instance']:r for r in new['managers']}
    # This source deliberately retains every known manager, including finished
    # and pending managers. Disappearance cannot erase an unresolved callback.
    need(set(before)<=set(current))
    for identity,row in before.items():
        latest=current[identity];a=row['callbacks'];b=latest['callbacks']
        need(a['instance']==b['instance'] and b['sequence']>=a['sequence']
             and (a['sequence']!=b['sequence'] or a==b))
        accept_compilations(row['compiled'],latest['compiled'],value['capturedEpochMs'])
        for key,immutable,terminal in (('proxies',('id','targetClass','signal','createdEpochMs'),'retiredEpochMs'),
                ('callbacks',('id','proxyId','scriptId','connectedEpochMs'),'disconnectedEpochMs')):
            rows={r['id']:r for r in b[key]}
            for original in a[key]:
                need(original['id'] in rows);now=rows[original['id']]
                need(all(now[k]==original[k] for k in immutable)
                     and (original[terminal]==0 or now==original))


def active(value):
    """Measured resource identities only; native dialog/context joins are separate."""
    validate(value,value['requestId'],value['processId'],value['capturedEpochMs'])
    result=[]
    for manager in value['source']['managers']:
        source=manager['callbacks'];proxies={p['id']:p for p in source['proxies']}
        for row in source['callbacks']:
            if row['disconnectedEpochMs']==0:
                result.append(dict(managerId=manager['membership']['instance'],sourceId=source['instance'],
                    callbackId=row['id'],proxyId=row['proxyId'],scriptId=row['scriptId'],signal=proxies[row['proxyId']]['signal']))
        for row in source['proxies']:
            if row['dispatches']:
                result.append(dict(managerId=manager['membership']['instance'],sourceId=source['instance'],
                    proxyId=row['id'],dispatches=row['dispatches'],signal=row['signal']))
    return result


class NativeCreateCallbacks:
    def __init__(self,send,original,clock_ms,guard,pid,*,monotonic=time.monotonic,sleep=time.sleep):
        need(all(callable(v) for v in (send,original,clock_ms,guard,monotonic,sleep)) and integer(pid,1))
        self.send,self.original,self.clock_ms,self.guard,self.pid=send,original,clock_ms,guard,pid
        self.monotonic,self.sleep,self.last=monotonic,sleep,None
        self.last_raw,self.last_sha256=None,None

    def read(self):
        try:
            request=uuid.uuid4().hex;started=previous=self.monotonic()
            need(number(started,0,1e15) and self.guard() is not False)
            requested=self.clock_ms();need(integer(requested,1))
            self.send(dict(schemaVersion=VERSION,commandId=request,action=ACTION))
            for attempt in range(51):
                need(self.guard() is not False);raw=self.original()
                try:value=decode(raw) if raw else None
                except json.JSONDecodeError:value=None
                current=self.monotonic();need(number(current,previous,1e15) and current-started<5);previous=current
                if type(value) is dict and value.get('requestId')==request:
                    epoch=self.clock_ms();need(integer(epoch,requested))
                    validate(value,request,self.pid,epoch);need(value['requestedEpochMs']>=requested)
                    continuity(self.last,value);need(self.guard() is not False)
                    freshness_started=self.monotonic();need(number(freshness_started,previous,1e15));previous=freshness_started
                    final=self.clock_ms();need(integer(final,epoch));fresh(value['capturedEpochMs'],final)
                    need(self.guard() is not False)
                    finished=self.monotonic();need(number(finished,previous,1e15) and finished-started<5
                        and final-value['capturedEpochMs']+math.ceil((finished-freshness_started)*1000)<=1500)
                    self.last=deepcopy(value);self.last_raw=raw;self.last_sha256=hashlib.sha256(raw.encode()).hexdigest()
                    return deepcopy(value)
                if attempt<50:self.sleep(.1)
        except Exception:raise NativeUIError('Original native Create callback observation is unavailable or invalid') from None
        raise NativeUIError('Original native Create callback observation did not produce this request')
