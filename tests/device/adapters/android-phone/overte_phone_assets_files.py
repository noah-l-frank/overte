"""Original fixed private input bundles with native inode and byte ownership."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import json
import re
import time
import uuid
from urllib.parse import unquote,urlsplit
from adapters.native_feature_observation import decode,exact,fresh,integer,need,number
from adapters.normal_ui import NativeUIError
from adapters.token_script_file_ui import file_url
from overte_phone_create_source import nonce,digest
from overte_phone_assets_fixture import NAMES,DIRECTORIES

FILE='phone-assets-files.json'


def command(value):
    fields={'schemaVersion','commandId','action','operation','runId','ownerToken'}
    if type(value) is dict and 'stage' in value:fields|={'stage'};need(integer(value['stage'],1,6))
    if type(value) is dict and value.get('operation')=='stage':fields|={'files'}
    exact(value,fields)
    need(type(value['schemaVersion']) is int and value['schemaVersion']==1 and value['action']=='phone-assets-files'
        and nonce(value['commandId']) and nonce(value['runId']) and digest(value['ownerToken'])
        and value['operation'] in ('stage','observe','retire-primary','release'))
    if value['operation']=='stage':
        need(type(value['files']) is dict and set(value['files'])==set(NAMES))
        total=0
        for encoded in value['files'].values():
            need(type(encoded) is str and len(encoded)<=65536);raw=base64.b64decode(encoded,validate=True)
            need(0<len(raw)<=32768 and base64.b64encode(raw).decode()==encoded);total+=len(raw)
        need(total<=131072)
    return value


def identity(value):
    exact(value,{'device','inode','size','modifiedNs','changedNs'})
    need(all(type(v) is str and re.fullmatch('[0-9]{1,22}',v) for v in value.values()) and int(value['inode'])>0)
    return value


def source(value,run,stage=None):
    need(stage is None or integer(stage,1,6))
    exact(value,{'assetsFilesVersion','exists','retiring','retired','directory','rootIdentity','directories','files','primaryRetired'})
    need(type(value['assetsFilesVersion']) is int and value['assetsFilesVersion']==1
        and all(type(value[key]) is bool for key in ('exists','retiring','retired','primaryRetired'))
        and type(value['directories']) is list and type(value['files']) is list)
    file_url(value['directory']);url=urlsplit(value['directory']);path=unquote(url.path)
    need(not url.query and not url.fragment and path.endswith('/feature-assets-'+run+('' if stage is None else '-stage'+str(stage))) and not path.endswith('//feature-assets-'+run))
    if not value['exists']:
        need(value['rootIdentity'] is None and not value['directories'] and not value['files'] and (not value['retired'] or value['retiring']))
        return value
    need(not value['retired']);identity(value['rootIdentity'])
    dirs=set()
    for row in value['directories']:
        exact(row,{'name','identity'});need(row['name'] in DIRECTORIES and row['name'] not in dirs);identity(row['identity']);dirs.add(row['name'])
    need(value['retiring'] or dirs==set(DIRECTORIES))
    need([row.get('name') for row in value['files']]==list(NAMES))
    for row in value['files']:
        exact(row,{'name','exists','identity','bytes','sha256'});need(type(row['exists']) is bool)
        if not row['exists']:
            need((value['retiring'] or value['primaryRetired'] and row['name']=='gltf-bundle/main.gltf') and row['identity'] is None
                and type(row['bytes']) is int and row['bytes']==0 and row['sha256']=='')
        else:
            identity(row['identity']);need(integer(row['bytes'],1,32768) and digest(row['sha256'])
                and row['bytes']==int(row['identity']['size']) and row['name'].rsplit('/',1)[0] in dirs)
    main=next(row for row in value['files'] if row['name']=='gltf-bundle/main.gltf')
    need(not value['primaryRetired'] or not main['exists'])
    return value


class PhoneAssetsFiles:
    def __init__(self,send,read,clock_ms,guard,pid,*,monotonic=time.monotonic,sleep=time.sleep,stage=None):
        need(all(callable(v) for v in (send,read,clock_ms,guard,monotonic,sleep)) and integer(pid,1))
        need(stage is None or integer(stage,1,6));self.stage=stage
        self.send,self.original,self.clock_ms,self.guard,self.pid=send,read,clock_ms,guard,pid
        self.monotonic,self.sleep,self.last=monotonic,sleep,None
    def request(self,operation,run,owner,files=None):
        try:
            value=dict(schemaVersion=1,commandId=uuid.uuid4().hex,action='phone-assets-files',operation=operation,runId=run,ownerToken=owner)
            if self.stage is not None:value['stage']=self.stage
            if files is not None:value['files']={key:base64.b64encode(raw).decode() for key,raw in files.items()}
            call=command(value);need(self.guard() is not False)
            started=previous=self.monotonic();need(number(started,0,1e15));requested=self.clock_ms();need(integer(requested,1));self.send(call)
            for attempt in range(51):
                need(self.guard() is not False);raw=self.original();need(type(raw) is str and len(raw.encode())<=262144)
                try:packet=decode(raw) if raw else None
                except json.JSONDecodeError:packet=None
                need(self.guard() is not False);now=self.monotonic();need(number(now,previous,1e15) and now-started<5);previous=now
                if type(packet) is dict and packet.get('requestId')==call['commandId']:
                    exact(packet,{'schemaVersion','requestId','runId','operation','instance','sequence','processId','requestedEpochMs','capturedEpochMs','source'})
                    need(type(packet['schemaVersion']) is int and packet['schemaVersion']==1 and packet['runId']==run and packet['operation']==operation
                        and nonce(packet['instance']) and integer(packet['sequence'],1) and integer(packet['processId'],1) and packet['processId']==self.pid
                        and integer(packet['requestedEpochMs'],requested) and integer(packet['capturedEpochMs'],packet['requestedEpochMs'])
                        and packet['capturedEpochMs']-packet['requestedEpochMs']<5000)
                    fresh(packet['capturedEpochMs'],self.clock_ms());source(packet['source'],run,self.stage)
                    if self.last is not None:
                        need(packet['instance']==self.last['instance'] and packet['runId']==self.last['runId'] and packet['sequence']>self.last['sequence']
                            and packet['capturedEpochMs']>=self.last['capturedEpochMs']
                            and (not self.last['source']['retired'] or packet['source']['retired'] and not packet['source']['exists']))
                    need(self.guard() is not False);fresh(packet['capturedEpochMs'],self.clock_ms())
                    now=self.monotonic();need(number(now,previous,1e15) and now-started<5);self.last=deepcopy(packet);return deepcopy(packet)
                if attempt<50:self.sleep(.1)
        except Exception:raise NativeUIError('Original Phone Assets private files are unavailable or invalid') from None
        raise NativeUIError('Original Phone Assets private files did not produce this request')
