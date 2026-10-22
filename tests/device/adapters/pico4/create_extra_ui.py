"""Original detailed Create/PolyVox controls on the bound normal Pico route."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import math
import time
from adapters.native_feature_observation import exact,integer,need
from adapters.token_create_ui import nonce,scope
from adapters.normal_ui import NativeUIError

VERSION=1
FIELDS={'create-extra.polyvox.'+axis for axis in 'xyz'}
COUNTS={'create-extra.detail-kind':6,'create-extra.polyvox.preset':6,
    'create-extra.polyvox.shape':4,'create-extra.polyvox.style':4}
IDS=FIELDS|set(COUNTS)|{'create-extra.detail-open','create-extra.polyvox.page','create-extra.polyvox.add','create-extra.polyvox.cancel'}


def text(value):
    need(type(value) is str and value in {str(v) for v in range(8,65)});return value


def metadata(row):
    need(type(row) is dict and row.get('id') in IDS and nonce(row.get('token')))
    base={'id','token','enabled','focused','inputReady'};identifier=row['id']
    need(all(type(row.get(k)) is bool for k in ('enabled','focused','inputReady')) and (not row['inputReady'] or row['enabled']))
    if identifier in FIELDS:exact(row,base|{'text'});text(row['text'])
    elif identifier in COUNTS:
        exact(row,base|{'count','currentIndex'});need(type(row['count']) is int and row['count']==COUNTS[identifier]
            and integer(row['currentIndex'],0,row['count']-1))
    elif identifier=='create-extra.polyvox.page':
        exact(row,base|{'profile','pageId'});need(nonce(row['pageId']) and row['profile']=='original-new-polyvox-v1' and not row['inputReady'])
    else:exact(row,base)
    return row


def inventory(value):
    exact(value,{'createExtraUiInventoryVersion','instance','sourceSequence','elapsedMs','complete','pages'})
    need(type(value['createExtraUiInventoryVersion']) is int and value['createExtraUiInventoryVersion']==1
        and nonce(value['instance']) and integer(value['sourceSequence'],1) and integer(value['elapsedMs'])
        and value['complete'] is True and type(value['pages']) is list and len(value['pages'])<=32)
    seen=set()
    for row in value['pages']:
        exact(row,{'id','contextId','windowId','firstObservedEpochMs','pageAlive','contextAlive','windowAlive'})
        need(all(nonce(row[k]) for k in ('id','contextId','windowId')) and row['id'] not in seen
            and integer(row['firstObservedEpochMs'],1) and all(type(row[k]) is bool for k in ('pageAlive','contextAlive','windowAlive')))
        seen.add(row['id'])
    return value


def inventory_continuity(before,after):
    inventory(before);inventory(after);need(before['instance']==after['instance'] and after['sourceSequence']>=before['sourceSequence']
        and after['elapsedMs']>=before['elapsedMs'] and len(after['pages'])>=len(before['pages']))
    if before['sourceSequence']==after['sourceSequence']:need(before==after)
    for a,b in zip(before['pages'],after['pages']):
        need(all(a[k]==b[k] for k in ('id','contextId','windowId','firstObservedEpochMs'))
            and all(a[k] or not b[k] for k in ('pageAlive','contextAlive','windowAlive')))


def snapshot(value):
    exact(value,{'createExtraControlsVersion','open','ready','scope','controls','createExtraUiInventory'})
    need(type(value['createExtraControlsVersion']) is int and value['createExtraControlsVersion']==VERSION
        and all(type(value[k]) is bool for k in ('open','ready')) and type(value['controls']) is list and len(value['controls'])<=32)
    scope(value['scope']);inventory(value['createExtraUiInventory']);ids=set();tokens=set()
    for row in value['controls']:
        metadata(row);need(row['id'] not in ids and row['token'] not in tokens);ids.add(row['id']);tokens.add(row['token'])
    need(value['open'] or not value['controls'])
    pages={r['id']:r for r in value['createExtraUiInventory']['pages']}
    for row in value['controls']:
        if row['id']=='create-extra.polyvox.page':need(row['pageId'] in pages and pages[row['pageId']]['pageAlive'] and pages[row['pageId']]['contextAlive'])
    return value


def project(value):
    need(value.get('createExtraControlsVersion')==1 and type(value['createExtraControlsVersion']) is int)
    return snapshot(dict(createExtraControlsVersion=VERSION,open=value['open'],ready=value['ready'],
        scope=dict(instance=value['bridgeId'],generation=value['generation'],sequence=value['lastCommandSequence'],
            elapsedMs=value['elapsedMs'],processId=value['processId']),controls=deepcopy([r for r in value['controls'] if r['id'] in IDS]),createExtraUiInventory=deepcopy(value['createExtraUiInventory'])))


def same_reference(original,current,identifier):
    snapshot(original);snapshot(current)
    need(identifier in IDS and all(original['scope'][k]==current['scope'][k] for k in ('instance','generation','sequence','processId'))
        and 0<=current['scope']['elapsedMs']-original['scope']['elapsedMs']<=5000)
    before=[r for r in original['controls'] if r['id']==identifier];after=[r for r in current['controls'] if r['id']==identifier]
    need(len(before)==len(after)==1 and before==after);return before[0]


class PicoCreateExtraIO:
    def __init__(self,io):self.io=io
    def capture(self):return project(self.io.capture())
    def activate(self,identifier,reference):self.io.navigation.input(identifier,reference=reference)
    def replace(self,identifier,value,reference):self.io.navigation.input(identifier,'replace',value,reference=reference)
    def choose(self,identifier,index,reference):self.io.navigation.input(identifier,'select-index',index=index,reference=reference)


class TokenCreateExtraUI:
    def __init__(self,io,intent,*,monotonic=time.monotonic,sleep=time.sleep):
        need(callable(intent) and callable(monotonic) and callable(sleep));self.io,self.intent,self.monotonic,self.sleep=io,intent,monotonic,sleep
        self.previous=None;self.clock=None
    def capture(self):
        value=deepcopy(snapshot(self.io.capture()))
        if self.previous is not None:
            inventory_continuity(self.previous['createExtraUiInventory'],value['createExtraUiInventory'])
            a,b=self.previous['scope'],value['scope'];need(all(a[k]==b[k] for k in ('instance','processId'))
                and b['sequence']>=a['sequence'] and b['elapsedMs']>=a['elapsedMs'])
        self.previous=value;return value
    @staticmethod
    def row(value,identifier,*,ready=True):
        rows=[r for r in value['controls'] if r['id']==identifier];need(len(rows)<=1)
        return rows[0] if rows and (not ready or rows[0]['enabled'] and rows[0]['inputReady']) else None
    def now(self):
        current=self.monotonic();need(type(current) in (int,float) and math.isfinite(current) and current>=0
            and (self.clock is None or current>=self.clock));self.clock=current;return current
    def wait(self,predicate):
        deadline=self.now()+10
        for attempt in range(102):
            current=self.capture()
            if predicate(current):return current
            remaining=deadline-self.now()
            if remaining<=0 or attempt==101:break
            self.sleep(min(.1,remaining))
        raise NativeUIError('Original Create PolyVox control transition was not observed')
    def input(self,identifier,action='activate',value=None):
        need(identifier in IDS-{'create-extra.polyvox.page'} and action in ('activate','replace','select-index'))
        before=self.capture();row=self.row(before,identifier);need(before['open'] and before['ready'] and row is not None)
        if action=='replace':need(identifier in FIELDS and row['focused']);text(value)
        elif action=='select-index':need(identifier in COUNTS and type(value) is int and 0<=value<COUNTS[identifier])
        else:need(value is None)
        self.intent(dict(createExtraInputVersion=1,action=action,controlId=identifier,controlToken=row['token'],scope=deepcopy(before['scope'])))
        if action=='activate':self.io.activate(identifier,before)
        elif action=='replace':self.io.replace(identifier,value,before)
        else:self.io.choose(identifier,value,before)
        after=self.capture();need(after['scope']['sequence']>before['scope']['sequence']);return after
    def choose(self,identifier,index):
        self.input(identifier);self.input(identifier,'select-index',index)
        self.wait(lambda v:bool(self.row(v,identifier) and self.row(v,identifier)['currentIndex']==index))
    def open_polyvox(self):
        self.choose('create-extra.detail-kind',3);self.input('create-extra.detail-open')
        return self.wait(lambda v:self.row(v,'create-extra.polyvox.page',ready=False) is not None)
    def configure_polyvox(self):
        for axis in 'xyz':
            identifier='create-extra.polyvox.'+axis;self.input(identifier)
            self.wait(lambda v:bool(self.row(v,identifier) and self.row(v,identifier)['focused']))
            self.input(identifier,'replace','8');self.wait(lambda v:bool(self.row(v,identifier) and self.row(v,identifier)['text']=='8'))
        self.choose('create-extra.polyvox.preset',1);self.choose('create-extra.polyvox.shape',0);self.choose('create-extra.polyvox.style',3)
        return self.capture()
