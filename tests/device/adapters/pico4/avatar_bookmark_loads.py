"""Passive original Qt bookmark connection/capture and dispatch observations.

An expired added capture marker is deliberately not whole-functor, Avatar,
resource or background-task retirement evidence.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
from adapters.native_avatar_render import _OriginalQuery,envelope,nonce
from adapters.native_feature_observation import decode,exact,integer,need,number
from adapters.pico4.avatar_state import digest
from adapters.native_graphics_subject import entity_id

ACTION='feature-pico-avatar-bookmark-loads-observe'
FILE='feature-pico-avatar-bookmark-loads.json'
FLAGS=('senderAlive','captureAlive','connectionObserved','connected','disconnectObserved','disconnected','completed','ownerThreadOnly')
FIXED=('id','nameSha256','urlSha256','avatarInstance','sessionId','createdEpochMs','bookmarkScale','bookmarkEntities')


def loads(value,epoch):
    exact(value,{'avatarBookmarkLoadsVersion','instance','capturedEpochMs','rows'})
    need(type(value['avatarBookmarkLoadsVersion']) is int and value['avatarBookmarkLoadsVersion']==1 and nonce(value['instance'])
        and integer(value['capturedEpochMs'],1,epoch) and type(value['rows']) is list and len(value['rows'])<=128)
    seen=set()
    for row in value['rows']:
        exact(row,set(FIXED)|set(FLAGS)|{'enteredEpochMs','returnedEpochMs','dispatches','active'})
        need(nonce(row['id']) and row['id'] not in seen and digest(row['nameSha256']) and digest(row['urlSha256']) and nonce(row['avatarInstance'])
            and entity_id(row['sessionId']) and row['sessionId']!='00000000-0000-0000-0000-000000000000'
            and integer(row['createdEpochMs'],1,value['capturedEpochMs']) and number(row['bookmarkScale'],-1e15,1e15)
            and integer(row['bookmarkEntities'],0,128) and all(type(row[k]) is bool for k in FLAGS)
            and integer(row['dispatches'],0,128) and integer(row['active'],0,row['dispatches'])
            and integer(row['enteredEpochMs'],0,value['capturedEpochMs']) and integer(row['returnedEpochMs'],0,value['capturedEpochMs']))
        if row['dispatches']==0:need(row['enteredEpochMs']==row['returnedEpochMs']==row['active']==0 and not row['completed'] and not row['disconnectObserved'])
        else:need(row['enteredEpochMs']>=row['createdEpochMs'])
        if row['returnedEpochMs']:need(row['returnedEpochMs']>=row['createdEpochMs'])
        if row['dispatches'] and not row['active']:need(row['returnedEpochMs']>=row['enteredEpochMs'])
        if row['active']:need(row['captureAlive'])
        if row['completed']:need(row['dispatches']>=1 and row['disconnectObserved'])
        if row['connected']:need(row['connectionObserved'])
        if row['disconnected']:need(row['disconnectObserved'])
        seen.add(row['id'])
    return value


def validate(value,request,pid,epoch):
    exact(request,{'schemaVersion','commandId','action'})
    need(type(request['schemaVersion']) is int and request['schemaVersion']==1 and nonce(request['commandId']) and request['action']==ACTION)
    envelope(value,request,pid,epoch);source=value['source']
    exact(source,{'picoAvatarBookmarkLoadsVersion','instance','loads'})
    need(type(source['picoAvatarBookmarkLoadsVersion']) is int and source['picoAvatarBookmarkLoadsVersion']==1 and nonce(source['instance']))
    loads(source['loads'],value['capturedEpochMs']);need(source['loads']['capturedEpochMs']>=value['requestedEpochMs']);return value


def continuity(before,after):
    if before is None:return
    a,b=before['source'],after['source'];x,y=a['loads'],b['loads']
    need(before['instance']==after['instance'] and after['sequence']>before['sequence'] and before['requestId']!=after['requestId']
        and after['capturedEpochMs']>=before['capturedEpochMs'] and a['instance']==b['instance'] and x['instance']==y['instance']
        and y['capturedEpochMs']>=x['capturedEpochMs'] and len(y['rows'])>=len(x['rows']))
    for old,new in zip(x['rows'],y['rows']):
        need(all(old[k]==new[k] for k in FIXED) and new['dispatches']>=old['dispatches']
            and new['enteredEpochMs']>=old['enteredEpochMs'] and new['returnedEpochMs']>=old['returnedEpochMs'])
        need(all(not old[k] or new[k] for k in ('connectionObserved','connected','disconnectObserved','disconnected','completed')))
        need(all(old[k] or not new[k] for k in ('senderAlive','captureAlive','ownerThreadOnly')))


class NativePicoAvatarBookmarkLoads(_OriginalQuery):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs);need(self.ios is False);self.previous=None;self.last_raw=self.last_sha256=None
        original=self.original
        def capture():
            raw=original();self._last_seen_raw=raw;return raw
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
