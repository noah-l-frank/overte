"""Actual native Snapshot request/callback/weak-lease originals, not image proof."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import re
import secrets
import time
from adapters.native_feature_observation import decode,exact,integer,need,number
from adapters.script_journey.lock import ScriptSourceLock

VERSION=2
READS=(1,2)
FILE='feature-snapshot-capture-originals.json'
ACTION='feature-snapshot-capture-originals'
LIMIT=65536
RESOURCES={'nativeReviewEnabled','activeRequests','taking360','waitingOnSnapshot','projectionTimerActive','projectionImagesBytes'}


def nonce(value):return type(value) is str and re.fullmatch('[0-9a-f]{32}',value) is not None
def birth(value):return type(value) is str and re.fullmatch('[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}',value) is not None
def sha(value):return type(value) is str and re.fullmatch('[0-9a-f]{64}',value) is not None


def validate(value,run,request,pid,epoch):
    exact(value,{'snapshotNativeCaptureVersion','commandId','runId','instance','sequence','pid','capturedEpochMs','resources','requests'})
    need(type(value['snapshotNativeCaptureVersion']) is int and value['snapshotNativeCaptureVersion'] in READS
        and nonce(run) and value['runId']==run and nonce(request) and value['commandId']==request and value['pid']==pid
        and integer(value['pid'],1) and birth(value['instance']) and integer(value['sequence'],1)
        and integer(value['capturedEpochMs'],1) and number(epoch,1,1e15) and -250<=epoch-value['capturedEpochMs']<=1500)
    resources=value['resources'];exact(resources,RESOURCES)
    need(all(type(resources[key]) is bool for key in RESOURCES-{'activeRequests','projectionImagesBytes'})
        and resources['nativeReviewEnabled'] and integer(resources['activeRequests'],0,8)
        and integer(resources['projectionImagesBytes'],0,256*1024*1024)
        and type(value['requests']) is list and len(value['requests'])<=32)
    identities=set()
    for row in value['requests']:
        exact(row,{'birth','requestId','registeredEpochMs','alive','nativeState','events'})
        need(birth(row['birth']) and row['birth'] not in identities and type(row['requestId']) is str
            and re.fullmatch('[A-Za-z0-9_-]{1,64}',row['requestId']) and integer(row['registeredEpochMs'],1,value['capturedEpochMs'])
            and type(row['alive']) is bool and row['nativeState'] in (('active','completed','cancelled') if row['alive'] else ('',))
            and type(row['events']) is list and len(row['events'])<=16)
        identities.add(row['birth']);last=row['registeredEpochMs'];terminal=False
        for index,event in enumerate(row['events']):
            exact(event,{'sequence','phase','publishedEpochMs','pathSha256','basenameSha256','error'}
                | ({'canonicalPathSha256'} if value['snapshotNativeCaptureVersion']==2 else set()))
            need(not terminal and type(event['sequence']) is int and event['sequence']==index+1
                and event['phase'] in ('processing','complete','cancelled','error') and integer(event['publishedEpochMs'],last,value['capturedEpochMs'])
                and type(event['error']) is str and len(event['error'])<=1024
                and ((event['pathSha256']==event['basenameSha256']=='') or sha(event['pathSha256']) and sha(event['basenameSha256'])))
            if event['phase']=='complete':need(sha(event['pathSha256']) and not event['error'])
            if event['phase']=='cancelled':need(event['pathSha256']==event['basenameSha256']==event['error']=='')
            if value['snapshotNativeCaptureVersion']==2:
                need(event['canonicalPathSha256']=='' or sha(event['canonicalPathSha256']))
                if event['phase']=='complete':need(sha(event['canonicalPathSha256']))
                if event['phase']=='cancelled' or event['pathSha256']=='':need(event['canonicalPathSha256']=='')
            terminal=event['phase'] in ('complete','cancelled','error');last=event['publishedEpochMs']
        if row['alive'] and row['events'] and terminal:
            need(row['nativeState']==('cancelled' if row['events'][-1]['phase']=='cancelled' else 'completed'))
    return value


def accept(previous,current):
    validate(current,current['runId'],current['commandId'],current['pid'],current['capturedEpochMs'])
    if previous is not None:
        validate(previous,previous['runId'],previous['commandId'],previous['pid'],previous['capturedEpochMs'])
        need(current['instance']==previous['instance'] and current['runId']==previous['runId'] and current['pid']==previous['pid']
            and current['snapshotNativeCaptureVersion']==previous['snapshotNativeCaptureVersion']
            and current['sequence']>previous['sequence'] and current['commandId']!=previous['commandId']
            and current['capturedEpochMs']>=previous['capturedEpochMs'] and len(current['requests'])>=len(previous['requests']))
        for old,new in zip(previous['requests'],current['requests']):
            need(all(new[key]==old[key] for key in ('birth','requestId','registeredEpochMs'))
                and new['events'][:len(old['events'])]==old['events'] and (old['alive'] or not new['alive']))
            if old['alive'] and new['alive'] and old['nativeState']!='active':need(new['nativeState']==old['nativeState'])
    return deepcopy(current)


class PicoSnapshotOriginals:
    def __init__(self,send,read,clock_ms,guard,pid,source_lock,*,monotonic=time.monotonic,sleep=time.sleep):
        need(isinstance(source_lock,ScriptSourceLock) and integer(pid,1) and all(callable(f) for f in (send,read,clock_ms,guard,monotonic,sleep)))
        self.send,self.read,self.clock_ms,self.guard,self.pid,self.lock=send,read,clock_ms,guard,pid,source_lock
        self.monotonic,self.sleep=monotonic,sleep;self.previous=self.last_raw=None
    def restore(self,value):
        validate(value,value['runId'],value['commandId'],self.pid,value['capturedEpochMs'])
        need(self.previous is None or self.previous==value)
        self.previous=deepcopy(value)
    def capture(self,run,operation='read'):
        need(nonce(run) and operation in ('arm','read'))
        with self.lock.held():
            started=self.monotonic();requested=self.clock_ms();need(number(started,0,1e15) and integer(requested,1) and self.guard() is not False)
            request=secrets.token_hex(16);self.send(dict(schemaVersion=1,commandId=request,runId=run,action=ACTION,operation=operation))
            for attempt in range(31):
                raw=self.read();need(raw is None or type(raw) is str and len(raw.encode())<=LIMIT)
                if raw:
                    value=decode(raw)
                    if value.get('commandId')==request:
                        epoch=self.clock_ms();validate(value,run,request,self.pid,epoch)
                        need(value['capturedEpochMs']>=requested);accepted=accept(self.previous,value)
                        result=deepcopy(accepted);saved=deepcopy(accepted)
                        need(self.guard() is not False);final=self.clock_ms();completed=self.monotonic()
                        need(number(completed,started,1e15) and number(final,epoch,1e15) and -250<=final-value['capturedEpochMs']
                            and max(final-value['capturedEpochMs'],requested-value['capturedEpochMs']+(completed-started)*1000)<=1500)
                        self.previous,self.last_raw=saved,raw;return result
                need(self.monotonic()-started<5 and attempt<30);self.sleep(.1)
            need(False)
    def original(self):
        need(self.last_raw is not None)
        return dict(raw=self.last_raw,sha256=hashlib.sha256(self.last_raw.encode()).hexdigest())
