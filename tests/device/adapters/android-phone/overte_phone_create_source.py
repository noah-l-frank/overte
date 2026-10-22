"""Original Phone Create entity/permission reads; no expected-state inputs.

This internal source does not advertise the complete Create journey. Product
inputs, controlled-domain authority, original pixels and file ownership remain
separate. A missing/partial native source is an error, never an empty inventory.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import re
import time
import uuid

from adapters.native_feature_observation import decode, exact, fresh, integer, need, number
from adapters.native_graphics_subject import entity_id, vector, rotation
from adapters.normal_ui import NativeUIError

FILE='phone-create-observation.json'
VERSION=2
LIMIT=262144


def nonce(value):return type(value) is str and re.fullmatch('[0-9a-f]{32}',value) is not None and value!='0'*32

def text(value,limit):return type(value) is str and len(value)<=limit and all(ord(ch)>=32 and ord(ch)!=127 for ch in value)

def digest(value):return type(value) is str and re.fullmatch('[0-9a-f]{64}',value) is not None


def render_source(value):
    exact(value,{'modelInstance','loaded','visible','addedToScene','geometry'})
    need(nonce(value['modelInstance']) and all(type(value[key]) is bool for key in ('loaded','visible','addedToScene')))
    geometry=value['geometry'];need(value['loaded']==(geometry is not None))
    if geometry is None:return value
    exact(geometry,{'instance','sourcePresent','sourceSha256','textures'})
    need(nonce(geometry['instance']) and type(geometry['sourcePresent']) is bool and digest(geometry['sourceSha256'])
        and type(geometry['textures']) is list and len(geometry['textures'])<=256)
    seen=set()
    for row in geometry['textures']:
        exact(row,{'material','channel','name','urlSha256','loaded','failed','originalSha256','originalBytes','gpuWidth','gpuHeight'})
        need(integer(row['material'],0,65535) and integer(row['channel'],0,255) and text(row['name'],256)
            and digest(row['urlSha256']) and all(type(row[key]) is bool for key in ('loaded','failed'))
            and (row['originalSha256']=='' or digest(row['originalSha256'])) and integer(row['originalBytes'],0,32*1024*1024)
            and (row['originalSha256']=='')==(row['originalBytes']==0)
            and all(integer(row[key],0,16384) for key in ('gpuWidth','gpuHeight'))
            and (row['material'],row['channel']) not in seen)
        seen.add((row['material'],row['channel']))
    return value


def command(value):
    exact(value,{'schemaVersion','commandId','action','runId','trackedIds'})
    need(type(value['schemaVersion']) is int and value['schemaVersion']==1
         and value['action']=='phone-create-observe' and nonce(value['commandId']) and nonce(value['runId'])
         and type(value['trackedIds']) is list and len(value['trackedIds'])<=32
         and all(entity_id(item) and item!='00000000-0000-0000-0000-000000000000' for item in value['trackedIds'])
         and value['trackedIds']==sorted(set(value['trackedIds'])))
    return value


def validate(value,request,pid,epoch):
    command(request)
    exact(value,{'schemaVersion','requestId','runId','instance','sequence','processId','requestedEpochMs','capturedEpochMs','source'})
    need(type(value['schemaVersion']) is int and value['schemaVersion']==1 and value['requestId']==request['commandId']
         and value['runId']==request['runId'] and nonce(value['instance']) and integer(value['sequence'],1,1_000_000_000)
         and integer(value['processId'],1) and value['processId']==pid and integer(value['requestedEpochMs'],1)
         and integer(value['capturedEpochMs'],1) and 0<=value['capturedEpochMs']-value['requestedEpochMs']<1500)
    fresh(value['capturedEpochMs'],epoch)
    source=value['source']
    exact(source,{'phoneCreateObservationVersion','connected','domainId','sessionId','canRez','canRezTmp','canRezAvatarEntities',
                  'scan','entities','absentIds'})
    need(type(source['phoneCreateObservationVersion']) is int and source['phoneCreateObservationVersion']==VERSION
         and all(type(source[key]) is bool for key in ('connected','canRez','canRezTmp','canRezAvatarEntities'))
         and (source['domainId'] is None or entity_id(source['domainId']))
         and (source['sessionId'] is None or entity_id(source['sessionId']))
         and (source['connected'] is False or source['domainId'] is not None))
    scan=source['scan'];exact(scan,{'center','radiusMeters','scannedEntities','complete','inventory'})
    vector(scan['center'],3,-1000000,1000000)
    need(type(scan['radiusMeters']) is int and scan['radiusMeters']==128 and integer(scan['scannedEntities'],0,1024)
         and scan['complete'] is True and type(scan['complete']) is bool
         and type(scan['inventory']) is list and len(scan['inventory'])==scan['scannedEntities'])
    inventory=set()
    for row in scan['inventory']:
        exact(row,{'id','instance','type','host','nameSha256'})
        need(entity_id(row['id']) and nonce(row['instance']) and row['id'] not in inventory and text(row['type'],64) and row['type']!='Unknown'
             and row['host'] in ('local','avatar','domain') and digest(row['nameSha256']))
        inventory.add(row['id'])
    need(type(source['entities']) is list and len(source['entities'])<=32
         and type(source['absentIds']) is list and len(source['absentIds'])<=32)
    seen=set();tracked=set(request['trackedIds']);prefix='e2e-'+request['runId']+'-'
    for row in source['entities']:
        exact(row,{'id','instance','name','createdEpochUs','lastEditedBy','type','host','parentId','position','rotation','dimensions','visible','locked',
                   'modelUrl','textures','voxel','render'})
        need(entity_id(row['id']) and nonce(row['instance']) and row['id'] not in seen and text(row['name'],256)
             and integer(row['createdEpochUs'],1,9007199254740991)
             and (row['lastEditedBy'] is None or entity_id(row['lastEditedBy']))
             and (row['id'] in tracked or row['name'] in {prefix+kind for kind in ('model','voxel','cube')})
             and text(row['type'],64) and row['type']!='Unknown' and row['host'] in ('local','avatar','domain')
             and (row['parentId'] is None or entity_id(row['parentId']))
             and all(type(row[key]) is bool for key in ('visible','locked'))
             and text(row['modelUrl'],2048) and text(row['textures'],16384))
        vector(row['position'],3,-1000000,1000000);rotation(row['rotation']);vector(row['dimensions'],3,0,1000000)
        need(min(row['dimensions'])>0)
        voxel=row['voxel']
        if row['type']=='PolyVox':
            exact(voxel,{'savedSha256','savedBytes','ready','volumeSize','cells'})
            need(digest(voxel['savedSha256']) and integer(voxel['savedBytes'],0,16*1024*1024) and type(voxel['ready']) is bool)
            vector(voxel['volumeSize'],3,1,128)
            if voxel['cells'] is not None:
                exact(voxel['cells'],{'sha256','occupied'})
                need(voxel['ready'] and voxel['volumeSize']==[8,8,8] and digest(voxel['cells']['sha256'])
                    and integer(voxel['cells']['occupied'],0,512))
        else:need(voxel is None)
        if row['render'] is not None:
            need(row['type']=='Model');render_source(row['render'])
        listed=[item for item in scan['inventory'] if item['id']==row['id']]
        if listed:need(listed[0]['instance']==row['instance'])
        seen.add(row['id'])
    absent=source['absentIds']
    need(all(entity_id(item) and item in tracked and item not in seen for item in absent)
         and absent==sorted(set(absent)) and tracked<=seen|set(absent))
    return value


class PhoneCreateSource:
    def __init__(self,send,read,clock_ms,guard,pid,*,monotonic=time.monotonic,sleep=time.sleep):
        need(all(callable(fn) for fn in (send,read,clock_ms,guard,monotonic,sleep)) and integer(pid,1))
        self.send,self.original,self.clock_ms,self.guard,self.pid=send,read,clock_ms,guard,pid
        self.monotonic,self.sleep,self.last=monotonic,sleep,None

    def read(self,run,tracked_ids=()):
        try:
            request=command(dict(schemaVersion=1,commandId=uuid.uuid4().hex,action='phone-create-observe',
                                 runId=run,trackedIds=list(tracked_ids)))
            need(self.guard() is not False)
            started=previous=self.monotonic();need(number(started,0,1e15))
            requested=self.clock_ms();need(integer(requested,1));self.send(request)
            for attempt in range(51):
                need(self.guard() is not False)
                raw=self.original();need(type(raw) is str and len(raw.encode())<=LIMIT)
                try:value=decode(raw) if raw else None
                except json.JSONDecodeError:value=None
                need(self.guard() is not False)
                current=self.monotonic();need(number(current,previous,1e15) and current-started<5);previous=current
                if type(value) is dict and value.get('requestId')==request['commandId']:
                    epoch=self.clock_ms();need(integer(epoch,requested))
                    validate(value,request,self.pid,epoch);need(value['requestedEpochMs']>=requested)
                    if self.last is not None:
                        need(value['runId']==self.last['runId'] and value['instance']==self.last['instance']
                             and value['sequence']>self.last['sequence'] and value['capturedEpochMs']>=self.last['capturedEpochMs'])
                    need(self.guard() is not False)
                    epoch=self.clock_ms();fresh(value['capturedEpochMs'],epoch)
                    current=self.monotonic();need(number(current,previous,1e15) and current-started<5)
                    self.last=deepcopy(value);return deepcopy(value)
                if attempt<50:self.sleep(.1)
        except Exception:
            raise NativeUIError('Original Phone Create observation is unavailable or invalid') from None
        raise NativeUIError('Original Phone Create observation did not produce this request')
