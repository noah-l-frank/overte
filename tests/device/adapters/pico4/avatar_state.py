"""Original advertised/load generations and actual native Avatar/Model state."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import base64
from adapters.native_feature_observation import decode
from adapters.native_avatar_render import _OriginalQuery,envelope,nonce
from adapters.native_feature_observation import exact,integer,number,need
from adapters.pico4.avatar_people_ui import text
from urllib.parse import urlsplit
from adapters.native_graphics_subject import entity_id

FILE='feature-pico-avatar-state.json'
ACTION='feature-pico-avatar-state-observe'


def digest(value):return type(value) is str and len(value)==64 and all(c in '0123456789abcdef' for c in value)
def sha(value):return hashlib.sha256(value.encode()).hexdigest()


def history(value,epoch):
    exact(value,{'modelLoadsVersion','instance','sequence','capturedEpochMs','complete','currentGeneration','requestedSha256','events'})
    need(type(value['modelLoadsVersion']) is int and value['modelLoadsVersion']==1 and nonce(value['instance'])
        and integer(value['sequence'],1) and integer(value['capturedEpochMs'],1,epoch) and value['complete'] is True
        and integer(value['currentGeneration'],0,1000000000) and type(value['events']) is list and len(value['events'])<=256)
    generation=0;requested='';previous=0
    for i,event in enumerate(value['events'],1):
        exact(event,{'eventSequence','generation','kind','capturedEpochMs','requestedSha256','resourceSha256','success'})
        need(type(event['eventSequence']) is int and event['eventSequence']==i and event['kind'] in ('requested','finished')
            and integer(event['capturedEpochMs'],1,value['capturedEpochMs']) and event['capturedEpochMs']>=previous);previous=event['capturedEpochMs']
        if event['kind']=='requested':
            generation+=1;requested=event['requestedSha256'];need(digest(requested) and event['resourceSha256']=='' and event['success'] is None)
        else:need(generation>0 and digest(event['resourceSha256']) and type(event['success']) is bool)
        need(type(event['generation']) is int and event['generation']==generation and event['requestedSha256']==requested)
    need(value['currentGeneration']==generation and value['requestedSha256']==requested);return value


def history_continuity(before,after):
    need(before['instance']==after['instance'] and after['sequence']>before['sequence'] and after['capturedEpochMs']>=before['capturedEpochMs']
        and len(after['events'])>=len(before['events']) and after['events'][:len(before['events'])]==before['events'])


def validate(value,request,pid,epoch):
    exact(request,{'schemaVersion','commandId','action'});need(type(request['schemaVersion']) is int and request['schemaVersion']==1
        and nonce(request['commandId']) and request['action']==ACTION);envelope(value,request,pid,epoch)
    source=value['source'];exact(source,{'picoAvatarStateVersion','sessionId','preferenceUrl','modelName','avatarEntityStorage','requestedUrl','avatarLoads','modelInstance','modelUrl','modelLoads',
        'rigId','loaded','geometry','scale','targetScale','hipsJoint','localRenderingEnabled'})
    need(type(source['picoAvatarStateVersion']) is int and source['picoAvatarStateVersion']==1 and entity_id(source['sessionId']) and source['sessionId']!='00000000-0000-0000-0000-000000000000'
        and nonce(source['modelInstance']) and integer(source['rigId'],0,2147483647) and all(type(source[k]) is bool for k in ('loaded','localRenderingEnabled'))
        and number(source['scale'],.0001,1000) and number(source['targetScale'],.0001,1000) and type(source['hipsJoint']) is int and -1<=source['hipsJoint']<=65535)
    need(type(source['modelName']) is str and len(source['modelName'])<=512 and not any(ord(c)<32 or ord(c)==127 for c in source['modelName'])
        and type(source['preferenceUrl']) is str and len(source['preferenceUrl'])<=4096)
    if source['preferenceUrl']:text(source['preferenceUrl']);need(urlsplit(source['preferenceUrl']).scheme in ('http','https','qrc'))
    storage(source['avatarEntityStorage'])
    for k in ('requestedUrl','modelUrl'):
        text(source[k]);need(urlsplit(source[k]).scheme in ('http','https','qrc'))
    for k in ('avatarLoads','modelLoads'):history(source[k],value['capturedEpochMs'])
    geometry=source['geometry']
    if geometry is not None:
        exact(geometry,{'instance','url'});need(nonce(geometry['instance']));text(geometry['url']);need(urlsplit(geometry['url']).scheme in ('http','https','qrc'))
    need(source['loaded']==(geometry is not None));return value


def storage(value):
    exact(value,{'avatarEntityStorageVersion','rows'});need(type(value['avatarEntityStorageVersion']) is int and value['avatarEntityStorageVersion']==1
        and type(value['rows']) is list and len(value['rows'])<=128)
    seen=set();total=0
    for row in value['rows']:
        exact(row,{'id','bytes','sha256','base64'});need(entity_id(row['id']) and row['id']!='00000000-0000-0000-0000-000000000000' and row['id'] not in seen
            and integer(row['bytes'],0,65536) and digest(row['sha256']) and type(row['base64']) is str and len(row['base64'])<=87384)
        seen.add(row['id']);total+=row['bytes'];need(total<=65536)
        try:data=base64.b64decode(row['base64'],validate=True)
        except ValueError:need(False)
        need(base64.b64encode(data).decode()==row['base64'] and len(data)==row['bytes'] and hashlib.sha256(data).hexdigest()==row['sha256'])
    need([r['id'] for r in value['rows']]==sorted(seen));return value


def continuity(before,after):
    if before is None:return
    need(before['instance']==after['instance'] and after['sequence']>before['sequence'] and before['requestId']!=after['requestId']
        and after['capturedEpochMs']>=before['capturedEpochMs'])
    a,b=before['source'],after['source'];need(a['sessionId']==b['sessionId'] and a['modelInstance']==b['modelInstance'])
    for k in ('avatarLoads','modelLoads'):history_continuity(a[k],b[k])


def failed(source):
    current=source['avatarLoads'];requested=sha(source['requestedUrl'])
    return current['currentGeneration']>0 and current['requestedSha256']==requested and any(
        e['generation']==current['currentGeneration'] and e['requestedSha256']==requested and e['kind']=='finished' and e['success'] is False
        and e['resourceSha256']==requested for e in current['events'])


class NativePicoAvatarState(_OriginalQuery):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs);need(self.ios is False);self.previous=None;self.last_raw=self.last_sha256=None
        original=self.original
        def capture():
            raw=original();self._last_seen_raw=raw;return raw
        self.original=capture

    def read(self):
        value=self._read(self._request(ACTION),validate);continuity(self.previous,value)
        need(decode(self._last_seen_raw)==value);self.last_raw=self._last_seen_raw;self.last_sha256=sha(self.last_raw)
        self.previous=deepcopy(value);return value
    def restore(self,frames):
        need(self.last is None and type(frames) is list and 0<len(frames)<=512)
        for value in frames:
            validate(value,dict(schemaVersion=1,commandId=value.get('requestId'),action=ACTION),self.pid,value['capturedEpochMs'])
            self._advance(value);continuity(self.previous,value);self.previous=self.last=deepcopy(value)
