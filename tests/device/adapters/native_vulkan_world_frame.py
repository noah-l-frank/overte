"""Original pre-HUD Vulkan target PNG after its actual submission fence.

No product screenshot API fallback; the caller owns durable command/file intent.
Native images, pixel hashes, byte chunks and retained allocations stay distinct.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
import hashlib
from io import BytesIO
import re
import uuid

from adapters.native_completed_frame import (NativeCompletedFrame,nonce,_validate_frame,_validate_storage)
from adapters.native_feature_observation import exact,fresh,integer,need,number
from adapters.normal_ui import NativeUIError

VERSION=1
STORAGE_VERSION=1
FILE='feature-vulkan-world-frame.json'
LIMIT=131072
PNG_LIMIT=33554432


def command(value):
    need(type(value) is dict)
    extra={'offset'} if value.get('operation')=='read-bytes' else set()
    exact(value,{'schemaVersion','commandId','action','requestId','operation'}|extra)
    need(type(value['schemaVersion']) is int and value['schemaVersion']==1 and value['action']=='feature-vulkan-world-frame'
         and nonce(value['commandId']) and nonce(value['requestId'])
         and value['operation'] in ('read','read-bytes','release','inspect'))
    if extra:need(integer(value['offset'],0,PNG_LIMIT-1))
    return value


def validate(value,request,pid,epoch):
    command(request);need(request['operation']=='read')
    _validate_frame(value,request,pid,epoch,'vulkanWorldFrameVersion',('pixelFormat','pixelsReadEpochMs','image'))
    source=value['source'];image=source['image'];exact(image,{'bytes','sha256','pixelSha256','width','height'})
    need(source['pixelFormat']=='rgba8-top-left' and integer(source['pixelsReadEpochMs'],source['fenceObservedEpochMs'],value['capturedEpochMs'])
         and integer(image['bytes'],1,PNG_LIMIT) and integer(image['width'],1,4096) and integer(image['height'],1,4096)
         and [image['width'],image['height']]==source['targetExtent'])
    for key in ('sha256','pixelSha256'):need(type(image[key]) is str and re.fullmatch('[0-9a-f]{64}',image[key]))
    return value


def storage(value,request,pid,epoch):
    command(request);need(request['operation'] in ('read-bytes','release','inspect'))
    extra={'pngBytes','gpuBufferBytes'}|({'offset','data'} if request['operation']=='read-bytes' else set())
    _validate_storage(value,request,pid,epoch,'vulkanWorldStorageVersion',extra)
    source=value['source']
    need(integer(source['pngBytes'],0,PNG_LIMIT) and integer(source['gpuBufferBytes'],0,67108864)
         and (source['present'] or source['pngBytes']==0))
    if request['operation']=='read-bytes':
        need(source['present'] and not source['retired'] and source['offset']==request['offset']
             and integer(source['offset'],0,source['pngBytes']-1) and type(source['data']) is str and len(source['data'])<=87384)
        raw=base64.b64decode(source['data'],validate=True)
        need(base64.b64encode(raw).decode()==source['data'] and len(raw)==min(65536,source['pngBytes']-source['offset']))
    return value


def absent(value):
    need(type(value) is dict)
    request=dict(schemaVersion=1,action='feature-vulkan-world-frame',**{k:value.get(k) for k in ('commandId','requestId','operation')})
    storage(value,request,value.get('processId'),value.get('capturedEpochMs'))
    source=value['source']
    return source['retired'] and not source['present'] and source['callbacks']==0 and not source['gpuPending'] \
        and source['metadataBytes']==source['pngBytes']==source['gpuBufferBytes']==0


def original_pixels(capture,raw):
    from PIL import Image
    need(type(capture) is dict)
    request=dict(schemaVersion=1,action='feature-vulkan-world-frame',operation='read',
                 commandId=capture.get('commandId'),requestId=capture.get('requestId'))
    validate(capture,request,capture.get('processId'),capture.get('capturedEpochMs'))
    meta=capture['source']['image']
    need(type(raw) is bytes and len(raw)==meta['bytes'] and hashlib.sha256(raw).hexdigest()==meta['sha256']
         and raw[:8]==b'\x89PNG\r\n\x1a\n' and raw[-8:-4]==b'IEND')
    with Image.open(BytesIO(raw)) as image:
        need(image.format=='PNG' and image.mode=='RGBA' and list(image.size)==[meta['width'],meta['height']])
        image.load();need(hashlib.sha256(image.tobytes()).hexdigest()==meta['pixelSha256'])
    return raw


class NativeVulkanWorldFrame(NativeCompletedFrame):
    command_validator=staticmethod(command)
    frame_validator=staticmethod(validate)
    storage_validator=staticmethod(storage)
    limit=LIMIT

    def image(self,capture):
        """Read bounded original bytes; each one-send command requires intent.

        Chunk responses are transport, not fresh frame observations. Publication
        must still bind the original frame/image clocks and source-owned PNG SHA.
        """
        try:
            started=previous=self.monotonic();need(number(started,0,1e15))
            def bound():
                nonlocal previous
                current=self.monotonic();need(number(current,previous,1e15) and current-started<1.5
                                               and self.guard() is not False);previous=current
            request=dict(schemaVersion=1,action='feature-vulkan-world-frame',operation='read',
                         commandId=capture['commandId'],requestId=capture['requestId'])
            validate(capture,request,self.pid,self.clock_ms())
            need(self.instance==capture['instance'] and self.sequence>=capture['sequence'])
            total=capture['source']['image']['bytes'];raw=bytearray()
            while len(raw)<total:
                bound()
                query=dict(schemaVersion=1,action='feature-vulkan-world-frame',operation='read-bytes',
                           commandId='ios-'+uuid.uuid4().hex,requestId=capture['requestId'],offset=len(raw))
                result=self.perform(query);source=result['source']
                need(source['pngBytes']==total and result['instance']==capture['instance'])
                raw.extend(base64.b64decode(source['data'],validate=True))
                bound()
            value=original_pixels(capture,bytes(raw));fresh(capture['capturedEpochMs'],self.clock_ms())
            bound()
            return value
        except Exception:
            raise NativeUIError('Original Vulkan world image is unavailable; command and file responsibility is retained') from None
