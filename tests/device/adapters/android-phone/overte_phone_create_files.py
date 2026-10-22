"""Original app-private Create input/output files, distinct from normal UI input.

A file receipt is no Create/export verdict. The owner must retain intent before
stage, ordinary export and release; original product bytes are independently
read and validated. This source cannot produce an exported selection.
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
from adapters.token_script_file_ui import file_url
from overte_phone_create_fixture import NAMES

FILE='phone-create-files.json'


def command(value):
    fields={'schemaVersion','commandId','action','operation','runId','ownerToken'}
    if type(value) is dict and value.get('operation')=='stage':fields.add('files')
    exact(value,fields)
    need(type(value['schemaVersion']) is int and value['schemaVersion']==1 and value['action']=='phone-create-files'
         and value['operation'] in ('stage','observe','seal-export','release')
         and all(type(value[key]) is str and re.fullmatch('[0-9a-f]{32}',value[key]) for key in ('commandId','runId'))
         and type(value['ownerToken']) is str and re.fullmatch('[0-9a-f]{64}',value['ownerToken']))
    if value['operation']=='stage':
        exact(value['files'],NAMES)
        for encoded in value['files'].values():
            need(type(encoded) is str and 0<len(encoded)<=32768)
            raw=base64.b64decode(encoded,validate=True)
            need(0<len(raw)<=16384 and base64.b64encode(raw).decode()==encoded)
    need(len(json.dumps(value).encode())<=49152)
    return value


def identity(value):
    exact(value,{'device','inode','size','modifiedNs','changedNs'})
    need(all(type(raw) is str and re.fullmatch('0|[1-9][0-9]{0,20}',raw) for raw in value.values()))
    return value


def source(value,run):
    exact(value,{'createFilesVersion','exists','retired','retiring','directory','rootIdentity','files','exportSealed'})
    need(type(value['createFilesVersion']) is int and value['createFilesVersion']==1
         and all(type(value[key]) is bool for key in ('exists','retired','retiring','exportSealed'))
         and file_url(value['directory']).endswith('/feature-create-'+run) and type(value['files']) is list)
    if not value['exists']:
        need(value['files']==[] and value['rootIdentity'] is None and not value['exportSealed']);return value
    need(not value['retired'] and len(value['files'])==3);identity(value['rootIdentity'])
    seen=set();present=set()
    for row in value['files']:
        need(type(row) is dict and row.get('name') in (*NAMES,'selection.json') and row['name'] not in seen
             and type(row.get('exists')) is bool)
        fields={'name','exists'}
        if row['exists']:
            fields|={'identity','bytes','sha256','base64'}
            need(integer(row.get('bytes'),1,65536 if row['name']=='selection.json' else 16384))
        exact(row,fields)
        if row['exists']:
            identity(row['identity']);need(int(row['identity']['size'])==row['bytes']
                and type(row['base64']) is str and len(row['base64'])<=90000)
            raw=base64.b64decode(row['base64'],validate=True)
            need(len(raw)==row['bytes'] and base64.b64encode(raw).decode()==row['base64']
                 and hashlib.sha256(raw).hexdigest()==row['sha256'])
            present.add(row['name'])
        seen.add(row['name'])
    need(not value['exportSealed'] or 'selection.json' in present or value['retiring'])
    return value


class PhoneCreateFiles:
    def __init__(self,send,read,clock_ms,guard,pid,*,monotonic=time.monotonic,sleep=time.sleep):
        need(all(callable(fn) for fn in (send,read,clock_ms,guard,monotonic,sleep)) and integer(pid,1))
        self.send,self.original,self.clock_ms,self.guard,self.pid=send,read,clock_ms,guard,pid
        self.monotonic,self.sleep,self.last=monotonic,sleep,None

    def request(self,operation,run,owner,files=None):
        try:
            call=dict(schemaVersion=1,commandId=uuid.uuid4().hex,action='phone-create-files',operation=operation,
                      runId=run,ownerToken=owner)
            if files is not None:
                need(type(files) is dict and all(type(raw) is bytes for raw in files.values()))
                call['files']={name:base64.b64encode(raw).decode() for name,raw in files.items()}
            command(call);need(self.guard() is not False)
            started=previous=self.monotonic();need(number(started,0,1e15))
            requested=self.clock_ms();need(integer(requested,1));self.send(call)
            for attempt in range(51):
                need(self.guard() is not False)
                raw=self.original();need(type(raw) is str and len(raw.encode())<=262144)
                try:packet=decode(raw) if raw else None
                except json.JSONDecodeError:packet=None
                need(self.guard() is not False)
                now=self.monotonic();need(number(now,previous,1e15) and now-started<5);previous=now
                if type(packet) is dict and packet.get('requestId')==call['commandId']:
                    exact(packet,{'schemaVersion','requestId','runId','operation','instance','sequence','processId',
                                  'requestedEpochMs','capturedEpochMs','source'})
                    need(type(packet['schemaVersion']) is int and packet['schemaVersion']==1 and packet['runId']==run
                         and packet['operation']==operation and type(packet['instance']) is str and re.fullmatch('[0-9a-f]{32}',packet['instance'])
                         and integer(packet['sequence'],1) and integer(packet['processId'],1) and packet['processId']==self.pid
                         and integer(packet['requestedEpochMs'],requested) and integer(packet['capturedEpochMs'],packet['requestedEpochMs'])
                         and packet['capturedEpochMs']-packet['requestedEpochMs']<5000)
                    epoch=self.clock_ms();fresh(packet['capturedEpochMs'],epoch);source(packet['source'],run)
                    if self.last is not None:
                        need(packet['instance']==self.last['instance'] and packet['runId']==self.last['runId']
                             and packet['sequence']>self.last['sequence'] and packet['capturedEpochMs']>=self.last['capturedEpochMs']
                             and (not self.last['source']['retired'] or packet['source']['retired'] and not packet['source']['exists']))
                    need(self.guard() is not False);fresh(packet['capturedEpochMs'],self.clock_ms())
                    now=self.monotonic();need(number(now,previous,1e15) and now-started<5)
                    self.last=deepcopy(packet);return deepcopy(packet)
                if attempt<50:self.sleep(.1)
        except Exception:
            raise NativeUIError('Original Phone Create file storage is unavailable or invalid') from None
        raise NativeUIError('Original Phone Create file storage did not produce this request')
