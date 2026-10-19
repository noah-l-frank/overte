"""Original native PNG memory transport and separately observed release.

No capture, UI screenshot, file fallback, paint, resampling or feature verdict.
Acquisition ownership must already have been persisted before the GPU request.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import hashlib
import json
import re
import time
import uuid
from adapters.native_feature_observation import decode,exact,fresh,integer,need,number
from adapters.normal_ui import NativeUIError
from adapters.world_render_evidence import LIMIT,image_name


def command(value,*,ios=False):
    need(type(value) is dict)
    keys={'schemaVersion','commandId','action','requestId','operation'}
    if value.get('operation')=='read':keys.add('offset')
    exact(value,keys)
    need(type(value['schemaVersion']) is int and value['schemaVersion']==1
         and value['action']=='feature-world-render-storage' and value['operation'] in ('read','release','inspect'))
    for key in ('commandId','requestId'):
        need(type(value[key]) is str and re.fullmatch(('ios-' if ios else '(?:ios-)?')+'[0-9a-f]{32}',value[key]))
    if value['operation']=='read':need(integer(value['offset'],0,LIMIT-1))
    return value


def receipt_file(nonce):
    image_name(nonce) # Same closed, normalized nonce grammar; no arbitrary paths.
    return 'world-render-storage-'+nonce.removeprefix('ios-')+'.json'


class NativeWorldRenderStorage:
    def __init__(self,send,read_file,clock_ms,guard,pid,*,receipt_intent,ios=False,monotonic=time.monotonic,sleep=time.sleep):
        need(all(callable(v) for v in (send,read_file,clock_ms,guard,receipt_intent,monotonic,sleep)) and integer(pid,1) and type(ios) is bool)
        self.send,self.original,self.clock_ms,self.guard,self.pid=send,read_file,clock_ms,guard,pid
        self.ios,self.monotonic,self.sleep=ios,monotonic,sleep
        self.receipt_intent=receipt_intent
        self.instance,self.sequence,self.capture=None,0,None

    def bind(self,value):
        need(type(value) is dict and value.get('processId')==self.pid and type(value.get('instance')) is str
             and re.fullmatch('[0-9a-f]{32}',value['instance']) and self.instance in (None,value['instance']))
        image=value['source']['image'];need(image['name']==image_name(value['requestId']) and integer(image['bytes'],1,LIMIT))
        self.instance=value['instance'];self.capture=deepcopy(value)

    def request(self,operation,request,offset=None):
        try:
            value=dict(schemaVersion=1,commandId=('ios-' if self.ios else '')+uuid.uuid4().hex,
                action='feature-world-render-storage',requestId=request,operation=operation)
            if offset is not None:value['offset']=offset
            command(value,ios=self.ios)
            started=previous=self.monotonic();need(number(started,0,1e15))
            requested=self.clock_ms();need(integer(requested,1) and self.guard() is not False)
            self.receipt_intent(deepcopy(value)) # This command creates a private original receipt file.
            now=self.monotonic();need(number(now,0,1e15) and now>=previous and now-started<(1.5 if self.ios else 5))
            previous=now;need(self.guard() is not False)
            self.send(value) # A release is sent once; uncertain mutations never replay.
            for attempt in range(51):
                need(self.guard() is not False)
                raw=self.original(receipt_file(value['commandId']))
                need(type(raw) in (str,bytes) and len(raw.encode() if type(raw) is str else raw)<=100000)
                try:sample=decode(raw) if raw else None
                except json.JSONDecodeError:sample=None
                need(self.guard() is not False)
                now=self.monotonic();need(number(now,0,1e15) and now>=previous and now-started<(1.5 if self.ios else 5))
                previous=now
                if type(sample) is dict and sample.get('commandId')==value['commandId']:
                    fields={'storageVersion','commandId','requestId','instance','sequence','processId','capturedEpochMs','present','callbacks','pngBytes'}
                    if operation=='read':fields.update(('offset','data'))
                    exact(sample,fields)
                    need(type(sample['storageVersion']) is int and sample['storageVersion']==1 and sample['requestId']==request
                         and type(sample['instance']) is str and re.fullmatch('[0-9a-f]{32}',sample['instance'])
                         and self.instance in (None,sample['instance']) and integer(sample['sequence'],self.sequence+1)
                         and integer(sample['processId'],1) and sample['processId']==self.pid
                         and integer(sample['capturedEpochMs'],1) and (self.ios or sample['capturedEpochMs']>=requested)
                         and type(sample['present']) is bool and integer(sample['callbacks'],0,1) and integer(sample['pngBytes'],0,LIMIT))
                    fresh(sample['capturedEpochMs'],sample['capturedEpochMs'] if self.ios else self.clock_ms())
                    if not sample['present']:need(sample['pngBytes']==0)
                    if operation=='read':
                        need(sample['present'] and sample['offset']==offset and type(sample['offset']) is int
                             and type(sample['data']) is str and 0<len(sample['data'])<=87384)
                        chunk=base64.b64decode(sample['data'],validate=True)
                        need(base64.b64encode(chunk).decode()==sample['data'] and 0<len(chunk)<=65536
                             and offset+len(chunk)<=sample['pngBytes'])
                    self.instance,self.sequence=sample['instance'],sample['sequence']
                    return sample
                if attempt<50:self.sleep(.03)
        except Exception:
            raise NativeUIError('Native world image storage is unavailable or invalid') from None
        raise NativeUIError('Native world image storage did not produce this request')

    def read(self,name):
        need(self.capture is not None and name==self.capture['source']['image']['name'])
        image=self.capture['source']['image'];chunks=[];offset=0
        started=previous=self.monotonic();need(number(started,0,1e15))
        while offset<image['bytes']:
            sample=self.request('read',self.capture['requestId'],offset)
            need(sample['pngBytes']==image['bytes'])
            chunk=base64.b64decode(sample['data'],validate=True)
            need(len(chunk)==min(65536,image['bytes']-offset))
            chunks.append(chunk);offset+=len(chunk)
            now=self.monotonic();need(number(now,0,1e15) and now>=previous and now-started<(1.5 if self.ios else 5));previous=now
        raw=b''.join(chunks)
        need(hashlib.sha256(raw).hexdigest()==image['sha256'] and self.guard() is not False)
        return raw

    def release(self,request):
        self.request('release',request)
        # A release receipt, empty file list or cancelled request does not prove
        # that queued/executing GPU callbacks have drained their local buffers.
        started=previous=self.monotonic();need(number(started,0,1e15))
        for attempt in range(51):
            sample=self.request('inspect',request)
            now=self.monotonic();need(number(now,0,1e15) and now>=previous and now-started<(1.5 if self.ios else 5));previous=now
            if not sample['present'] and sample['callbacks']==0 and sample['pngBytes']==0:
                if self.capture is not None and self.capture['requestId']==request:self.capture=None
                return sample
            if attempt<50:self.sleep(.03)
        raise NativeUIError('Native world image buffers or callbacks remain owned')
