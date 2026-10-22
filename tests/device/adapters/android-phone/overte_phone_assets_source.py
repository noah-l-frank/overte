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
from overte_phone_create_source import nonce,digest,text

FILE='phone-assets-observation.json'
DOWNLOAD_FILE='phone-assets-download.json'
RESOLVE_FILE='phone-assets-resolve.json'
LIMIT=4*1024*1024


def command(value):
    download=value.get('action')=='phone-assets-download' if type(value) is dict else False
    resolve=value.get('action')=='phone-assets-resolve' if type(value) is dict else False
    exact(value,{'schemaVersion','commandId','action','runId'}|({'hash'} if download else set())|({'path'} if resolve else set()))
    need(type(value['schemaVersion']) is int and value['schemaVersion']==1 and nonce(value['commandId']) and nonce(value['runId'])
        and value['action'] in ('phone-assets-observe','phone-assets-download','phone-assets-resolve') and (not download or digest(value['hash'])))
    if resolve:
        need(type(value['path']) is str and re.fullmatch(r'/(?:e2e-|renamed-)'+value['runId']+r'/(?:main\.gltf|main\.obj|stand\.fbx|mesh/triangle\.bin|textures/checker\.png|materials/palette\.mtl)',value['path']))
    return value


def mapping_path(value):
    need(text(value,1024) and len(value)>1 and value.startswith('/') and not value.endswith('/') and '\\' not in value
        and all(part not in ('','.','..') for part in value[1:].split('/')))
    return value


def mappings(value):
    exact(value,{'phoneAssetsObservationVersion','domainId','sessionId','assetServerId','canWrite','complete','mappings'})
    need(type(value['phoneAssetsObservationVersion']) is int and value['phoneAssetsObservationVersion']==2 and value['complete'] is True
        and entity_id(value['domainId']) and entity_id(value['sessionId']) and entity_id(value['assetServerId']) and type(value['canWrite']) is bool
        and type(value['mappings']) is list and len(value['mappings'])<=4096)
    previous=None
    for row in value['mappings']:
        exact(row,{'path','hash','bakeStatus','bakeError'});mapping_path(row['path'])
        ordering=row['path'].encode('utf-16-be')
        need((previous is None or ordering>previous) and digest(row['hash']) and integer(row['bakeStatus'],0,5) and text(row['bakeError'],4096))
        previous=ordering
    return value


def download(value,request):
    exact(value,{'phoneAssetsDownloadVersion','domainId','sessionId','assetServerId','hash','bytes','base64','loadedFromCache'})
    need(type(value['phoneAssetsDownloadVersion']) is int and value['phoneAssetsDownloadVersion']==2
        and all(entity_id(value[key]) for key in ('domainId','sessionId','assetServerId')) and value['hash']==request['hash']
        and integer(value['bytes'],1,1024*1024) and type(value['base64']) is str and type(value['loadedFromCache']) is bool)
    data=base64.b64decode(value['base64'],validate=True)
    need(len(data)==value['bytes'] and base64.b64encode(data).decode()==value['base64'] and hashlib.sha256(data).hexdigest()==value['hash'])
    return value


def resolve(value,request):
    exact(value,{'phoneAssetsResolveVersion','domainId','sessionId','assetServerId','requestedPath','hash','redirected','redirectedPath'})
    need(type(value['phoneAssetsResolveVersion']) is int and value['phoneAssetsResolveVersion']==1
        and all(entity_id(value[key]) for key in ('domainId','sessionId','assetServerId'))
        and value['requestedPath']==request['path'] and digest(value['hash']) and type(value['redirected']) is bool)
    mapping_path(value['requestedPath'])
    if value['redirected']:mapping_path(value['redirectedPath'])
    else:need(value['redirectedPath']=='')
    return value


def validate(value,request,pid,epoch):
    command(request)
    exact(value,{'schemaVersion','requestId','runId','instance','sequence','processId','requestedEpochMs','capturedEpochMs','source','activeRequests','retainedResults'})
    need(type(value['schemaVersion']) is int and value['schemaVersion']==1 and value['requestId']==request['commandId'] and value['runId']==request['runId']
        and nonce(value['instance']) and integer(value['sequence'],1,1_000_000_000) and integer(value['processId'],1) and value['processId']==pid
        and integer(value['requestedEpochMs'],1) and integer(value['capturedEpochMs'],value['requestedEpochMs'])
        and value['capturedEpochMs']-value['requestedEpochMs']<1500
        and type(value['activeRequests']) is int and value['activeRequests']==0 and type(value['retainedResults']) is int and value['retainedResults']==0)
    fresh(value['capturedEpochMs'],epoch)
    if request['action']=='phone-assets-download':download(value['source'],request)
    elif request['action']=='phone-assets-resolve':resolve(value['source'],request)
    else:mappings(value['source'])
    return value


class PhoneAssetsSource:
    def __init__(self,send,read,clock_ms,guard,pid,*,download=False,resolve=False,monotonic=time.monotonic,sleep=time.sleep):
        need(all(callable(fn) for fn in (send,read,clock_ms,guard,monotonic,sleep)) and integer(pid,1) and type(download) is bool and type(resolve) is bool and not(download and resolve))
        self.send,self.original,self.clock_ms,self.guard,self.pid=send,read,clock_ms,guard,pid
        self.is_download,self.is_resolve,self.monotonic,self.sleep,self.last=download,resolve,monotonic,sleep,None

    def read(self,run,hash=None,*,path=None):
        try:
            request=dict(schemaVersion=1,commandId=uuid.uuid4().hex,action='phone-assets-download' if self.is_download else 'phone-assets-resolve' if self.is_resolve else 'phone-assets-observe',runId=run)
            if self.is_download:request['hash']=hash
            else:need(hash is None)
            if self.is_resolve:request['path']=path
            else:need(path is None)
            command(request);need(self.guard() is not False)
            started=previous=self.monotonic();need(number(started,0,1e15))
            requested=self.clock_ms();need(integer(requested,1));self.send(request)
            for attempt in range(51):
                need(self.guard() is not False);raw=self.original();need(type(raw) is str and len(raw.encode())<=LIMIT)
                try:value=decode(raw) if raw else None
                except json.JSONDecodeError:value=None
                need(self.guard() is not False);current=self.monotonic();need(number(current,previous,1e15) and current-started<5);previous=current
                if type(value) is dict and value.get('requestId')==request['commandId']:
                    epoch=self.clock_ms();need(integer(epoch,requested));validate(value,request,self.pid,epoch);need(value['requestedEpochMs']>=requested)
                    if self.last is not None:
                        need(value['runId']==self.last['runId'] and value['instance']==self.last['instance'] and value['sequence']>self.last['sequence']
                            and value['capturedEpochMs']>=self.last['capturedEpochMs']
                            and all(value['source'][key]==self.last['source'][key] for key in ('domainId','sessionId','assetServerId')))
                    need(self.guard() is not False);fresh(value['capturedEpochMs'],self.clock_ms())
                    current=self.monotonic();need(number(current,previous,1e15) and current-started<5)
                    self.last=deepcopy(value);return deepcopy(value)
                if attempt<50:self.sleep(.1)
        except Exception:raise NativeUIError('Original Phone Assets read is unavailable or invalid') from None
        raise NativeUIError('Original Phone Assets read did not produce this request')
