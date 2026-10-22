"""Original native capture file FD/namespace/close/one-send retirement source."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import re
import time
import uuid
import hashlib
from adapters.pico4.navigation import NativeNavigationIO
from adapters.script_journey.lock import ScriptSourceLock
from adapters.native_feature_observation import decode,exact,fresh,integer,need,number
from adapters.normal_ui import NativeUIError
from adapters.pico4.snapshot_originals import nonce
ROOTS={"/data/"+base+"/org.overte.pico/files/Snapshots" for base in ("user/0","data")}
def capture_id(value):return type(value) is str and re.fullmatch("[A-Za-z0-9_-]{1,64}",value) is not None

FILE='feature-pico-snapshot-files.json'
VERSION=1
PREFIX=re.compile(r'(?:e2e-[0-9a-f]{32}(?:-[A-Za-z0-9_-]{1,11})?|parity-[0-9a-f]{16}-(?:still-png|still-jpg|animated|panorama|cubemap))')


def prefix(value):return type(value) is str and len(value)<=48 and PREFIX.fullmatch(value) is not None

def path(value):
    return type(value) is str and len(value)<=2048 and any(value.startswith(root+'/') and '/' not in value[len(root)+1:]
        and value[len(root)+1:] not in ('','.','..') and '\\' not in value and all(ord(char)>=32 and ord(char)!=127 for char in value) for root in ROOTS)


def command(value):
    control=type(value) is dict and value.get('action')=='pico-snapshot-files-control'
    exact(value,{'schemaVersion','commandId','action','runId'}|({'operation','prefix','fileId','operationId'} if control else set()))
    need(type(value['schemaVersion']) is int and value['schemaVersion']==1 and nonce(value['commandId']) and nonce(value['runId'])
        and value['action'] in ('pico-snapshot-files-observe','pico-snapshot-files-control'))
    if control:
        need(nonce(value['operationId']))
        if value['operation']=='plan':need(prefix(value['prefix']) and value['fileId']=='')
        else:need(value['operation'] in ('retire','seal') and value['prefix']=='' and nonce(value['fileId']))
    return value


def source(value,epoch):
    exact(value,{'picoSnapshotCaptureFilesVersion','instance','complete','sequence','capturedEpochMs','rows','captures','plans'})
    need(type(value['picoSnapshotCaptureFilesVersion']) is int and value['picoSnapshotCaptureFilesVersion']==1
        and nonce(value['instance']) and value['complete'] is True and integer(value['sequence'],1)
        and integer(value['capturedEpochMs'],1,epoch)
        and all(type(value[key]) is list and len(value[key])<=64 for key in ('rows','captures','plans')))
    plans={};events=set();names=[];operations=set()
    for row in value['plans']:
        exact(row,{'id','runId','prefix','event','checkedEpochMs','rootPresent','rootDevice','rootInode','sealed','sealId','sealedEpochMs'})
        need(nonce(row['id']) and row['id'] not in plans and nonce(row['runId']) and prefix(row['prefix'])
            and integer(row['event'],1) and row['event'] not in events and integer(row['checkedEpochMs'],1,value['capturedEpochMs'])
            and type(row['rootPresent']) is bool and integer(row['rootDevice']) and integer(row['rootInode']))
        need(not any(older==row['prefix'] or older.startswith(row['prefix']+'-') or row['prefix'].startswith(older+'-') for older in names))
        need(row['rootInode']>0 if row['rootPresent'] else row['rootInode']==row['rootDevice']==0)
        need(type(row['sealed']) is bool and integer(row['sealedEpochMs'],0,value['capturedEpochMs']))
        if row['sealed']:
            need(nonce(row['sealId']) and row['sealId'] not in operations and row['sealedEpochMs']>=row['checkedEpochMs']);operations.add(row['sealId'])
        else:need(row['sealId']=='' and row['sealedEpochMs']==0)
        plans[row['id']]=row;events.add(row['event']);names.append(row['prefix'])
    need(not operations.intersection(plans))
    captures={}
    for row in value['captures']:
        exact(row,{'captureId','event','beganEpochMs','terminal','terminalPath','terminalEpochMs'})
        need(capture_id(row['captureId']) and row['captureId'] not in captures and integer(row['event'],1) and row['event'] not in events
            and integer(row['beganEpochMs'],1,value['capturedEpochMs']) and row['terminal'] in ('','complete','cancelled','error'))
        if row['terminal']=='':need(row['terminalPath']=='' and row['terminalEpochMs']==0)
        else:need(integer(row['terminalEpochMs'],row['beganEpochMs'],value['capturedEpochMs']) and (row['terminalPath']=='' or path(row['terminalPath'])))
        if row['terminal']=='complete':need(path(row['terminalPath']))
        captures[row['captureId']]=row;events.add(row['event'])
    ids=set();roots={}
    for row in value['rows']:
        exact(row,{'id','captureId','path','planId','runId','sha256','retireId','deleteIssued','deleteResult','absent','checkedEpochMs',
            'phase','preexisting','rootDevice','rootInode','device','inode','uid','links','opened','closed','bytes','createdEpochMs','closedEpochMs',
            'removeAttempted','removeAttempts','nativeRemoved'})
        need(nonce(row['id']) and row['id'] not in ids and row['captureId'] in captures and path(row['path'])
            and row['phase'] in ('opening','writing','closing','closed','open-failed')
            and all(type(row[key]) is bool for key in ('preexisting','deleteIssued','absent','opened','closed','removeAttempted','nativeRemoved'))
            and integer(row['rootDevice']) and integer(row['rootInode'],1) and integer(row['device']) and integer(row['inode']) and integer(row['uid'])
            and integer(row['links'],0,1) and integer(row['bytes'],0,256*1024*1024)
            and integer(row['createdEpochMs'],captures[row['captureId']]['beganEpochMs'],value['capturedEpochMs'])
            and integer(row['closedEpochMs'],0,value['capturedEpochMs']) and integer(row['checkedEpochMs'],0,value['capturedEpochMs'])
            and integer(row['removeAttempts'],0,4) and integer(row['deleteResult'],-2,0))
        ids.add(row['id'])
        if row['planId']:
            plan=plans.get(row['planId']);need(plan is not None and row['runId']==plan['runId']
                and row['path'].rsplit('/',1)[-1].startswith(plan['prefix']+'-') and captures[row['captureId']]['event']>plan['event']
                and row['createdEpochMs']>=plan['checkedEpochMs'])
            root=(row['rootDevice'],row['rootInode']);need(roots.setdefault(row['planId'],root)==root)
            if plan['rootPresent']:need(row['rootDevice']==plan['rootDevice'] and row['rootInode']==plan['rootInode'])
        else:need(row['runId']=='')
        if row['opened']:need(row['inode']>0 and row['links']==1 and row['phase'] in ('writing','closing','closed'))
        else:need(row['device']==row['inode']==row['uid']==row['links']==row['bytes']==0 and row['phase'] in ('opening','open-failed'))
        if row['closed']:
            need(row['phase'] in ('closed','open-failed') and row['closedEpochMs']>=row['createdEpochMs'])
            if row['opened']:need(type(row['sha256']) is str and re.fullmatch('[0-9a-f]{64}',row['sha256']))
            else:need(row['sha256']=='')
        else:need(row['closedEpochMs']==0 and row['sha256']=='' and row['phase'] in ('opening','writing','closing'))
        need(row['removeAttempted']==(row['removeAttempts']>0) and (not row['nativeRemoved'] or row['removeAttempted']) and (not row['removeAttempted'] or row['closed']))
        if row['retireId']:
            need(nonce(row['retireId']) and row['retireId'] not in operations and row['retireId'] not in plans and row['planId']
                and not row['preexisting'] and row['closed'] and row['checkedEpochMs']>0 and row['absent']
                and captures[row['captureId']]['terminal']!='')
            operations.add(row['retireId'])
            if row['deleteIssued']:need(row['opened'] and not row['nativeRemoved'] and row['deleteResult'] in (-1,0))
            else:need(row['deleteResult']==-2 and (row['nativeRemoved'] or not row['opened']))
        else:need(not row['deleteIssued'] and row['deleteResult']==-2 and not row['absent'] and row['checkedEpochMs']==0)
    for plan in value['plans']:
        if plan['sealed']:need(all(row['retireId'] and row['absent'] for row in value['rows'] if row['planId']==plan['id']))
    for capture in value['captures']:
        if capture['terminal']=='complete':need(any(row['captureId']==capture['captureId'] and row['path']==capture['terminalPath'] and row['opened'] and row['closed'] for row in value['rows']))
    return value


def continuity(before,after):
    need(all(after[key]==before[key] for key in ('runId','instance','processId')) and after['sequence']>before['sequence'] and after['capturedEpochMs']>=before['capturedEpochMs'])
    a,b=before['source'],after['source'];need(b['instance']==a['instance'] and b['sequence']>a['sequence'] and b['capturedEpochMs']>=a['capturedEpochMs'])
    for key,id in (('plans','id'),('captures','captureId'),('rows','id')):
        old={row[id]:row for row in a[key]};new={row[id]:row for row in b[key]};need(set(old)<=set(new))
        for identifier,row in old.items():
            current=new[identifier]
            if key=='plans':
                need(all(current[field]==row[field] for field in ('id','runId','prefix','event','checkedEpochMs','rootPresent','rootDevice','rootInode')))
                if row['sealed']:need(row==current)
            elif key=='captures':
                need(all(current[field]==row[field] for field in ('captureId','event','beganEpochMs')))
                if row['terminal']:need(row==current)
            else:
                need(all(current[field]==row[field] for field in ('id','captureId','path','planId','runId','preexisting','rootDevice','rootInode','createdEpochMs')))
                if row['opened']:need(current['opened'] and all(current[field]==row[field] for field in ('device','inode','uid','links')))
                if row['closed']:need(current['closed'] and all(current[field]==row[field] for field in ('bytes','sha256','closedEpochMs')))
                need(current['removeAttempts']>=row['removeAttempts'] and (not row['nativeRemoved'] or current['nativeRemoved']))
                if row['retireId']:need(all(current[field]==row[field] for field in ('retireId','deleteIssued','deleteResult','absent')) and current['checkedEpochMs']>=row['checkedEpochMs'])


def validate(value,request,pid,epoch):
    command(request)
    exact(value,{'schemaVersion','requestId','runId','instance','sequence','processId','requestedEpochMs','capturedEpochMs','accepted','source'})
    need(type(value['schemaVersion']) is int and value['schemaVersion']==1 and value['runId']==request['runId'] and value['requestId']==request['commandId'] and nonce(value['instance']) and integer(value['sequence'],1)
        and type(value['accepted']) is bool and type(value['processId']) is int and value['processId']==pid
        and integer(value['requestedEpochMs'],1) and integer(value['capturedEpochMs'],value['requestedEpochMs']) and value['capturedEpochMs']-value['requestedEpochMs']<1500)
    fresh(value['capturedEpochMs'],epoch);source(value['source'],value['capturedEpochMs'])
    need(value['source']['capturedEpochMs']>=value['requestedEpochMs'])
    return value




class PicoSnapshotCaptureFileIO(NativeNavigationIO):
    # Reuse the actual original writer and its final immutable owner callback.
    # The existing Probe receives this fixed Android control command filename.
    DIRECTORY='files/overte-e2e/android-control-'
    def guard(self):
        super().guard();self.adapter._installation(self.target)
    def raw(self):
        return self.adapter.adb.read_debug_app_file(self.target,'org.overte.pico','files/overte-e2e/'+FILE,attempts=1)
    def _read(self,kind):
        need(kind=='status');raw=self.raw()
        if raw is None or raw=='':return raw
        actual=decode(raw)
        # Only transport correlation. The strict original packet is acquired
        # independently below; this envelope never supplies a file-state fact.
        return json.dumps(dict(commandId=actual.get('requestId'),packet=actual))


class PicoSnapshotCaptureFileSource:
    def __init__(self,io,clock_ms,pid,source_lock,*,read_only=True,monotonic=time.monotonic,sleep=time.sleep):
        need(isinstance(io,PicoSnapshotCaptureFileIO) and isinstance(source_lock,ScriptSourceLock)
            and integer(pid,1) and type(read_only) is bool and (read_only or callable(io._before_send))
            and all(callable(fn) for fn in (clock_ms,monotonic,sleep)))
        self.io,self.clock_ms,self.pid,self.lock=io,clock_ms,pid,source_lock
        self.read_only,self.monotonic,self.sleep=read_only,monotonic,sleep;self.last=self.raw=self.last_request=None
    @staticmethod
    def envelope(run,operation='observe',*,prefix='',file_id='',operation_id=''):
        request=dict(schemaVersion=1,commandId=uuid.uuid4().hex,action='pico-snapshot-files-observe',runId=run)
        if operation!='observe':request.update(action='pico-snapshot-files-control',operation=operation,prefix=prefix,fileId=file_id,operationId=operation_id)
        else:need(prefix==file_id==operation_id=='')
        command(request);return request
    def restore(self,value,request):
        validate(value,request,self.pid,value['capturedEpochMs']);need(self.last is None)
        self.last=deepcopy(value) # Historical prefix only; subsequent reads need a new actual native nonce.
    def request(self,run,operation='observe',*,prefix='',file_id='',operation_id=''):
        request=self.envelope(run,operation,prefix=prefix,file_id=file_id,operation_id=operation_id)
        need(not self.read_only or operation=='observe')
        with self.lock.held():
            started=self.monotonic();requested=self.clock_ms();need(number(started,0,1e15) and integer(requested,1))
            self.io.bind_input();self.io.send(deepcopy(request))
            previous=started
            for attempt in range(31):
                self.io.guard();raw=self.io.raw();need(raw is None or type(raw) is str and len(raw.encode())<=262144)
                if raw:
                    value=decode(raw)
                    if value.get('requestId')==request['commandId']:
                        epoch=self.clock_ms();validate(value,request,self.pid,epoch);need(value['requestedEpochMs']>=requested)
                        if self.last is not None:continuity(self.last,value)
                        result=deepcopy(value);saved=deepcopy(value);saved_request=deepcopy(request)
                        self.io.guard();final=self.clock_ms();completed=self.monotonic()
                        need(number(completed,previous,1e15) and completed-started<5 and number(final,epoch,1e15)
                            and -250<=final-value['capturedEpochMs'] and max(final-value['capturedEpochMs'],
                                requested-value['capturedEpochMs']+(completed-started)*1000)<=1500)
                        self.last,self.raw,self.last_request=saved,raw,saved_request;return result
                now=self.monotonic();need(number(now,previous,1e15) and now-started<5 and attempt<30);previous=now;self.sleep(.1)
            need(False)
    def original(self):
        need(self.raw is not None)
        return dict(raw=self.raw,sha256=hashlib.sha256(self.raw.encode()).hexdigest(),request=deepcopy(self.last_request))
