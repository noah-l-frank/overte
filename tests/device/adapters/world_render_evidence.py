"""Original world-target acquisition reader; no rendered-feature verdict.

Version 1 deliberately refuses stereo and unimplemented Vulkan readback.
The GPU/backend hook and platform original-file transport must be implemented
before this internal reader can acquire anything on a target.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import hashlib
import io
import json
import re
import time
import uuid
from adapters.native_feature_observation import decode,exact,fresh,integer,need,number
from adapters.normal_ui import NativeUIError

FILE='world-render-observation.json'
IMAGE_PREFIX='world-render-image-'


def image_name(request):
    nonce=request[4:] if request.startswith('ios-') else request
    need(re.fullmatch('[0-9a-f]{32}',nonce) is not None)
    return IMAGE_PREFIX+nonce+'.png'
LIMIT=32*1024*1024
PIXELS=8388608


def digest(value):return type(value) is str and re.fullmatch('[0-9a-f]{64}',value) is not None


def extent(value):
    return type(value) is list and len(value)==2 and all(integer(v,1,4096) for v in value) and value[0]*value[1]<=PIXELS


def validate(value,request,pid,epoch):
    exact(value,{'schemaVersion','requestId','instance','sequence','requestedEpochMs','capturedEpochMs','processId','source'})
    need(type(value['schemaVersion']) is int and value['schemaVersion']==1 and value['requestId']==request
         and type(value['instance']) is str and re.fullmatch('[0-9a-f]{32}',value['instance']) is not None
         and integer(value['sequence'],1) and integer(value['processId'],1) and value['processId']==pid
         and integer(value['requestedEpochMs'],1) and integer(value['capturedEpochMs'],1)
         and 0<=value['capturedEpochMs']-value['requestedEpochMs']<5000)
    fresh(value['capturedEpochMs'],epoch)
    source=value['source']
    exact(source,{'captureVersion','available','acquisitionSequence','recordedEpochMs','startedEpochMs','capturedEpochMs',
        'backend','stage','view','sourceExtent','sourceViewport','targetExtent','pixelFormat','image'})
    need(type(source['captureVersion']) is int and source['captureVersion']==1 and source['available'] is True
         and integer(source['acquisitionSequence'],1) and source['backend']=='opengl'
         and source['stage']=='tone-map-before-hud' and source['view']=='main-mono'
         and source['pixelFormat']=='rgba8-top-left' and extent(source['sourceExtent']) and extent(source['targetExtent']))
    stamps=[value['requestedEpochMs'],source['recordedEpochMs'],source['startedEpochMs'],source['capturedEpochMs'],value['capturedEpochMs']]
    need(all(integer(v,1) for v in stamps) and stamps==sorted(stamps))
    fresh(source['capturedEpochMs'],epoch)
    viewport=source['sourceViewport']
    need(type(viewport) is list and len(viewport)==4 and all(integer(v,0,4096) for v in viewport)
         and viewport[2]>0 and viewport[3]>0 and viewport[0]+viewport[2]<=source['sourceExtent'][0]
         and viewport[1]+viewport[3]<=source['sourceExtent'][1])
    image=source['image']
    exact(image,{'name','bytes','sha256','pixelSha256','width','height'})
    need(image['name']==image_name(request) and integer(image['bytes'],1,LIMIT) and digest(image['sha256']) and digest(image['pixelSha256'])
         and integer(image['width'],1,4096) and integer(image['height'],1,4096)
         and [image['width'],image['height']]==source['targetExtent'])
    return value


def original_pixels(value,raw):
    from PIL import Image
    image=value['source']['image']
    need(type(raw) is bytes and 0<len(raw)<=LIMIT and len(raw)==image['bytes']
         and hashlib.sha256(raw).hexdigest()==image['sha256'])
    with Image.open(io.BytesIO(raw)) as decoded:
        need(decoded.format=='PNG' and decoded.mode=='RGBA' and decoded.size==(image['width'],image['height']))
        decoded.load()
        need(hashlib.sha256(decoded.tobytes()).hexdigest()==image['pixelSha256'])
    return raw


def measured_scale(value):
    """Ratios from actual rendered source viewport, never a preference getter."""
    source=value['source'];viewport=source['sourceViewport'];target=source['targetExtent']
    return dict(x=viewport[2]/target[0],y=viewport[3]/target[1])


class NativeWorldRenderCapture:
    def __init__(self,send,read,files,clock_ms,guard,pid,*,intent,ios=False,monotonic=time.monotonic,sleep=time.sleep):
        need(all(callable(v) for v in (send,read,clock_ms,guard,intent,monotonic,sleep)) and integer(pid,1) and type(ios) is bool
             and callable(getattr(files,'read',None)))
        self.send,self.original,self.files,self.clock_ms,self.guard,self.pid=send,read,files,clock_ms,guard,pid
        self.ios,self.monotonic,self.sleep,self.intent=ios,monotonic,sleep,intent
        self.instance,self.sequence,self.acquisition,self.captured=None,0,0,0

    def read(self,after_sequence):
        try:
            need(integer(after_sequence) and after_sequence>=self.sequence and self.guard() is not False)
            started=previous=self.monotonic();need(number(started,0,1e15))
            timeout=1.5 if self.ios else 5.0 # Fresh nonce causality bounds age without assuming equal host/native clocks.
            requested=self.clock_ms();need(integer(requested,1))
            request=('ios-' if self.ios else '')+uuid.uuid4().hex
            command=dict(schemaVersion=1,commandId=request,action='feature-world-render-observe')
            self.intent(dict(command)) # Persist potential native image ownership before acquisition.
            now=self.monotonic();need(number(now,0,1e15) and now>=previous and now-started<timeout);previous=now
            need(self.guard() is not False)
            self.send(command)
            for attempt in range(51):
                need(self.guard() is not False)
                raw=self.original()
                try:value=decode(raw) if raw else None
                except json.JSONDecodeError:value=None
                need(self.guard() is not False)
                now=self.monotonic();need(number(now,0,1e15) and now>=previous and now-started<timeout);previous=now
                if type(value) is dict and value.get('requestId')==request:
                    epoch=value.get('capturedEpochMs') if self.ios else self.clock_ms()
                    validate(value,request,self.pid,epoch)
                    source=value['source']
                    need(self.instance in (None,value['instance']) and value['sequence']>after_sequence
                         and source['acquisitionSequence']>self.acquisition and source['capturedEpochMs']>=self.captured
                         and (self.ios or value['requestedEpochMs']>=requested))
                    if callable(getattr(self.files,'bind',None)): self.files.bind(value)
                    png=self.files.read(source['image']['name'])
                    need(self.guard() is not False)
                    now=self.monotonic();need(number(now,0,1e15) and now>=previous and now-started<timeout)
                    previous=now
                    if not self.ios:fresh(source['capturedEpochMs'],self.clock_ms())
                    original_pixels(value,png)
                    need(self.guard() is not False)
                    now=self.monotonic();need(number(now,0,1e15) and now>=previous and now-started<timeout)
                    if not self.ios:fresh(source['capturedEpochMs'],self.clock_ms())
                    self.instance,self.sequence,self.acquisition,self.captured=value['instance'],value['sequence'],source['acquisitionSequence'],source['capturedEpochMs']
                    return value,png
                if attempt<50:self.sleep(0.1)
        except Exception:
            raise NativeUIError('Original world render acquisition is unavailable or invalid') from None
        raise NativeUIError('Original world render acquisition did not produce this request')
