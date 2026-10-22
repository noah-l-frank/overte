"""Original weak Go To/Places root lifetime; hidden is distinct from destroyed."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import re
import time
import uuid
from adapters.native_feature_observation import decode,exact,fresh,integer,need,number
from adapters.token_create_ui import nonce
from adapters.normal_ui import NativeUIError

VERSION=2
FILE='feature-navigation-panels.json'
PROFILES=frozenset(('pico-address-v1','pico-places-v1'))


def identifier(value):return type(value) is str and re.fullmatch('[0-9a-f]{32}',value) is not None


def command(value):
    exact(value,{'schemaVersion','commandId','action','runId'})
    need(type(value['schemaVersion']) is int and value['schemaVersion']==1 and value['action']=='feature-navigation-panels'
         and identifier(value['commandId']) and identifier(value['runId']))
    return value


def validate(value,request,pid,epoch):
    command(request)
    version=value.get('navigationPanelsVersion') if type(value) is dict else None
    exact(value,{'navigationPanelsVersion','commandId','runId','instance','sequence','processId','capturedEpochMs','complete','roots','ui'}|({'lookup'} if version==2 else set()))
    need(type(version) is int and version in (1,2)
         and value['commandId']==request['commandId'] and value['runId']==request['runId'] and identifier(value['instance'])
         and integer(value['sequence'],1,4096) and integer(pid,1) and integer(value['processId'],1) and value['processId']==pid
         and value['complete'] is True and type(value['roots']) is list and len(value['roots'])<=128)
    fresh(value['capturedEpochMs'],epoch);ui=value['ui']
    exact(ui,{'bridgeId','generation','sequence','elapsedMs','observedEpochMs','open','ready'})
    need(nonce(ui['bridgeId']) and nonce(ui['generation']) and integer(ui['sequence']) and integer(ui['elapsedMs'])
         and integer(ui['observedEpochMs'],1) and 0<=value['capturedEpochMs']-ui['observedEpochMs']<=1500
         and type(ui['open']) is bool and type(ui['ready']) is bool and (ui['open'] or not ui['ready']))
    seen=set()
    for row in value['roots']:
        exact(row,{'rootId','profile','sourceSha256','firstObservedEpochMs','alive','inCurrentTree','visible'})
        need(identifier(row['rootId']) and row['rootId'] not in seen and type(row['profile']) is str and row['profile'] in PROFILES
             and type(row['sourceSha256']) is str and re.fullmatch('[0-9a-f]{64}',row['sourceSha256'])
             and integer(row['firstObservedEpochMs'],1,value['capturedEpochMs'])
             and all(type(row[k]) is bool for k in ('alive','inCurrentTree','visible'))
             and (row['alive'] or not row['inCurrentTree'] and not row['visible'])
             and (not row['visible'] or row['inCurrentTree'] and ui['open']))
        seen.add(row['rootId'])
    if version==2:
        lookup=value['lookup'];exact(lookup,{'complete','home','address'});need(type(lookup['complete']) is bool)
        home,address=lookup['home'],lookup['address']
        if home is not None:
            exact(home,{'rootId','sourceSha256','pageIndex','pageCount','visible'})
            need(identifier(home['rootId']) and home['rootId'] not in seen and type(home['sourceSha256']) is str
                 and re.fullmatch('[0-9a-f]{64}',home['sourceSha256']) and integer(home['pageCount'],0,32)
                 and type(home['pageIndex']) is int and -1<=home['pageIndex']<home['pageCount']
                 and type(home['visible']) is bool and (not home['visible'] or ui['open']))
        current=[r for r in value['roots'] if r['profile']=='pico-address-v1' and r['alive'] and r['inCurrentTree']]
        if address is not None:
            exact(address,{'rootId','sourceSha256','textSha256','textLength','focused','inputReady','visible'})
            need(identifier(address['rootId']) and all(type(address[k]) is str and re.fullmatch('[0-9a-f]{64}',address[k])
                 for k in ('sourceSha256','textSha256')) and integer(address['textLength'],0,2048)
                 and all(type(address[k]) is bool for k in ('focused','inputReady','visible'))
                 and (not address['inputReady'] or address['focused']))
            matching=[r for r in current if r['rootId']==address['rootId']]
            need(len(matching)==1 and matching[0]['sourceSha256']==address['sourceSha256'] and matching[0]['visible']==address['visible'])
        if lookup['complete']:need(len(current)<=1 and bool(current)==(address is not None))
    return value


def continuation(before,after):
    need(before['navigationPanelsVersion']==after['navigationPanelsVersion'] and before['instance']==after['instance'] and before['processId']==after['processId'] and before['runId']==after['runId']
         and after['sequence']>before['sequence'] and after['capturedEpochMs']>=before['capturedEpochMs']
         and before['ui']['bridgeId']==after['ui']['bridgeId']
         and all(after['ui'][k]>=before['ui'][k] for k in ('sequence','elapsedMs','observedEpochMs')))
    old={r['rootId']:r for r in before['roots']};new={r['rootId']:r for r in after['roots']};need(set(old)<=set(new))
    for key,row in new.items():
        if key not in old:need(row['firstObservedEpochMs']>=before['capturedEpochMs'])
        else:
            prior=old[key]
            need(all(prior[k]==row[k] for k in ('profile','sourceSha256','firstObservedEpochMs')) and (prior['alive'] or not row['alive']))


def retired(value,roots):
    need(type(roots) is list and roots and len(set(roots))==len(roots) and all(identifier(r) for r in roots))
    rows={r['rootId']:r for r in value['roots']}
    need(all(key in rows and not rows[key]['alive'] for key in roots))
    return True


class NativeNavigationPanels:
    def __init__(self,send,original,clock_ms,guard,pid,*,monotonic=time.monotonic,sleep=time.sleep):
        need(all(callable(f) for f in (send,original,clock_ms,guard,monotonic,sleep)) and integer(pid,1))
        self.send,self.original,self.clock_ms,self.guard,self.pid=send,original,clock_ms,guard,pid
        self.monotonic,self.sleep=monotonic,sleep;self.last=None;self.requests=set()
    def read(self,run):
        request=dict(schemaVersion=1,commandId=uuid.uuid4().hex,action='feature-navigation-panels',runId=run)
        try:
            command(request);need(request['commandId'] not in self.requests and len(self.requests)<4096)
            self.requests.add(request['commandId']);need(self.guard() is not False)
            started=previous=self.monotonic();need(number(started,0,1e15));self.send(deepcopy(request))
            for attempt in range(51):
                now=self.monotonic();need(number(now,0,1e15) and previous<=now and now-started<5 and self.guard() is not False)
                previous=now;raw=self.original()
                try:value=decode(raw) if raw else None
                except (ValueError,NativeUIError):value=None
                if type(value) is dict and value.get('commandId')==request['commandId']:
                    validate(value,request,self.pid,self.clock_ms())
                    if self.last is not None:continuation(self.last,value)
                    now=self.monotonic();need(number(now,0,1e15) and previous<=now and now-started<5 and self.guard() is not False)
                    self.last=deepcopy(value);return value
                if attempt==50:break
                self.sleep(.1)
        except Exception:raise NativeUIError('Original Navigation panel lifetime is unavailable') from None
        raise NativeUIError('Original Navigation panel lifetime is unavailable')
