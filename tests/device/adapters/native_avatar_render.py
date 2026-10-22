"""Original loaded local-avatar/render view metadata; no visual verdict."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
import re
import time
import uuid

from adapters.native_feature_observation import decode,exact,fresh,integer,need,number
from adapters.native_graphics_subject import vector,rotation
from adapters.normal_ui import NativeUIError
from adapters.world_render_evidence import recorded_view,digest

VERSION=1
FILE='feature-avatar-render.json'
LIMIT=262144
EMPTY_SHA256=hashlib.sha256(b'').hexdigest()


def nonce(value,*,ios=False):
    return type(value) is str and re.fullmatch(('ios-' if ios else '')+'[0-9a-f]{32}',value) is not None


def command(value,*,ios=False):
    exact(value,{'schemaVersion','commandId','action'})
    need(type(ios) is bool and type(value['schemaVersion']) is int and value['schemaVersion']==1
         and value['action']=='feature-avatar-render-observe' and nonce(value['commandId'],ios=ios))
    return value


def envelope(value,request,pid,epoch):
    exact(value,{'schemaVersion','requestId','instance','sequence','processId','requestedEpochMs','capturedEpochMs','source'})
    need(type(value['schemaVersion']) is int and value['schemaVersion']==1 and value['requestId']==request['commandId']
         and nonce(value['instance']) and integer(value['sequence'],1,9007199254740991)
         and integer(value['processId'],1) and value['processId']==pid
         and integer(value['requestedEpochMs'],1) and integer(value['capturedEpochMs'],1)
         and 0<=value['capturedEpochMs']-value['requestedEpochMs']<1500)
    fresh(value['capturedEpochMs'],epoch)


def loaded_source(present,sha):
    need(type(present) is bool and digest(sha) and (present or sha==EMPTY_SHA256))


def validate(value,request,pid,epoch):
    command(request,ios=request['commandId'].startswith('ios-'));envelope(value,request,pid,epoch)
    source=value['source']
    exact(source,{'avatarRenderVersion','modelInstance','rigId','loaded','visible','addedToScene',
        'localRenderingEnabled','avatarShouldRender','geometry','pose','cameraMode','view'})
    need(type(source['avatarRenderVersion']) is int and source['avatarRenderVersion']==VERSION
         and nonce(source['modelInstance']) and integer(source['rigId'],0,2147483647)
         and all(type(source[k]) is bool for k in ('loaded','visible','addedToScene','localRenderingEnabled','avatarShouldRender'))
         and type(source['cameraMode']) is str and len(source['cameraMode'])<=64 and '\0' not in source['cameraMode'])
    geometry=source['geometry']
    if geometry is not None:
        exact(geometry,{'instance','sourcePresent','sourceSha256'});need(nonce(geometry['instance']))
        loaded_source(geometry['sourcePresent'],geometry['sourceSha256'])
    need(source['loaded']==(geometry is not None))
    pose=source['pose'];exact(pose,{'feetPosition','orientation','modelScale'})
    vector(pose['feetPosition'],3,-1e6,1e6);rotation(pose['orientation']);need(number(pose['modelScale'],.0001,1000))
    recorded_view(source['view'])
    return value


class _OriginalQuery:
    """Bounded read-only transport. Original timestamps survive copy/replay."""
    def __init__(self,send,read,clock_ms,guard,pid,*,ios=False,monotonic=time.monotonic,sleep=time.sleep):
        need(all(callable(v) for v in (send,read,clock_ms,guard,monotonic,sleep)) and integer(pid,1) and type(ios) is bool)
        self.send,self.original,self.clock_ms,self.guard,self.pid=send,read,clock_ms,guard,pid
        self.ios,self.monotonic,self.sleep=ios,monotonic,sleep
        self.last=None

    def _advance(self,value):
        if self.last is not None:
            need(value['instance']==self.last['instance'] and value['sequence']>self.last['sequence']
                 and value['capturedEpochMs']>=self.last['capturedEpochMs'] and value['requestId']!=self.last['requestId'])

    def _read(self,request,validator):
        try:
            started=previous=self.monotonic();need(number(started,0,1e15))
            need(self.guard() is not False)
            requested=self.clock_ms();need(integer(requested,1))
            self.send(request)
            for attempt in range(51):
                need(self.guard() is not False)
                raw=self.original();need(type(raw) is str and len(raw.encode())<=LIMIT)
                try:value=decode(raw) if raw else None
                except json.JSONDecodeError:value=None
                need(self.guard() is not False)
                now=self.monotonic();need(number(now,0,1e15) and now>=previous and now-started<(1.5 if self.ios else 5))
                previous=now
                if type(value) is dict and value.get('requestId')==request['commandId']:
                    epoch=value.get('capturedEpochMs') if self.ios else self.clock_ms()
                    need(integer(epoch,1) and (self.ios or epoch>=requested))
                    validator(value,request,self.pid,epoch);self._advance(value)
                    need(self.ios or value['requestedEpochMs']>=requested)
                    observed=now
                    result=deepcopy(value)
                    need(self.guard() is not False)
                    current=self.monotonic();need(number(current,0,1e15) and previous<=current
                        and current-started<(1.5 if self.ios else 5))
                    clock=self.clock_ms();need(integer(clock,1) and (self.ios or clock>=epoch))
                    final=self.monotonic();need(number(final,0,1e15) and current<=final
                        and final-started<(1.5 if self.ios else 5))
                    # A frozen/reversed device clock cannot hide time consumed
                    # by final guards, file decoding or copying an original.
                    floor=epoch+int((final-observed)*1000)
                    validator(result,request,self.pid,max(floor,clock) if not self.ios else floor)
                    retained=deepcopy(result)
                    final=self.monotonic();need(number(final,0,1e15) and final>=current
                        and final-started<(1.5 if self.ios else 5))
                    validator(result,request,self.pid,max(epoch+int((final-observed)*1000),clock) if not self.ios else epoch+int((final-observed)*1000))
                    need(self.guard() is not False)
                    delivered=self.clock_ms();need(integer(delivered,1) and (self.ios or delivered>=clock))
                    finished=self.monotonic();need(number(finished,final,1e15)
                        and finished-started<(1.5 if self.ios else 5))
                    validator(result,request,self.pid,max(epoch+int((finished-observed)*1000),delivered) if not self.ios else epoch+int((finished-observed)*1000))
                    self.last=retained
                    return result
                if attempt<50:self.sleep(.1)
        except Exception:
            raise NativeUIError('Original avatar/render provenance is unavailable or invalid') from None
        raise NativeUIError('Original avatar/render provenance did not produce this request')

    def _request(self,action,**selectors):
        return dict(schemaVersion=1,commandId=('ios-' if self.ios else '')+uuid.uuid4().hex,action=action,**selectors)


class NativeAvatarRender(_OriginalQuery):
    def read(self):
        return self._read(command(self._request('feature-avatar-render-observe'),ios=self.ios),validate)

    def restore(self,frames):
        need(self.last is None and type(frames) is list and 0<len(frames)<=256)
        for frame in frames:
            request=command(dict(schemaVersion=1,commandId=frame.get('requestId'),action='feature-avatar-render-observe'),ios=self.ios)
            validate(frame,request,self.pid,frame.get('capturedEpochMs'));self._advance(frame);self.last=deepcopy(frame)
