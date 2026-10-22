"""Actual Avatar/People QML controls over the existing normal Pico input route."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import math
import re
import time
from urllib.parse import urlsplit
from adapters.native_feature_observation import exact,need
from adapters.token_create_ui import nonce,scope,navigation,metadata as navigation_metadata
from adapters.normal_ui import NativeUIError

VERSION=1
STATIC={'avatar.'+s for s in ('entry','page','url','wearables','settings','scale','settings.scrollbar',
    'bookmark.add','bookmark.manage','bookmark.previous','bookmark.next','dialog.input','dialog.confirm','dialog.cancel',
    'wearable.add','wearable.remove')}|{'people.'+s for s in ('entry','page','nearby','connections','RequestConnection',
    'ConnectionAccept','ConnectionDecline','ConnectionCancel')}


def control_id(value):
    return type(value) is str and (navigation(value) or value in STATIC or re.fullmatch(r'(?:avatar\.bookmark\.row\.|people\.row\.)(?:0|[1-9][0-9]{0,2})',value) is not None
        or re.fullmatch(r'people\.remove\.[A-Za-z0-9_.-]{1,128}',value) is not None)


def text(value):
    need(type(value) is str and len(value)<=4096)
    if re.fullmatch(r'(?:e2e-|hidden-)[0-9a-f]{32}',value):return value
    need(not re.search(r'[\x00-\x20\x7f]',value))
    try:
        parts=urlsplit(value)
        need(not parts.username and not parts.password and not parts.fragment)
        need(parts.scheme in ('http','https') and bool(parts.hostname) or parts.scheme=='qrc' and parts.path.startswith('/') and not parts.netloc)
    except ValueError:need(False)
    return value


def metadata(row):
    need(type(row) is dict and control_id(row.get('id')) and nonce(row.get('token')))
    if navigation(row['id']):return navigation_metadata(row)
    identifier=row['id'];fields={'id','token','enabled','focused','inputReady'}
    need(all(type(row.get(k)) is bool for k in ('enabled','focused','inputReady')) and (not row['inputReady'] or row['enabled']))
    if identifier.endswith('.page'):need(not row['inputReady'])
    if identifier.startswith('avatar.') and identifier!='avatar.entry':fields.add('managing');need(type(row.get('managing')) is bool)
    if identifier=='avatar.dialog.input':fields.add('text');need(type(row.get('text')) is str and len(row['text'])<=4096)
    if 'dialogTitle' in row or 'dialogSource' in row:
        fields|={'dialogTitle','dialogSource'};need(all(type(row.get(k)) is str and 0<len(row[k])<=512 for k in ('dialogTitle','dialogSource')))
    if identifier=='avatar.scale':
        fields|={'value','from','to','stepSize'};need(all(type(row.get(k)) in (int,float) and math.isfinite(row[k]) for k in ('value','from','to','stepSize')))
        need(row['from']==1 and row['to']==40 and row['from']<=row['value']<=row['to'] and row['stepSize']>=0)
    if identifier.startswith('avatar.bookmark.row.'):fields.add('bookmarkName');need(type(row.get('bookmarkName')) is str and len(row['bookmarkName'])<=512)
    if identifier=='avatar.wearable.remove':
        fields|={'wearableId','wearableUrlSha256'};need(type(row.get('wearableId')) is str and len(row['wearableId'])<=64
            and type(row.get('wearableUrlSha256')) is str and re.fullmatch('[0-9a-f]{64}',row['wearableUrlSha256']))
    if identifier.startswith('people.') and identifier!='people.entry':
        fields|={'consent','tab'};need(type(row.get('consent')) is dict and type(row.get('tab')) is str and row['tab'] in ('nearbyTab','connectionsTab'))
    if 'peerSession' in row or 'userName' in row:
        fields|={'peerSession','userName'};need(all(type(row.get(k)) is str and len(row[k])<=128 for k in ('peerSession','userName')))
    exact(row,fields);return row


def snapshot(value):
    exact(value,{'avatarPeopleControlsVersion','open','ready','scope','controls'})
    need(type(value['avatarPeopleControlsVersion']) is int and value['avatarPeopleControlsVersion']==1
        and all(type(value[k]) is bool for k in ('open','ready')) and type(value['controls']) is list and len(value['controls'])<=384)
    scope(value['scope']);ids=set();tokens=set()
    for row in value['controls']:
        metadata(row);need(row['id'] not in ids and row['token'] not in tokens);ids.add(row['id']);tokens.add(row['token'])
    need(value['open'] or not value['controls']);return value


def project(value):
    need(type(value.get('avatarPeopleControlsVersion')) is int and value['avatarPeopleControlsVersion']==1)
    return snapshot(dict(avatarPeopleControlsVersion=1,open=value['open'],ready=value['ready'],
        scope=dict(instance=value['bridgeId'],generation=value['generation'],sequence=value['lastCommandSequence'],elapsedMs=value['elapsedMs'],processId=value['processId']),
        controls=deepcopy([r for r in value['controls'] if control_id(r['id'])])))


def same_reference(original,current,identifier):
    snapshot(original);snapshot(current);need(control_id(identifier)
        and all(original['scope'][k]==current['scope'][k] for k in ('instance','generation','sequence','processId'))
        and 0<=current['scope']['elapsedMs']-original['scope']['elapsedMs']<=5000)
    before=[r for r in original['controls'] if r['id']==identifier];after=[r for r in current['controls'] if r['id']==identifier]
    need(len(before)==len(after)==1 and before==after);return before[0]


class PicoAvatarPeopleIO:
    def __init__(self,io):self.io=io
    def capture(self):return project(self.io.capture())
    def input(self,identifier,action,reference,**args):self.io.navigation.input(identifier,action,reference=reference,**args)


class TokenAvatarPeopleUI:
    def __init__(self,io,intent,*,monotonic=time.monotonic,sleep=time.sleep):
        need(callable(intent) and callable(monotonic) and callable(sleep));self.io,self.intent,self.monotonic,self.sleep=io,intent,monotonic,sleep
        self.previous=None;self.clock=None
    def capture(self):
        value=deepcopy(snapshot(self.io.capture()))
        if self.previous is not None:
            a,b=self.previous['scope'],value['scope'];need(all(a[k]==b[k] for k in ('instance','processId')) and b['sequence']>=a['sequence'] and b['elapsedMs']>=a['elapsedMs'])
        self.previous=value;return value
    @staticmethod
    def row(value,identifier,*,ready=True):
        rows=[r for r in value['controls'] if r['id']==identifier];need(len(rows)<=1)
        return rows[0] if rows and (not ready or rows[0]['enabled'] and (navigation(identifier) or rows[0]['inputReady'])) else None
    def now(self):
        value=self.monotonic();need(type(value) in (int,float) and math.isfinite(value) and value>=0 and (self.clock is None or value>=self.clock));self.clock=value;return value
    def wait(self,predicate):
        deadline=self.now()+10
        for attempt in range(102):
            current=self.capture()
            if predicate(current):return current
            remaining=deadline-self.now()
            if remaining<=0 or attempt==101:break
            self.sleep(min(.1,remaining))
        raise NativeUIError('Original Avatar/People transition was not observed')
    def input(self,identifier,action='activate',value=None):
        need(control_id(identifier) and not identifier.endswith('.page') and action in ('activate','replace','scroll','set-value'))
        before=self.capture();row=self.row(before,identifier);need(before['open'] and before['ready'] and row is not None)
        args={}
        if navigation(identifier):need(action=='activate' and value is None)
        if action=='replace':need(identifier=='avatar.dialog.input' and row['focused']);args['text']=text(value)
        elif action=='scroll':need(identifier=='avatar.settings.scrollbar' and value in ('up','down'));args['direction']=value
        elif action=='set-value':need(identifier=='avatar.scale' and type(value) in (int,float) and math.isfinite(value) and 1<=value<=40);args['value']=value
        else:need(value is None)
        self.intent(dict(avatarPeopleInputVersion=1,action=action,controlId=identifier,controlToken=row['token'],scope=deepcopy(before['scope'])))
        self.io.input(identifier,action,before,**args)
        after=self.capture();need(after['scope']['sequence']>before['scope']['sequence']);return after
    def set_url(self,url):
        text(url);self.input('avatar.url');self.wait(lambda v:self.row(v,'avatar.dialog.input') is not None)
        self.input('avatar.dialog.input');self.wait(lambda v:bool(self.row(v,'avatar.dialog.input') and self.row(v,'avatar.dialog.input')['focused']))
        self.input('avatar.dialog.input','replace',url);self.wait(lambda v:bool(self.row(v,'avatar.dialog.input') and self.row(v,'avatar.dialog.input')['text']==url))
        self.input('avatar.dialog.confirm');return self.wait(lambda v:self.row(v,'avatar.dialog.input',ready=False) is None)

    def open(self,page='avatar'):
        need(page in ('avatar','people'));current=self.capture();need(current['open'] and current['ready'])
        if self.row(current,page+'.page',ready=False) is not None:return current
        if self.row(current,page+'.entry') is None:self.input('tablet.home');current=self.capture()
        for n in range(1,33):
            if self.row(current,page+'.entry') is not None:break
            identifier='tablet.page.'+str(n)
            if self.row(current,identifier) is not None:self.input(identifier);current=self.capture()
        need(self.row(current,page+'.entry') is not None);self.input(page+'.entry')
        return self.wait(lambda v:self.row(v,page+'.page',ready=False) is not None)
