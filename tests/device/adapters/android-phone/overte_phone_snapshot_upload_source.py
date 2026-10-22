"""Read-only original Snapshot upload jobs, network replies and lifetimes."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import hashlib
import json
import re
import time
import uuid
from urllib.parse import urlsplit
from adapters.native_feature_observation import decode,exact,fresh,integer,need,number
from adapters.normal_ui import NativeUIError
from overte_phone_snapshot_source import ROOTS,nonce,text

FILE='phone-snapshot-upload-observation.json'
SHA=re.compile('[0-9a-f]{64}')


def command(value):
    exact(value,{'schemaVersion','commandId','action','runId'})
    need(type(value['schemaVersion']) is int and value['schemaVersion']==1 and value['action']=='phone-snapshot-upload-observe' and nonce(value['commandId']) and nonce(value['runId']))
    return value


def path(value):
    need(text(value,2048) and any(value.startswith(root+'/') and '/' not in value[len(root)+1:] and value[len(root)+1:] not in ('','.','..') and '\\' not in value for root in ROOTS));return value


def sha(value):need(type(value) is str and SHA.fullmatch(value));return value


def source(value,epoch):
    exact(value,{'snapshotUploadObservationVersion','instance','complete','capturedEpochMs','sequence','events','jobs'})
    need(type(value['snapshotUploadObservationVersion']) is int and value['snapshotUploadObservationVersion']==1 and nonce(value['instance']) and value['complete'] is True and integer(value['capturedEpochMs'],1,epoch) and integer(value['sequence'],0,256) and type(value['events']) is list and len(value['events'])==value['sequence'] and type(value['jobs']) is list and len(value['jobs'])<=32)
    ids=[];request_ids=set()
    for job in value['jobs']:
        exact(job,{'id','path','href','uploaderAlive','fileAlive','multipartAlive','file','cancelRequested','terminal','requests'})
        need(nonce(job['id']) and job['terminal'] in ('','error','cancelled','success') and all(type(job[key]) is bool for key in ('uploaderAlive','fileAlive','multipartAlive','cancelRequested')) and text(job['href'],4096));path(job['path']);ids.append(job['id'])
        file=job['file'];need(type(file) is dict)
        if file:
            exact(file,{'bytes','sha256','device','inode','readBytes','readSha256'})
            need(integer(file['bytes'],1,32*1024*1024) and integer(file['device']) and integer(file['inode'],1) and integer(file['readBytes'],0,32*1024*1024));sha(file['sha256']);sha(file['readSha256'])
        else:need(not job['fileAlive'] and not job['multipartAlive'])
        need(type(job['requests']) is list and len(job['requests'])<=4)
        for row in job['requests']:
            exact(row,{'id','stage','url','operation','authRequired','authorizationPresent','multipart','boundary','bodyBytes','bodySha256','dispatchCurrent','sentBytes','totalBytes','finished','destroyed','status','networkError','responseId','replyBytes','replySha256','replyBase64'})
            need(nonce(row['id']) and row['id'] not in request_ids and row['stage'] in ('image','story') and type(row['operation']) is int and row['operation']==4 and all(type(row[k]) is bool for k in ('authRequired','authorizationPresent','multipart','dispatchCurrent','finished','destroyed')))
            request_ids.add(row['id']);url=urlsplit(row['url'])
            need(url.scheme=='https' and url.hostname and not url.username and not url.password and not url.query and not url.fragment and url.path==('/api/v1/snapshots' if row['stage']=='image' else '/api/v1/user_stories') and text(row['url'],4096))
            need(row['authRequired'] and row['authorizationPresent'] and row['dispatchCurrent'] and row['multipart']==(row['stage']=='image') and integer(row['bodyBytes'],0,16384) and integer(row['sentBytes'],0,64*1024*1024) and integer(row['totalBytes'],-1,64*1024*1024) and integer(row['status'],0,599) and integer(row['networkError'],0,999) and integer(row['replyBytes'],0,16384) and (row['responseId']=='' or nonce(row['responseId'])))
            need(type(row['boundary']) is str and (re.fullmatch(r'[A-Za-z0-9_\-.+]{1,128}',row['boundary']) is not None if row['multipart'] else row['boundary']==''))
            sha(row['bodySha256']);sha(row['replySha256']);need(type(row['replyBase64']) is str)
            try:raw=base64.b64decode(row['replyBase64'],validate=True)
            except (ValueError,TypeError):need(False)
            need(len(raw)==row['replyBytes'] and hashlib.sha256(raw).hexdigest()==row['replySha256'])
            if not row['finished']:need(row['status']==row['networkError']==row['replyBytes']==0 and row['responseId']=='')
    need(ids==sorted(set(ids)))
    before=0;begun=set()
    allowed={'begin','file-open','file-unavailable','file-destroyed','multipart-created','multipart-destroyed','request-created','upload-progress','reply-finished','reply-destroyed','cancel-requested','terminal','uploader-destroyed'}
    for index,row in enumerate(value['events'],1):
        exact(row,{'sequence','jobId','kind','capturedEpochMs'})
        need(type(row['sequence']) is int and row['sequence']==index and row['jobId'] in ids and row['kind'] in allowed and integer(row['capturedEpochMs'],max(1,before),value['capturedEpochMs']))
        if row['kind']=='begin':need(row['jobId'] not in begun);begun.add(row['jobId'])
        else:need(row['jobId'] in begun)
        before=row['capturedEpochMs']
    need(begun==set(ids));return value


def validate(value,request,pid,epoch):
    command(request);exact(value,{'schemaVersion','requestId','runId','instance','sequence','processId','requestedEpochMs','capturedEpochMs','source'})
    need(type(value['schemaVersion']) is int and value['schemaVersion']==1 and value['requestId']==request['commandId'] and value['runId']==request['runId'] and nonce(value['instance']) and integer(value['sequence'],1,9007199254740991) and integer(value['processId'],1) and value['processId']==pid and integer(value['requestedEpochMs'],1) and integer(value['capturedEpochMs'],value['requestedEpochMs']) and value['capturedEpochMs']-value['requestedEpochMs']<1500)
    fresh(value['capturedEpochMs'],epoch);source(value['source'],value['capturedEpochMs']);need(value['source']['capturedEpochMs']>=value['requestedEpochMs']);return value


def continuity(before,after):
    need(all(after[k]==before[k] for k in ('runId','instance','processId')) and after['sequence']>before['sequence'] and after['capturedEpochMs']>=before['capturedEpochMs'])
    a,b=before['source'],after['source'];need(b['instance']==a['instance'] and b['sequence']>=a['sequence'] and b['events'][:len(a['events'])]==a['events'])
    jobs={job['id']:job for job in b['jobs']}
    for old in a['jobs']:
        need(old['id'] in jobs);new=jobs[old['id']]
        need(all(new[k]==old[k] for k in ('id','path','href')) and len(new['requests'])>=len(old['requests']))
        if old['file']:
            need(all(new['file'][k]==old['file'][k] for k in ('bytes','sha256','device','inode')) and new['file']['readBytes']>=old['file']['readBytes'])
        for key in ('uploaderAlive','fileAlive','multipartAlive'):
            if not old[key] and any(event['jobId']==old['id'] and event['kind']=={'uploaderAlive':'uploader-destroyed','fileAlive':'file-destroyed','multipartAlive':'multipart-destroyed'}[key] for event in a['events']):need(not new[key])
        if old['terminal']:need(new['terminal']==old['terminal'])
        if old['cancelRequested']:need(new['cancelRequested'])
        for one,two in zip(old['requests'],new['requests']):
            need(all(two[k]==one[k] for k in ('id','stage','url','operation','authRequired','authorizationPresent','multipart','boundary','bodyBytes','bodySha256','dispatchCurrent')))
            for key in ('finished','destroyed'):
                if one[key]:need(two[key])
            if one['finished']:need(all(two[k]==one[k] for k in ('status','networkError','responseId','replyBytes','replySha256','replyBase64')))


def require_retired(value):
    source(value,value['capturedEpochMs'])
    for job in value['jobs']:
        need(job['terminal'] and not any(job[k] for k in ('uploaderAlive','fileAlive','multipartAlive')) and all(row['finished'] and row['destroyed'] for row in job['requests']))
    return value


class PhoneSnapshotUploadSource:
    def __init__(self,send,read,clock_ms,guard,pid,*,monotonic=time.monotonic,sleep=time.sleep):
        need(all(callable(fn) for fn in (send,read,clock_ms,guard,monotonic,sleep)) and integer(pid,1))
        self.send,self.original,self.clock_ms,self.guard,self.pid=send,read,clock_ms,guard,pid
        self.monotonic,self.sleep,self.last=monotonic,sleep,None

    def read(self,run):
        try:
            request=command(dict(schemaVersion=1,commandId=uuid.uuid4().hex,action='phone-snapshot-upload-observe',runId=run))
            need(self.guard() is not False);started=previous=self.monotonic();requested=self.clock_ms();self.send(request)
            for attempt in range(51):
                need(self.guard() is not False);raw=self.original();need(type(raw) is str and len(raw.encode())<=262144)
                try:value=decode(raw) if raw else None
                except json.JSONDecodeError:value=None
                need(self.guard() is not False);now=self.monotonic();need(number(now,previous,1e15) and now-started<5);previous=now
                if type(value) is dict and value.get('requestId')==request['commandId']:
                    validate(value,request,self.pid,self.clock_ms());need(value['requestedEpochMs']>=requested)
                    if self.last is not None:continuity(self.last,value)
                    need(self.guard() is not False);fresh(value['capturedEpochMs'],self.clock_ms());need(self.monotonic()-started<5)
                    self.last=deepcopy(value);return deepcopy(value)
                if attempt<50:self.sleep(.1)
        except Exception:raise NativeUIError('Original Snapshot upload observation is unavailable or invalid') from None
        raise NativeUIError('Original Snapshot upload observation did not produce this request')
