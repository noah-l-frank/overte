"""Original completed AssetClient mapping/bake and content reads; no verdicts."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import base64
import hashlib
import json
import re
import time
import uuid

from adapters.native_feature_observation import decode,exact,fresh,integer,need,number
from adapters.native_graphics_subject import entity_id
from adapters.normal_ui import NativeUIError
from adapters.native_avatar_render import nonce as _nonce
from adapters.world_render_evidence import digest
import math

def nonce(value):return _nonce(value) and value!='0'*32
def text(value,limit):return type(value) is str and len(value)<=limit and all(ord(ch)>=32 and ord(ch)!=127 for ch in value)

FILE='feature-pico-assets-observation.json'
DOWNLOAD_FILE='feature-pico-assets-download.json'
RESOLVE_FILE='feature-pico-assets-resolve.json'
LIMIT=4*1024*1024
SCOPE={'domainSession','clientInstance','nodeListInstance','assetServerInstance'}


def effective_epoch(clock_ms,requested,started,current):
    native=clock_ms();need(integer(native,requested))
    return max(native,requested+math.ceil((current-started)*1000))


def command(value):
    download=value.get('action')=='feature-pico-assets-download' if type(value) is dict else False
    resolve=value.get('action')=='feature-pico-assets-resolve' if type(value) is dict else False
    exact(value,{'schemaVersion','commandId','action','runId'}|({'hash'} if download else set())|({'path'} if resolve else set()))
    need(type(value['schemaVersion']) is int and value['schemaVersion']==1 and nonce(value['commandId']) and nonce(value['runId'])
        and value['action'] in ('feature-pico-assets-observe','feature-pico-assets-download','feature-pico-assets-resolve') and (not download or digest(value['hash'])))
    if resolve:
        need(type(value['path']) is str and re.fullmatch(r'/(?:e2e-|renamed-)'+value['runId']+r'/(?:main\.gltf|main\.obj|stand\.fbx|mesh/triangle\.bin|textures/checker\.png|materials/palette\.mtl)',value['path']))
    return value


def mapping_path(value):
    need(text(value,1024) and len(value)>1 and value.startswith('/') and not value.endswith('/') and '\\' not in value
        and all(part not in ('','.','..') for part in value[1:].split('/')))
    return value


def mappings(value):
    exact(value,{'picoAssetsObservationVersion','domainId','sessionId','assetServerId','canWrite','complete','mappings'}|SCOPE)
    need(type(value['picoAssetsObservationVersion']) is int and value['picoAssetsObservationVersion']==1 and value['complete'] is True
        and entity_id(value['domainId']) and entity_id(value['sessionId']) and entity_id(value['assetServerId']) and type(value['canWrite']) is bool
        and type(value['mappings']) is list and len(value['mappings'])<=4096)
    previous=None
    for row in value['mappings']:
        exact(row,{'path','hash','bakeStatus','bakeError'});mapping_path(row['path'])
        ordering=row['path'].encode('utf-16-be')
        need((previous is None or ordering>previous) and digest(row['hash']) and integer(row['bakeStatus'],0,5) and type(row['bakeError']) is str and len(row['bakeError'].encode('utf-16-be'))<=8192)
        previous=ordering
    return value


def download(value,request):
    exact(value,{'picoAssetsDownloadVersion','domainId','sessionId','assetServerId','hash','bytes','base64','loadedFromCache'}|SCOPE)
    need(type(value['picoAssetsDownloadVersion']) is int and value['picoAssetsDownloadVersion']==1
        and all(entity_id(value[key]) for key in ('domainId','sessionId','assetServerId')) and value['hash']==request['hash']
        and integer(value['bytes'],1,1024*1024) and type(value['base64']) is str and type(value['loadedFromCache']) is bool)
    data=base64.b64decode(value['base64'],validate=True)
    need(len(data)==value['bytes'] and base64.b64encode(data).decode()==value['base64'] and hashlib.sha256(data).hexdigest()==value['hash'])
    return value


def resolve(value,request):
    exact(value,{'picoAssetsResolveVersion','domainId','sessionId','assetServerId','requestedPath','hash','redirected','redirectedPath'}|SCOPE)
    need(type(value['picoAssetsResolveVersion']) is int and value['picoAssetsResolveVersion']==1
        and all(entity_id(value[key]) for key in ('domainId','sessionId','assetServerId'))
        and value['requestedPath']==request['path'] and digest(value['hash']) and type(value['redirected']) is bool)
    mapping_path(value['requestedPath'])
    if value['redirected']:mapping_path(value['redirectedPath'])
    else:need(value['redirectedPath']=='')
    return value


def connection(value,run,captured):
    need(all(nonce(value[key]) for key in ('clientInstance','nodeListInstance','assetServerInstance')))
    session=value['domainSession'];exact(session,{'domainSessionVersion','instance','revision','connected','domainSha256','connectionBirth','connectedEpochMs'})
    need(type(session['domainSessionVersion']) is int and session['domainSessionVersion']==1 and nonce(session['instance'])
        and integer(session['revision'],1,9007199254740991) and session['connected'] is True and nonce(session['connectionBirth'])
        and integer(session['connectedEpochMs'],1,captured)
        and session['domainSha256']==hashlib.sha256((run+':').encode()+uuid.UUID(value['domainId']).bytes).hexdigest())


def validate(value,request,pid,epoch):
    command(request)
    exact(value,{'schemaVersion','requestId','runId','instance','sequence','processId','requestedEpochMs','capturedEpochMs','source','activeRequests','retainedResults'})
    need(type(value['schemaVersion']) is int and value['schemaVersion']==1 and value['requestId']==request['commandId'] and value['runId']==request['runId']
        and nonce(value['instance']) and integer(value['sequence'],1,512) and integer(value['processId'],1) and value['processId']==pid
        and integer(value['requestedEpochMs'],1) and integer(value['capturedEpochMs'],value['requestedEpochMs'])
        and value['capturedEpochMs']-value['requestedEpochMs']<1500
        and type(value['activeRequests']) is int and value['activeRequests']==0 and type(value['retainedResults']) is int and value['retainedResults']==0)
    fresh(value['capturedEpochMs'],epoch)
    if request['action']=='feature-pico-assets-download':download(value['source'],request)
    elif request['action']=='feature-pico-assets-resolve':resolve(value['source'],request)
    else:mappings(value['source'])
    connection(value['source'],request['runId'],value['capturedEpochMs'])
    return value


class PicoAssetsSource:
    def __init__(self,send,read,clock_ms,guard,pid,*,download=False,resolve=False,monotonic=time.monotonic,sleep=time.sleep,intent=None):
        need(all(callable(fn) for fn in (send,read,clock_ms,guard,monotonic,sleep)) and integer(pid,1) and type(download) is bool and type(resolve) is bool and not(download and resolve))
        self.send,self.original,self.clock_ms,self.guard,self.pid=send,read,clock_ms,guard,pid
        self.is_download,self.is_resolve,self.monotonic,self.sleep,self.last=download,resolve,monotonic,sleep,None
        need(intent is None or callable(intent));self.intent=intent;self.pending=None;self.last_raw=self.last_sha256=None;self.history=[]

    def read(self,run,hash=None,*,path=None):
        try:
            request=dict(schemaVersion=1,commandId=uuid.uuid4().hex,action='feature-pico-assets-download' if self.is_download else 'feature-pico-assets-resolve' if self.is_resolve else 'feature-pico-assets-observe',runId=run)
            if self.is_download:request['hash']=hash
            else:need(hash is None)
            if self.is_resolve:request['path']=path
            else:need(path is None)
            command(request);need(len(self.history)<128 and self.pending is None and self.guard() is not False)
            started=previous=self.monotonic();need(number(started,0,1e15))
            requested=self.clock_ms();need(integer(requested,1))
            if self.intent is not None:need(self.intent(deepcopy(request)) is not False)
            self.pending=deepcopy(request);self.send(request)
            for attempt in range(51):
                need(self.guard() is not False);raw=self.original();need(type(raw) is str and len(raw.encode())<=LIMIT)
                try:value=decode(raw) if raw else None
                except json.JSONDecodeError:value=None
                need(self.guard() is not False);current=self.monotonic();need(number(current,previous,1e15) and current-started<5);previous=current
                if type(value) is dict and value.get('requestId')==request['commandId']:
                    epoch=effective_epoch(self.clock_ms,requested,started,current);need(integer(epoch,requested));validate(value,request,self.pid,epoch);need(value['requestedEpochMs']>=requested)
                    if self.last is not None:
                        need(value['runId']==self.last['runId'] and value['instance']==self.last['instance'] and value['sequence']>self.last['sequence']
                            and value['capturedEpochMs']>=self.last['capturedEpochMs']
                            and all(value['source'][key]==self.last['source'][key] for key in ('domainId','sessionId','assetServerId','domainSession','clientInstance','nodeListInstance','assetServerInstance')))
                    need(self.guard() is not False);fresh(value['capturedEpochMs'],self.clock_ms())
                    current=self.monotonic();need(number(current,previous,1e15) and current-started<5)
                    fresh(value['capturedEpochMs'],effective_epoch(self.clock_ms,requested,started,current))
                    self.last=deepcopy(value);self.last_raw=raw;self.last_sha256=hashlib.sha256(raw.encode()).hexdigest()
                    self.history.append(dict(command=deepcopy(request),raw=raw,sha256=self.last_sha256));self.pending=None;return deepcopy(value)
                if attempt<50:self.sleep(.1)
        except Exception:raise NativeUIError('Original Pico Assets read is unavailable or invalid') from None
        raise NativeUIError('Original Pico Assets read did not produce this request')

    def restore(self,history,pending=None):
        """Historical originals preserve continuity and never become fresh samples."""
        need(type(history) is list and len(history)<=128 and self.last is None and not self.history and self.pending is None)
        previous=None;seen=set()
        action='feature-pico-assets-download' if self.is_download else 'feature-pico-assets-resolve' if self.is_resolve else 'feature-pico-assets-observe'
        for original in history:
            exact(original,{'command','raw','sha256'});request=command(original['command']);need(request['action']==action)
            need(type(original['raw']) is str and len(original['raw'].encode())<=LIMIT and digest(original['sha256'])
                and hashlib.sha256(original['raw'].encode()).hexdigest()==original['sha256'])
            value=decode(original['raw']);validate(value,request,self.pid,value['capturedEpochMs'])
            need(request['commandId'] not in seen);seen.add(request['commandId'])
            if previous is not None:
                need(value['instance']==previous['instance'] and value['runId']==previous['runId'] and value['sequence']>previous['sequence']
                    and value['capturedEpochMs']>=previous['capturedEpochMs']
                    and all(value['source'][key]==previous['source'][key] for key in ('domainId','sessionId','assetServerId','domainSession','clientInstance','nodeListInstance','assetServerInstance')))
            previous=value
        if pending is not None:
            command(pending);need(pending['action']==action and pending['commandId'] not in seen
                and (previous is None or pending['runId']==previous['runId']))
        self.history=deepcopy(history);self.pending=deepcopy(pending)
        if previous is not None:self.last=deepcopy(previous);self.last_raw=history[-1]['raw'];self.last_sha256=history[-1]['sha256']
