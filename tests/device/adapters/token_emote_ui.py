"""Original Emote widgets and ordinary inputs, never animation verdicts."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from functools import wraps
import re
import time
from adapters.native_feature_observation import exact,integer,need,number
from adapters.normal_ui import NativeUIError

VERSION=1
NAMES=('Crying','Surprised','Dancing','Cheering','Waving','Fall','Pointing','Clapping','Sit','Love')


def control_id(value):
    return type(value) is str and (value in ('emote.page','emote.grid','emote.entry','tablet.home')
        or value.startswith('emote.play.') and value[len('emote.play.'):] in NAMES
        or re.fullmatch(r'tablet\.page\.(?:[1-9]|[12][0-9]|3[0-2])',value) is not None)


def nonce(value):return type(value) is str and re.fullmatch('[0-9a-f]{32}',value) is not None


def metadata(row):
    need(type(row) is dict and control_id(row.get('id')) and nonce(row.get('token')))
    base={'id','token','enabled','focused','inputReady'};identifier=row['id']
    need(all(type(row.get(k)) is bool for k in ('enabled','focused','inputReady')))
    if identifier=='emote.page':
        exact(row,base|{'profile','activeName','names','componentSourceSha256'})
        need(row['profile']=='phone-native-chooser-v1' and row['activeName'] in ('',*NAMES)
            and type(row['activeName']) is str and type(row['names']) is list and len(row['names'])==10
            and all(type(name) is str for name in row['names']) and sorted(row['names'])==sorted(NAMES)
            and type(row['componentSourceSha256']) is str and re.fullmatch('[0-9a-f]{64}',row['componentSourceSha256'])
            and row['inputReady'] is False)
    elif identifier=='emote.grid':
        exact(row,base|{'contentY','originY','contentHeight','viewportHeight','moving','dragging'})
        need(number(row['contentY'],-1e6,1e6) and number(row['originY'],-1e6,1e6)
            and number(row['contentHeight'],.1,1e6) and number(row['viewportHeight'],.1,4096)
            and type(row['moving']) is bool and type(row['dragging']) is bool
            and (not row['inputReady'] or not row['moving'] and not row['dragging']))
    elif identifier.startswith('emote.play.'):
        exact(row,base|{'name','index','highlighted'})
        need(row['name']==identifier[len('emote.play.'):] and integer(row['index'],0,9)
            and type(row['highlighted']) is bool)
    else:exact(row,base)
    return row


def snapshot(value):
    exact(value,{'emoteControlsVersion','open','ready','scope','controls'})
    need(type(value['emoteControlsVersion']) is int and value['emoteControlsVersion']==VERSION
        and type(value['open']) is bool and type(value['ready']) is bool and type(value['controls']) is list and len(value['controls'])<=64)
    scope=value['scope'];exact(scope,{'instance','generation','sequence','sourceSequence','elapsedMs','capturedEpochMs','processId'})
    need(nonce(scope['instance']) and nonce(scope['generation']) and integer(scope['sequence'])
        and integer(scope['sourceSequence'],1) and integer(scope['elapsedMs']) and integer(scope['capturedEpochMs'],1)
        and integer(scope['processId'],1))
    ids=set();tokens=set();page=None
    for row in value['controls']:
        metadata(row);need(row['id'] not in ids and row['token'] not in tokens);ids.add(row['id']);tokens.add(row['token'])
        if row['id']=='emote.page':page=row
    buttons=[row for row in value['controls'] if row['id'].startswith('emote.play.')]
    if page is None:need(not buttons and 'emote.grid' not in ids)
    else:
        need('emote.grid' in ids)
        need(all(page['names'][row['index']]==row['name'] and row['highlighted']==(page['activeName']==row['name']) for row in buttons))
    need((value['open'] and value['ready']) or not value['controls'])
    return value


def same_reference(original,current,identifier):
    snapshot(original);snapshot(current)
    left,right=original['scope'],current['scope']
    need(all(left[k]==right[k] for k in ('instance','generation','sequence','processId'))
        and right['sourceSequence']>left['sourceSequence'] and 0<=right['elapsedMs']-left['elapsedMs']<=5000)
    before=[row for row in original['controls'] if row['id']==identifier]
    after=[row for row in current['controls'] if row['id']==identifier]
    need(len(before)==len(after)==1 and before[0]==after[0]);return before[0]


def bounded(method):
    @wraps(method)
    def operation(self,*args,**kwargs):
        outer=self.started is None
        if outer:self.started=self.now()
        try:
            self.now();value=method(self,*args,**kwargs);self.now();return value
        finally:
            if outer:self.started=None
    return operation


class TokenEmoteUI:
    def __init__(self,io,intent,*,monotonic=time.monotonic,sleep=time.sleep):
        need(callable(intent) and callable(monotonic) and callable(sleep))
        self.io,self.intent,self.monotonic,self.sleep=io,intent,monotonic,sleep
        self.previous=None;self.clock=None;self.started=None

    def now(self):
        value=self.monotonic();need(number(value,0,1e15) and (self.clock is None or value>=self.clock));self.clock=value
        need(self.started is None or value-self.started<20);return value

    def capture(self):
        self.now();value=snapshot(self.io.capture());self.now();scope=value['scope']
        if self.previous is not None:
            old=self.previous['scope'];need(all(scope[k]==old[k] for k in ('instance','generation','processId'))
                and scope['sourceSequence']>old['sourceSequence'] and scope['sequence']>=old['sequence']
                and scope['elapsedMs']>=old['elapsedMs'] and scope['capturedEpochMs']>=old['capturedEpochMs'])
        self.previous=deepcopy(value);return value

    @staticmethod
    def row(value,identifier):
        rows=[row for row in value['controls'] if row['id']==identifier];need(len(rows)<=1);return rows[0] if rows else None

    def wait(self,predicate):
        started=self.now()
        for attempt in range(102):
            value=self.capture();now=self.now();need(now-started<=10)
            if predicate(value):return value
            if now-started>=10 or attempt==101:break
            self.sleep(min(.1,10-(now-started)))
        raise NativeUIError('Original Emote widget transition was not observed')

    @bounded
    def input(self,identifier,*,direction=None):
        need(control_id(identifier) and identifier!='emote.page')
        need(direction in ('up','down') if identifier=='emote.grid' else direction is None)
        original=self.capture();row=self.row(original,identifier)
        need(original['open'] and original['ready'] and row is not None and row['enabled'] and row['inputReady'])
        action='scroll' if direction is not None else 'activate';scope=original['scope']
        need(self.intent(dict(controlId=identifier,action=action,sequence=scope['sequence']+1,
            instance=scope['instance'],generation=scope['generation'],direction=direction,original=deepcopy(original))) is not False)
        if direction is None:self.io.activate(identifier,reference=original)
        else:self.io.scroll(identifier,direction,reference=original)
        current=self.capture()['scope'];need(current['sequence']==scope['sequence']+1)
        return original

    @bounded
    def open(self):
        current=self.capture();need(current['open'] and current['ready'])
        if self.row(current,'emote.page') is not None:return
        if self.row(current,'emote.entry') is None:
            self.input('tablet.home')
            current=self.capture()
        for page in range(1,33):
            if self.row(current,'emote.entry') is not None:break
            identifier='tablet.page.'+str(page)
            if self.row(current,identifier) is not None:self.input(identifier);current=self.capture()
        need(self.row(current,'emote.entry') is not None);self.input('emote.entry')
        self.wait(lambda value:self.row(value,'emote.page') is not None)

    @bounded
    def visible(self,name):
        need(type(name) is str and name in NAMES)
        identifier='emote.play.'+name
        for _attempt in range(12):
            current=self.wait(lambda value:(self.row(value,'emote.grid') or {}).get('inputReady') is True)
            page=self.row(current,'emote.page');need(page is not None)
            grid=self.row(current,'emote.grid');row=self.row(current,identifier)
            if row is not None and row['enabled'] and row['inputReady']:return row
            visible=[r['index'] for r in current['controls'] if r['id'].startswith('emote.play.') and r['inputReady']]
            need(bool(visible));index=page['names'].index(name)
            need(index<min(visible) or index>max(visible))
            direction='up' if index<min(visible) else 'down';before=grid['contentY']
            self.input('emote.grid',direction=direction)
            self.wait(lambda value:((self.row(value,'emote.grid') or {}).get('contentY',before)-before)
                *(-1 if direction=='up' else 1)>.01)
        raise NativeUIError('Original Emote button remains outside the viewport')

    @bounded
    def play(self,name):
        self.visible(name);self.input('emote.play.'+name)
        # A consumed widget input proves neither Rig override nor visible pose.

    @bounded
    def cancel(self):
        current=self.capture();page=self.row(current,'emote.page');need(page is not None)
        if page['activeName']:self.play(page['activeName'])

    @bounded
    def close(self):
        if self.row(self.capture(),'emote.page') is None:return
        self.input('tablet.home');self.wait(lambda value:self.row(value,'emote.page') is None)
