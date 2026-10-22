"""Independent original AvatarBookmarks cache and physical JSON source."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import hashlib
from adapters.native_avatar_render import _OriginalQuery,envelope,nonce
from adapters.native_feature_observation import decode,exact,integer,need
from adapters.pico4.avatar_state import digest

ACTION='feature-pico-avatar-bookmarks-observe'
FILE='feature-pico-avatar-bookmarks.json'


def bytes_of(value,limit):
    need(type(value) is str and len(value)<=4*((limit+2)//3))
    try:raw=base64.b64decode(value,validate=True)
    except (ValueError,TypeError):need(False)
    need(len(raw)<=limit and base64.b64encode(raw).decode()==value);return raw


def storage(value,epoch):
    exact(value,{'avatarBookmarkStorageVersion','capturedEpochMs','pathSha256','present','file','rawBase64','rawSha256','cacheBase64','mapSha256','bookmarks'})
    need(type(value['avatarBookmarkStorageVersion']) is int and value['avatarBookmarkStorageVersion']==1
        and integer(value['capturedEpochMs'],1,epoch) and type(value['present']) is bool and type(value['bookmarks']) is dict
        and len(value['bookmarks'])<=1000 and all(type(k) is str and k and len(k)<=4096 for k in value['bookmarks']))
    need(all(digest(value[k]) for k in ('pathSha256','rawSha256','mapSha256')))
    raw=bytes_of(value['rawBase64'],262144);cache=bytes_of(value['cacheBase64'],262144)
    need(hashlib.sha256(raw).hexdigest()==value['rawSha256'] and hashlib.sha256(cache).hexdigest()==value['mapSha256']
        and decode(cache.decode('utf-8'))==value['bookmarks'])
    if not value['present']:need(value['file'] is None and raw==b'' and value['bookmarks']=={})
    else:
        exact(value['file'],{'bytes','sha256','revisionSha256'})
        need(integer(value['file']['bytes'],1,262144) and value['file']['bytes']==len(raw)
            and value['file']['sha256']==value['rawSha256'] and digest(value['file']['revisionSha256'])
            and decode(raw.decode('utf-8'))==value['bookmarks'])
    return value


def validate(value,request,pid,epoch):
    envelope(value,request,pid,epoch)
    exact(value['source'],{'picoAvatarBookmarksVersion','instance','storage'});source=value['source']
    need(type(source['picoAvatarBookmarksVersion']) is int and source['picoAvatarBookmarksVersion']==1 and nonce(source['instance']))
    storage(source['storage'],value['capturedEpochMs'])
    need(source['storage']['capturedEpochMs']>=value['requestedEpochMs']);return value


def continuity(before,after):
    if before is None:return
    need(before['instance']==after['instance'] and after['sequence']>before['sequence'] and before['requestId']!=after['requestId']
        and after['capturedEpochMs']>=before['capturedEpochMs'] and before['source']['instance']==after['source']['instance']
        and before['source']['storage']['pathSha256']==after['source']['storage']['pathSha256']
        and after['source']['storage']['capturedEpochMs']>=before['source']['storage']['capturedEpochMs'])


class NativePicoAvatarBookmarks(_OriginalQuery):
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
