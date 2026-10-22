"""Original NativeCreate voxel tools on the normal candidate-bound Qt route."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import math
import re
import time
from adapters.native_feature_observation import exact,integer,need,number
from adapters.token_create_ui import nonce,scope
from adapters.normal_ui import NativeUIError

VERSION=1
ENUMS=dict(createAppMode=['object','voxel'],voxelEditMode=['single','sphere','cube'],
    voxelEditDynamics=['click','continuous'],voxelPointerMode=['laser','brush'])
COUNTS={'create-voxel.'+k:v for k,v in dict(mode=2,shape=3,dynamics=2,pointer=2).items()}
FIELDS={'create-voxel.diameter','create-voxel.reach'}
IDS=set(COUNTS)|FIELDS|{'create-voxel.remove','create-voxel.apply'}


def settings(value):
    exact(value,set(ENUMS)|{'voxelSphereSize','voxelBrushLength','voxelRemove'})
    need(all(type(value[k]) is str and value[k] in allowed for k,allowed in ENUMS.items())
        and type(value['voxelRemove']) is bool and number(value['voxelSphereSize'],0,100) and value['voxelSphereSize']>0
        and number(value['voxelBrushLength'],0,100))
    for identifier,key in (('diameter','voxelSphereSize'),('reach','voxelBrushLength')):text('create-voxel.'+identifier,str(value[key]))
    return value


def text(identifier,value):
    need(identifier in FIELDS and type(value) is str and len(value)<=40
        and re.fullmatch(r'(?:0|[1-9][0-9]{0,2})(?:\.[0-9]{1,17})?(?:e[+-]?[0-9]{1,2})?',value))
    parsed=float(value);need(math.isfinite(parsed) and parsed<=100 and (parsed>0 if identifier.endswith('diameter') else parsed>=0));return value


def metadata(row):
    need(type(row) is dict and row.get('id') in IDS and nonce(row.get('token')))
    identifier=row['id'];base={'id','token','enabled','focused','inputReady'}
    need(all(type(row.get(k)) is bool for k in ('enabled','focused','inputReady')) and (not row['inputReady'] or row['enabled']))
    if identifier in COUNTS:
        exact(row,base|{'count','currentIndex'}|({'settings'} if identifier=='create-voxel.mode' else set()))
        need(type(row['count']) is int and row['count']==COUNTS[identifier] and integer(row['currentIndex'],0,row['count']-1))
        if identifier=='create-voxel.mode':settings(row['settings'])
    elif identifier in FIELDS:exact(row,base|{'text'});text(identifier,row['text'])
    elif identifier=='create-voxel.remove':exact(row,base|{'checked'});need(type(row['checked']) is bool)
    else:exact(row,base)
    return row


def snapshot(value):
    exact(value,{'createVoxelControlsVersion','open','ready','scope','controls'})
    need(type(value['createVoxelControlsVersion']) is int and value['createVoxelControlsVersion']==VERSION
        and all(type(value[k]) is bool for k in ('open','ready')) and type(value['controls']) is list and len(value['controls'])<=len(IDS))
    scope(value['scope']);ids=set();tokens=set()
    for row in value['controls']:
        metadata(row);need(row['id'] not in ids and row['token'] not in tokens);ids.add(row['id']);tokens.add(row['token'])
    need(value['open'] or not value['controls']);return value


def project(value):
    need(type(value.get('createVoxelControlsVersion')) is int and value['createVoxelControlsVersion']==VERSION)
    return snapshot(dict(createVoxelControlsVersion=VERSION,open=value['open'],ready=value['ready'],
        scope=dict(instance=value['bridgeId'],generation=value['generation'],sequence=value['lastCommandSequence'],elapsedMs=value['elapsedMs'],processId=value['processId']),
        controls=deepcopy([r for r in value['controls'] if r['id'] in IDS])))


def same_reference(original,current,identifier):
    snapshot(original);snapshot(current);a,b=original['scope'],current['scope']
    need(identifier in IDS and all(a[k]==b[k] for k in ('instance','generation','sequence','processId')) and 0<=b['elapsedMs']-a['elapsedMs']<=5000)
    old=[r for r in original['controls'] if r['id']==identifier];new=[r for r in current['controls'] if r['id']==identifier]
    need(len(old)==len(new)==1 and old==new);return old[0]


class PicoCreateVoxelIO:
    def __init__(self,original):self.original=original
    def capture(self):return project(self.original.capture())
    def activate(self,identifier,reference):self.original.navigation.input(identifier,reference=reference)
    def replace(self,identifier,value,reference):self.original.navigation.input(identifier,'replace',value,reference=reference)
    def choose(self,identifier,index,reference):self.original.navigation.input(identifier,'select-index',index=index,reference=reference)


class TokenCreateVoxelUI:
    def __init__(self,io,intent,*,monotonic=time.monotonic,sleep=time.sleep):
        need(all(callable(v) for v in (intent,monotonic,sleep)));self.io,self.intent,self.monotonic,self.sleep=io,intent,monotonic,sleep
        self.previous=None;self.clock=None
    def capture(self):
        value=deepcopy(snapshot(self.io.capture()));b=value['scope']
        if self.previous is not None:
            a=self.previous['scope'];need(a['instance']==b['instance'] and a['processId']==b['processId'] and a['sequence']<=b['sequence'] and a['elapsedMs']<=b['elapsedMs'])
        self.previous=value;return value
    @staticmethod
    def row(value,identifier):
        rows=[r for r in value['controls'] if r['id']==identifier];need(len(rows)<=1)
        return rows[0] if rows and rows[0]['enabled'] and rows[0]['inputReady'] else None
    def wait(self,predicate):
        started=self.monotonic();need(number(started,0,1e15));previous=started
        for attempt in range(102):
            value=self.capture();now=self.monotonic();need(number(now,previous,started+10));previous=now
            if predicate(value):return value
            need(attempt<101);self.sleep(min(.1,max(0,started+10-now)))
        raise NativeUIError('Original voxel tool transition is unavailable')
    def input(self,identifier,action='activate',value=None):
        before=self.capture();row=self.row(before,identifier);need(before['open'] and before['ready'] and row is not None)
        if action=='replace':need(identifier in FIELDS and row['focused']);text(identifier,value)
        elif action=='select-index':need(identifier in COUNTS and integer(value,0,COUNTS[identifier]-1))
        else:need(action=='activate' and value is None)
        self.intent(dict(createVoxelInputVersion=VERSION,action=action,controlId=identifier,controlToken=row['token'],scope=deepcopy(before['scope'])))
        if action=='replace':self.io.replace(identifier,value,before)
        elif action=='select-index':self.io.choose(identifier,value,before)
        else:self.io.activate(identifier,before)
        after=self.capture();need(after['scope']['sequence']>before['scope']['sequence']);return after
    def reveal(self,identifier,scroll):
        need(identifier in IDS and callable(scroll))
        for direction in ('up','down'):
            for attempt in range(33):
                current=self.capture()
                if self.row(current,identifier):return current
                if not scroll(direction):break
                need(attempt<32)
        raise NativeUIError('Original voxel tool could not be revealed')
    def choose(self,identifier,index,scroll):
        self.reveal(identifier,scroll);self.input(identifier);self.input(identifier,'select-index',index)
        return self.wait(lambda v:bool(self.row(v,identifier) and self.row(v,identifier)['currentIndex']==index))
    def replace(self,identifier,value,scroll):
        text(identifier,value);self.reveal(identifier,scroll);self.input(identifier)
        self.wait(lambda v:bool(self.row(v,identifier) and self.row(v,identifier)['focused']));self.input(identifier,'replace',value)
        return self.wait(lambda v:bool(self.row(v,identifier) and self.row(v,identifier)['text']==value))
