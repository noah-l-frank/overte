"""Fresh original MyAvatar model-setter Qt connection observations.

Weak capture expiration is deliberately separate from Model/HFM/renderer,
Avatar/sender destruction and whole feature retirement.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
from adapters.native_avatar_render import _OriginalQuery,envelope,nonce
from adapters.native_feature_observation import decode,exact,integer,need
from adapters.native_graphics_subject import entity_id
from adapters.pico4.avatar_state import digest

ACTION='feature-pico-avatar-model-connections-observe'
FILE='feature-pico-avatar-model-connections.json'
FLAGS={'ownerAlive','senderAlive','captureAlive','connected','disconnected','completed','ownerThreadOnly'}
FIXED={'id','urlSha256','change','createdEpochMs'}


def connections(value,epoch):
    exact(value,{'avatarModelConnectionsVersion','instance','capturedEpochMs','rows'})
    need(type(value['avatarModelConnectionsVersion']) is int and value['avatarModelConnectionsVersion']==1
        and nonce(value['instance']) and integer(value['capturedEpochMs'],1,epoch)
        and type(value['rows']) is list and len(value['rows'])<=128)
    seen=set();change=0
    for row in value['rows']:
        exact(row,FIXED|FLAGS|{'enteredEpochMs','returnedEpochMs','dispatches','active'})
        need(nonce(row['id']) and row['id'] not in seen and digest(row['urlSha256'])
            and integer(row['change'],change+1,2147483647)
            and integer(row['createdEpochMs'],1,value['capturedEpochMs'])
            and all(type(row[key]) is bool for key in FLAGS)
            and integer(row['dispatches'],0,128) and integer(row['active'],0,row['dispatches'])
            and integer(row['enteredEpochMs'],0,value['capturedEpochMs'])
            and integer(row['returnedEpochMs'],0,value['capturedEpochMs']))
        if not row['dispatches']:
            need(row['enteredEpochMs']==row['returnedEpochMs']==row['active']==0
                and not row['completed'] and not row['disconnected'])
        else:need(row['enteredEpochMs']>=row['createdEpochMs'])
        if row['returnedEpochMs']:need(row['returnedEpochMs']>=row['createdEpochMs'])
        if row['dispatches'] and not row['active']:need(row['returnedEpochMs']>=row['enteredEpochMs'])
        if row['active']:need(row['captureAlive'])
        if row['completed']:need(row['dispatches']>=1 and row['disconnected'])
        seen.add(row['id']);change=row['change']
    return value


def validate(value,request,pid,epoch):
    exact(request,{'schemaVersion','commandId','action'})
    need(type(request['schemaVersion']) is int and request['schemaVersion']==1
        and nonce(request['commandId']) and request['action']==ACTION)
    envelope(value,request,pid,epoch);source=value['source']
    exact(source,{'picoAvatarModelConnectionsVersion','instance','avatarInstance','sessionId','connections'})
    need(type(source['picoAvatarModelConnectionsVersion']) is int and source['picoAvatarModelConnectionsVersion']==1
        and nonce(source['instance']) and nonce(source['avatarInstance']) and entity_id(source['sessionId'])
        and source['sessionId']!='00000000-0000-0000-0000-000000000000')
    connections(source['connections'],value['capturedEpochMs'])
    need(source['connections']['capturedEpochMs']>=value['requestedEpochMs']);return value


def continuity(before,after):
    if before is None:return
    a,b=before['source'],after['source'];x,y=a['connections'],b['connections']
    need(before['processId']==after['processId'] and before['instance']==after['instance']
        and after['sequence']>before['sequence'] and before['requestId']!=after['requestId']
        and after['capturedEpochMs']>=before['capturedEpochMs']
        and all(a[key]==b[key] for key in ('instance','avatarInstance','sessionId'))
        and x['instance']==y['instance'] and y['capturedEpochMs']>=x['capturedEpochMs']
        and len(y['rows'])>=len(x['rows']))
    for old,new in zip(x['rows'],y['rows']):
        need(all(old[key]==new[key] for key in FIXED)
            and all(new[key]>=old[key] for key in ('dispatches','enteredEpochMs','returnedEpochMs'))
            and all(not old[key] or new[key] for key in ('connected','disconnected','completed'))
            and all(old[key] or not new[key] for key in ('ownerAlive','senderAlive','captureAlive','ownerThreadOnly')))


def retired(value):
    """Only the observed original model-setter connections have returned."""
    return all(row['ownerThreadOnly'] and row['connected'] and row['disconnected'] and row['completed']
        and row['dispatches']==1 and row['active']==0 and not row['captureAlive']
        for row in value['source']['connections']['rows'])


class NativePicoAvatarModelConnections(_OriginalQuery):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs);need(self.ios is False);self.previous=None;self.last_raw=self.last_sha256=None
        original=self.original
        def capture():
            raw=original();need(type(raw) is str and len(raw.encode())<=65536);self._last_seen_raw=raw;return raw
        self.original=capture
    def read(self):
        value=self._read(self._request(ACTION),validate);continuity(self.previous,value)
        need(decode(self._last_seen_raw)==value);self.last_raw=self._last_seen_raw
        self.last_sha256=hashlib.sha256(self.last_raw.encode()).hexdigest();self.previous=deepcopy(value);return value
    def restore(self,frames):
        need(self.last is None and type(frames) is list and 0<len(frames)<=512)
        for value in frames:
            validate(value,dict(schemaVersion=1,commandId=value.get('requestId'),action=ACTION),self.pid,value['capturedEpochMs'])
            self._advance(value);continuity(self.previous,value);self.previous=self.last=deepcopy(value)
