"""Original fixed private input bundles with native inode and byte ownership."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import json
import hashlib
import math
import re
import time
import uuid
from urllib.parse import unquote,urlsplit
from adapters.native_feature_observation import decode,exact,fresh,integer,need,number
from adapters.normal_ui import NativeUIError
from adapters.token_script_file_ui import file_url
from adapters.native_avatar_render import nonce
from adapters.world_render_evidence import digest
from adapters.assets_input import NAMES,DIRECTORIES

FILE='feature-pico-assets-files.json'


def command(value):
    fields={'schemaVersion','commandId','action','operation','runId','ownerToken'}
    if type(value) is dict and 'stage' in value:fields|={'stage'};need(integer(value['stage'],1,6))
    if type(value) is dict and value.get('operation')=='stage':fields|={'files'}
    exact(value,fields)
    need(type(value['schemaVersion']) is int and value['schemaVersion']==1 and value['action']=='feature-pico-assets-files'
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


class NativeAssetsFiles:
    def __init__(self,send,read,clock_ms,guard,pid,*,monotonic=time.monotonic,sleep=time.sleep,stage=None):
        need(all(callable(v) for v in (send,read,clock_ms,guard,monotonic,sleep)) and integer(pid,1))
        need(stage is None or integer(stage,1,6));self.stage=stage
        self.send,self.original,self.clock_ms,self.guard,self.pid=send,read,clock_ms,guard,pid
        self.monotonic,self.sleep,self.last=monotonic,sleep,None
        self.last_raw=self.last_sha256=None;self.history=[]
    def request(self,operation,run,owner,files=None):
        try:
            value=dict(schemaVersion=1,commandId=uuid.uuid4().hex,action='feature-pico-assets-files',operation=operation,runId=run,ownerToken=owner)
            if self.stage is not None:value['stage']=self.stage
            if files is not None:value['files']={key:base64.b64encode(raw).decode() for key,raw in files.items()}
            call=command(value);need(len(self.history)<128 and self.guard() is not False)
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
                    fresh(packet['capturedEpochMs'],max(self.clock_ms(),requested+math.ceil((now-started)*1000)));source(packet['source'],run,self.stage)
                    if self.last is not None:
                        need(packet['instance']==self.last['instance'] and packet['runId']==self.last['runId'] and packet['sequence']>self.last['sequence']
                            and packet['capturedEpochMs']>=self.last['capturedEpochMs']
                            and (not self.last['source']['retired'] or packet['source']['retired'] and not packet['source']['exists']))
                    need(self.guard() is not False);fresh(packet['capturedEpochMs'],self.clock_ms())
                    now=self.monotonic();need(number(now,previous,1e15) and now-started<5)
                    fresh(packet['capturedEpochMs'],max(self.clock_ms(),requested+math.ceil((now-started)*1000)))
                    self.last=deepcopy(packet);self.last_raw=raw;self.last_sha256=hashlib.sha256(raw.encode()).hexdigest()
                    self.history.append(dict(command=deepcopy(call),raw=raw,sha256=self.last_sha256));return deepcopy(packet)
                if attempt<50:self.sleep(.1)
        except Exception:raise NativeUIError('Original Pico Assets private files are unavailable or invalid') from None
        raise NativeUIError('Original Pico Assets private files did not produce this request')

    def restore(self,history):
        """Validate original bytes at historical epochs, never as fresh reads."""
        need(type(history) is list and len(history)<=128 and self.last is None and not self.history)
        previous=None;seen=set()
        for original in history:
            exact(original,{'command','raw','sha256'});call=command(original['command'])
            need(type(original['raw']) is str and len(original['raw'].encode())<=262144
                and digest(original['sha256']) and hashlib.sha256(original['raw'].encode()).hexdigest()==original['sha256'])
            packet=decode(original['raw']);exact(packet,{'schemaVersion','requestId','runId','operation','instance','sequence','processId','requestedEpochMs','capturedEpochMs','source'})
            need(type(packet['schemaVersion']) is int and packet['schemaVersion']==1
                and packet['requestId']==call['commandId'] and packet['requestId'] not in seen
                and packet['runId']==call['runId'] and packet['operation']==call['operation'] and call.get('stage')==self.stage
                and nonce(packet['instance']) and integer(packet['sequence'],1,9007199254740991)
                and type(packet['processId']) is int and packet['processId']==self.pid
                and integer(packet['requestedEpochMs'],1) and integer(packet['capturedEpochMs'],packet['requestedEpochMs'])
                and packet['capturedEpochMs']-packet['requestedEpochMs']<5000)
            source(packet['source'],call['runId'],self.stage);seen.add(packet['requestId'])
            if previous is not None:
                need(packet['instance']==previous['instance'] and packet['runId']==previous['runId']
                    and packet['sequence']>previous['sequence'] and packet['capturedEpochMs']>=previous['capturedEpochMs']
                    and (not previous['source']['retired'] or packet['source']['retired'] and not packet['source']['exists']))
            previous=packet
        self.history=deepcopy(history)
        if previous is not None:
            self.last=deepcopy(previous);self.last_raw=history[-1]['raw'];self.last_sha256=history[-1]['sha256']
