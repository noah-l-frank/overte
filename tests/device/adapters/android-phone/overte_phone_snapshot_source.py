"""Read-only original capture/upload history and current native responsibilities.

This source is not a capture/export verdict. The public owner must join actual
normal input, original files/pixels, Android export readbacks and the peer.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import re
import time
import uuid

from adapters.native_feature_observation import decode,exact,fresh,integer,need,number
from adapters.normal_ui import NativeUIError
from overte_phone_snapshot_exports import exports,continuity as export_continuity

FILE='phone-snapshot-observation.json'
ROOTS={'/data/'+base+'/io.github.noah_be.overte.phone/files/Snapshots' for base in ('user/0','data')}


def nonce(value):return type(value) is str and re.fullmatch('[0-9a-f]{32}',value) is not None
def text(value,limit):return type(value) is str and len(value)<=limit and all(ord(ch)>=32 and ord(ch)!=127 for ch in value)
def capture_id(value):return type(value) is str and re.fullmatch('[A-Za-z0-9_-]{1,64}',value) is not None


def command(value):
    exact(value,{'schemaVersion','commandId','action','runId'})
    need(type(value['schemaVersion']) is int and value['schemaVersion']==1 and value['action']=='phone-snapshot-observe'
        and nonce(value['commandId']) and nonce(value['runId']))
    return value


def review(value,valid_path):
    exact(value,{'snapshotReviewObservationVersion','present','review'})
    need(type(value['snapshotReviewObservationVersion']) is int and value['snapshotReviewObservationVersion']==1
        and type(value['present']) is bool)
    if not value['present']:need(value['review'] is None);return value
    row=value['review']
    exact(row,{'componentUrl','visible','capturing','processing','loggedIn','canShare','canBlast','statusError',
        'captureSettingsLoaded','statusText','uploadPath','exportTicket','mode','format','capabilities','exportBusy','exportError','images'})
    from urllib.parse import urlsplit
    component=urlsplit(row['componentUrl'])
    need(component.scheme in ('file','qrc') and not component.netloc and not component.query and not component.fragment
        and component.path.endswith('/system/snapshot/NativeSnapshotReview.qml')
        and all(type(row[key]) is bool for key in ('visible','capturing','processing','loggedIn','canShare','canBlast',
            'statusError','captureSettingsLoaded','exportBusy')) and (not row['processing'] or row['capturing'])
        and text(row['statusText'],2048) and text(row['exportError'],256) and text(row['exportTicket'],64)
        and (row['uploadPath']=='' or valid_path(row['uploadPath'])) and integer(row['mode'],0,3)
        and row['format'] in ('png','jpg','jpeg','webp') and type(row['capabilities']) is list
        and len(row['capabilities'])<=2 and len(set(row['capabilities']))==len(row['capabilities'])
        and all(raw in ('save','share') for raw in row['capabilities']) and type(row['images']) is list and len(row['images'])<=8)
    seen=set()
    for image in row['images']:
        exact(image,{'path','storyPresent'})
        need(valid_path(image['path']) and image['path'] not in seen and type(image['storyPresent']) is bool);seen.add(image['path'])
    return value


def source(value):
    exact(value,{'phoneSnapshotObservationVersion','nativeReview','storageRoot','captures','uploads','history','review','androidExport'})
    need(type(value['phoneSnapshotObservationVersion']) is int and value['phoneSnapshotObservationVersion']==3
        and value['nativeReview'] is True and value['storageRoot'] in ROOTS)
    root=value['storageRoot']
    def path(raw):
        return (text(raw,2048) and raw.startswith(root+'/') and '/' not in raw[len(root)+1:]
            and raw[len(root)+1:] not in ('','.','..') and '\\' not in raw)
    history=value['history'];exact(history,{'snapshotHistoryVersion','instance','complete','sequence','events'})
    need(type(history['snapshotHistoryVersion']) is int and history['snapshotHistoryVersion']==1 and nonce(history['instance'])
        and history['complete'] is True and integer(history['sequence'],0,256)
        and type(history['events']) is list and len(history['events'])==history['sequence'])
    epoch=elapsed=0;begun=set()
    for index,row in enumerate(history['events'],1):
        exact(row,{'sequence','kind','id','phase','path','error','capturedEpochMs','elapsedMs'})
        need(type(row['sequence']) is int and row['sequence']==index and integer(row['capturedEpochMs'],max(1,epoch))
            and integer(row['elapsedMs'],elapsed) and text(row['error'],256))
        kind=row['kind'];need(kind in ('capture-begin','capture-status','upload-begin','upload-status'))
        if kind.startswith('capture-'):
            need(capture_id(row['id']) and (row['path']=='' or path(row['path'])))
            if kind=='capture-begin':need(row['id'] not in begun and row['path']=='');begun.add(row['id'])
        else:need(path(row['id']) and row['path']==row['id'])
        if kind.endswith('-begin'):need(row['phase']==row['error']=='')
        else:need(row['phase'] in (('processing','complete','cancelled','error') if kind=='capture-status' else ('success','cancelled','error')))
        epoch,elapsed=row['capturedEpochMs'],row['elapsedMs']
    captures=value['captures'];need(type(captures) is list and len(captures)<=8)
    ids=[]
    for row in captures:
        exact(row,{'id','state','announced'})
        need(capture_id(row['id']) and row['id'] in begun and row['state'] in ('active','cancelled','completed') and type(row['announced']) is bool)
        ids.append(row['id'])
    need(ids==sorted(set(ids)))
    uploads=value['uploads'];need(type(uploads) is list and len(uploads)<=64 and all(path(raw) for raw in uploads) and uploads==sorted(set(uploads)))
    review(value['review'],path)
    exports(value['androidExport'],path)
    return value


def validate(value,request,pid,epoch):
    command(request)
    exact(value,{'schemaVersion','requestId','runId','instance','sequence','processId','requestedEpochMs','capturedEpochMs','source'})
    need(type(value['schemaVersion']) is int and value['schemaVersion']==1 and value['requestId']==request['commandId']
        and value['runId']==request['runId'] and nonce(value['instance']) and integer(value['sequence'],1,1_000_000_000)
        and integer(value['processId'],1) and value['processId']==pid and integer(value['requestedEpochMs'],1)
        and integer(value['capturedEpochMs'],value['requestedEpochMs']) and value['capturedEpochMs']-value['requestedEpochMs']<1500)
    fresh(value['capturedEpochMs'],epoch);source(value['source'])
    need(all(row['capturedEpochMs']<=value['capturedEpochMs'] for row in value['source']['history']['events']))
    need(integer(value['source']['androidExport']['capturedEpochMs'],value['requestedEpochMs'],value['capturedEpochMs']))
    return value


def continuity(before,after):
    need(after['runId']==before['runId'] and after['instance']==before['instance'] and after['processId']==before['processId']
        and after['sequence']>before['sequence'] and after['capturedEpochMs']>=before['capturedEpochMs']
        and after['source']['storageRoot']==before['source']['storageRoot'])
    a,b=before['source']['history'],after['source']['history']
    need(b['instance']==a['instance'] and b['sequence']>=a['sequence'] and b['events'][:len(a['events'])]==a['events'])
    export_continuity(before['source']['androidExport'],after['source']['androidExport'])


class PhoneSnapshotSource:
    def __init__(self,send,read,clock_ms,guard,pid,*,monotonic=time.monotonic,sleep=time.sleep):
        need(all(callable(fn) for fn in (send,read,clock_ms,guard,monotonic,sleep)) and integer(pid,1))
        self.send,self.original,self.clock_ms,self.guard,self.pid=send,read,clock_ms,guard,pid
        self.monotonic,self.sleep,self.last=monotonic,sleep,None

    def read(self,run):
        try:
            request=command(dict(schemaVersion=1,commandId=uuid.uuid4().hex,action='phone-snapshot-observe',runId=run))
            need(self.guard() is not False);started=previous=self.monotonic();need(number(started,0,1e15))
            requested=self.clock_ms();need(integer(requested,1));self.send(request)
            for attempt in range(51):
                need(self.guard() is not False);raw=self.original();need(type(raw) is str and len(raw.encode())<=262144)
                try:value=decode(raw) if raw else None
                except json.JSONDecodeError:value=None
                need(self.guard() is not False);now=self.monotonic();need(number(now,previous,1e15) and now-started<5);previous=now
                if type(value) is dict and value.get('requestId')==request['commandId']:
                    epoch=self.clock_ms();need(integer(epoch,requested));validate(value,request,self.pid,epoch)
                    need(value['requestedEpochMs']>=requested)
                    if self.last is not None:continuity(self.last,value)
                    need(self.guard() is not False);fresh(value['capturedEpochMs'],self.clock_ms())
                    now=self.monotonic();need(number(now,previous,1e15) and now-started<5)
                    self.last=deepcopy(value);return deepcopy(value)
                if attempt<50:self.sleep(.1)
        except Exception:
            raise NativeUIError('Original Phone Snapshot observation is unavailable or invalid') from None
        raise NativeUIError('Original Phone Snapshot observation did not produce this request')
