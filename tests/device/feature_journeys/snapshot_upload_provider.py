"""Opt-in authenticated Snapshot backend on the existing trusted listener.

Rows arise only from actual native protocol requests. A reader can observe
original bodies and lifecycle facts; neither an input ACK nor Close deletes a
story. Credentials and request headers are never retained in observations.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from copy import deepcopy
import base64
import hashlib
from io import BytesIO
import json
import math
import os
import re
import secrets
import threading
import time
from urllib.parse import urlsplit
from feature_journeys.avatar_social_http import AccountAuthenticator
from feature_journeys.contract import identifier
from feature_journeys.snapshot_upload_protocol import multipart,story

UPLOAD='/api/v1/snapshots'
STORIES='/api/v1/user_stories'
BODY=UPLOAD+'/'


def encode(value):return json.dumps(value,separators=(',',':'),sort_keys=True,allow_nan=False).encode('utf-8')
def sha(raw):return hashlib.sha256(raw).hexdigest()


class SnapshotUploadProvider:
    def __init__(self,authenticate,*,epoch_ms=lambda:int(time.time()*1000),monotonic=time.monotonic):
        if type(authenticate) is not AccountAuthenticator or not callable(epoch_ms) or not callable(monotonic):
            raise ValueError('Actual original Snapshot OAuth authority and clocks are required')
        self.authenticate,self.epoch_ms,self.monotonic=authenticate,epoch_ms,monotonic
        self.lock=threading.RLock();self.instance=secrets.token_hex(16);self.runs={};self.retired=set();self.last_epoch=0;self.last_mono=0.;self.sequence=0;self.story_id=0
    def clock(self):
        epoch,mono=self.epoch_ms(),self.monotonic()
        if type(epoch) is not int or epoch<max(1,self.last_epoch) or type(mono) not in (int,float) or not math.isfinite(mono) or not self.last_mono<=mono<1e15:
            raise ValueError('Snapshot backend clocks are unavailable')
        self.last_epoch,self.last_mono=epoch,mono;return dict(epochMs=epoch,monotonicMs=mono*1000)
    def provision(self,run,account_run=None):
        identifier(run);account_run=run if account_run is None else identifier(account_run)
        with self.lock:
            if run in self.runs or run in self.retired or len(self.runs)>=16 or len(self.retired)>=256:
                raise ValueError('Snapshot backend scope is reused or full')
            # The already provisioned actual account is the authority. This
            # provider does not mint a login, token, profile or client verdict.
            username=self.authenticate.provider.credentials(account_run,'owned')['username']
            if username!='e2e-'+account_run or any(row['principal']==username for row in self.runs.values()):raise ValueError('Original Snapshot principal is unavailable or already bound')
            self.runs[run]=dict(principal=username,accountRun=account_run,ticket=None,tickets=set(),created=self.clock(),uploads={},stories={},requests={},history=[],queries={},fenced=False,fenceClock=None)
    def activate(self,run,ticket):
        identifier(run);identifier(ticket)
        with self.lock:
            row=self.runs[run]
            if row['fenced'] or ticket in row['tickets'] or len(row['tickets'])>=256:raise ValueError('Snapshot backend challenge is retired')
            self.clock();row['ticket']=ticket;row['tickets'].add(ticket)
    def event(self,run,kind,**detail):
        row=self.runs[run]
        if len(row['history'])>=2048:raise ValueError('Snapshot backend history is full')
        self.sequence+=1;value=dict(sequence=self.sequence,clock=self.clock(),ticket=row['ticket'],kind=kind,detail=detail);row['history'].append(value);return value
    def resolve(self,authorization):
        if type(authorization) is not str or len(authorization)>512:return None
        principal=self.authenticate(authorization)
        matches=[run for run,row in self.runs.items() if row['principal']==principal and not row['fenced']]
        if len(matches)!=1:return None
        return matches[0]
    @contextmanager
    def response(self,method,path,content_type,raw,authorization,origin):
        """Own an actual request through its observed original socket write.

        The listener supplies the measured HTTPS authority, invokes ``written``
        only after its complete write, and lets exceptions cross this context.
        Missing or failed writes are distinct retained facts.
        """
        with self.lock:
            run=self.resolve(authorization)
            if run is None:
                yield 401,b'{"status":"fail","error":"unauthorized"}',None,None;return
            if type(origin) is not str or not 0<len(origin)<=512 or not origin.isascii() or any(ord(c)<=32 or ord(c)==127 for c in origin):
                raise ValueError('Invalid original Snapshot request authority')
            row=self.runs[run];url=urlsplit(origin)
            if row['ticket'] is None or url.scheme!='https' or not url.hostname or url.username or url.password or url.path or url.query or url.fragment:
                raise ValueError('Original Snapshot request authority is unavailable')
            if len(row['requests'])>=256 or any(not request['left'] for request in row['requests'].values()):
                raise ValueError('Snapshot backend request responsibility is pending')
            response_id=secrets.token_hex(16);request=dict(instance=response_id,method=method,path=path,bodyBytes=len(raw),bodySha256=sha(raw),ticket=row['ticket'],
                entered=self.clock(),prepared=None,written=False,writeFailed=False,left=None,status=None,responseBytes=None,responseSha256=None)
            row['requests'][response_id]=request;self.event(run,'request-entered',request=response_id,method=method,path=path,bodyBytes=len(raw),bodySha256=sha(raw))
            try:
                status,body=self.handle(run,response_id,method,path,content_type,raw,origin)
                serialized=body if type(body) is bytes else encode(body)
                request.update(prepared=self.clock(),status=status,responseBytes=len(serialized),responseSha256=sha(serialized))
                self.event(run,'response-prepared',request=response_id,status=status,bytes=len(serialized),sha256=sha(serialized))
                def written(actual):
                    with self.lock:
                        if request['written'] or request['writeFailed'] or request['left'] is not None or actual!=dict(status=status,responseId=response_id,bytes=len(serialized),sha256=sha(serialized)):
                            raise ValueError('Original Snapshot response write differs')
                        request['written']=True;self.event(run,'response-written',request=response_id)
                yield status,serialized,response_id,written
            except BaseException:
                request['writeFailed']=True;self.event(run,'request-failed',request=response_id);raise
            finally:
                request['left']=self.clock();self.event(run,'request-left',request=response_id)
    def handle(self,run,request,method,path,content_type,raw,origin):
        row=self.runs[run]
        if method=='POST' and path==UPLOAD:
            if len(row['uploads'])>=16:raise ValueError('Snapshot backend upload limit reached')
            metadata,image=multipart(content_type,raw)
            if not metadata['filename'].startswith('parity-'+run[:16]+'-'):return 403,dict(status='fail',error='foreign-file')
            identity=secrets.token_hex(16);image_url=origin+BODY+identity+'/image'
            result=dict(id=identity,thumbnail_url=image_url,image_url=image_url,original_image_file_name=metadata['filename'])
            row['uploads'][identity]=dict(instance=identity,file=metadata,body=image,request=request,reply=result,retired=None)
            self.event(run,'upload-stored',upload=identity,request=request,file=metadata)
            return 200,dict(status='success',data=result)
        if method=='POST' and path==STORIES:
            if content_type.split(';')[0].strip()!='application/json':raise ValueError('Original Snapshot story requires JSON')
            original,details=story(raw);upload=row['uploads'].get(details['snapshot_id'])
            if upload is None or upload['retired'] is not None or any(story['upload']==upload['instance'] and story['deleted'] is None for story in row['stories'].values()):
                return 409,dict(status='fail',error='unknown-or-duplicate-snapshot')
            reply=upload['reply']
            expected=dict(image_url=reply['image_url'],snapshot_id=reply['id'],original_image_file_name=reply['original_image_file_name'])
            if details!=expected:return 409,dict(status='fail',error='foreign-snapshot-details')
            if original['thumbnail_url']!=reply['thumbnail_url']:return 409,dict(status='fail',error='foreign-thumbnail')
            self.story_id+=1;identifier_value=str(self.story_id);value={**original,'id':self.story_id,'details':details}
            row['stories'][identifier_value]=dict(id=identifier_value,upload=upload['instance'],request=request,original=value,deleted=None,retired=None)
            self.event(run,'story-stored',story=identifier_value,upload=upload['instance'],request=request)
            return 200,dict(status='success',user_story=value)
        match=re.fullmatch(re.escape(STORIES)+r'/([1-9][0-9]{0,9})',path)
        if match and method in ('GET','DELETE') and raw==b'':
            value=row['stories'].get(match[1])
            if value is None or value['deleted'] is not None or value['retired'] is not None:return 404,dict(status='fail',error='not-found')
            if method=='GET':return 200,dict(status='success',user_story=value['original'])
            value['deleted']=self.clock();self.event(run,'story-deleted',story=value['id'],request=request)
            return 200,dict(status='success')
        match=re.fullmatch(re.escape(BODY)+r'([0-9a-f]{32})/image',path)
        if match and method=='GET' and raw==b'':
            value=row['uploads'].get(match[1])
            if value is not None and value['retired'] is None:return 200,value['body']
            return 404,dict(status='fail',error='not-found')
        return 404,dict(status='fail',error='not-found')
    def snapshot(self,run,nonce):
        identifier(run);identifier(nonce)
        with self.lock:
            row=self.runs[run]
            if nonce in row['queries']:
                old=row['queries'][nonce]
                if old['kind']!='source':raise ValueError('Snapshot original query kind differs')
                return deepcopy(old['packet'])
            if len(row['queries'])>=32:raise ValueError('Snapshot backend original query limit reached')
            self.sequence+=1
            value=dict(snapshotUploadBackendVersion=1,instance=self.instance,sequence=self.sequence,runId=run,requestId=nonce,processId=os.getpid(),clockDomain='snapshot-backend-host',clock=self.clock(),
                ticket=row['ticket'],created=row['created'],fenced=row['fenced'],fenceClock=row['fenceClock'],accountProvider=self.authenticate.provider.instance,accountRun=row['accountRun'],
                principalSha256=sha(row['principal'].encode()),uploads=[{key:deepcopy(value) for key,value in upload.items() if key!='body'} for upload in row['uploads'].values()],
                stories=deepcopy(list(row['stories'].values())),requests=deepcopy(list(row['requests'].values())),history=deepcopy(row['history']),
                sourceJournalRetirementRequired=True,transportProcessProofRequired=True,wholeFeatureRequired=True)
            raw=encode(value)
            if len(raw)>700*1024:raise ValueError('Original Snapshot source exceeds its bound')
            row['queries'][nonce]=dict(kind='source',packet=deepcopy(value),raw=raw);return value
    def body(self,run,nonce,identity,offset):
        identifier(run);identifier(nonce);identifier(identity)
        if type(offset) is not int or not 0<=offset<8*1024*1024 or offset%(512*1024):raise ValueError('Invalid original Snapshot body offset')
        with self.lock:
            row=self.runs[run]
            if nonce in row['queries']:
                old=row['queries'][nonce]
                if old['kind']!='body' or old['packet']['upload']!=identity or old['packet']['offset']!=offset:raise ValueError('Snapshot original body query differs')
                return deepcopy(old['packet'])
            if len(row['queries'])>=32:raise ValueError('Snapshot backend original query limit reached')
            upload=row['uploads'][identity]
            if upload['retired'] is not None or upload['body'] is None or offset>=len(upload['body']):raise ValueError('Original Snapshot backend body is unavailable')
            before=self.clock()
            with BytesIO(upload['body']) as stream:stream.seek(offset);raw=stream.read(512*1024)
            self.sequence+=1;packet=dict(snapshotUploadBackendBodyVersion=1,instance=self.instance,processId=os.getpid(),clockDomain='snapshot-backend-host',
                runId=run,requestId=nonce,ticket=row['ticket'],upload=identity,offset=offset,totalBytes=len(upload['body']),sha256=upload['file']['sha256'],partSha256=sha(raw),
                eof=offset+len(raw)==len(upload['body']),clockBefore=before,clockAfter=self.clock(),data=base64.b64encode(raw).decode(),readerClosed=stream.closed,
                sourceJournalRetirementRequired=True)
            row['queries'][nonce]=dict(kind='body',packet=deepcopy(packet),raw=encode(packet));return packet
    def original(self,run,nonce,kind,*,identity=None,offset=None):
        if kind=='source':
            if identity is not None or offset is not None:raise ValueError('Snapshot source query has no selected outcome')
            self.snapshot(run,nonce)
        elif kind=='body':self.body(run,nonce,identity,offset)
        else:raise ValueError('Unknown original Snapshot query kind')
        with self.lock:
            raw=self.runs[run]['queries'][nonce]['raw']
            return dict(snapshotUploadBackendExportVersion=1,kind=kind,runId=run,requestId=nonce,original=dict(base64=base64.b64encode(raw).decode(),bytes=len(raw),sha256=sha(raw)))
    def fence(self,run):
        identifier(run)
        with self.lock:
            row=self.runs[run]
            if row['fenced']:raise ValueError('Snapshot backend is already fenced')
            authority=self.authenticate.provider.snapshot(row['accountRun'])
            if authority['grantsEnabled'] or authority['accessTokens'] or authority['refreshTokens'] or authority['inflightRequests'] or authority['heldRequests'] or authority['armedHold']:
                raise ValueError('Actual Snapshot OAuth authority remains active')
            if any(request['left'] is None or request['prepared'] is None or not (request['written'] or request['writeFailed']) for request in row['requests'].values()):
                raise ValueError('Snapshot backend response responsibility remains uncertain')
            row['fenceClock']=self.clock();row['fenced']=True;self.event(run,'authority-fenced',accountOriginal=authority)
    def retirement_ready(self,run):
        row=self.runs[run];now=self.clock()
        if not row['fenced'] or any(now[key]-row['fenceClock'][key]<3000 for key in now) or any(request['left'] is None for request in row['requests'].values()):
            raise ValueError('Snapshot backend original quiet is incomplete')
        return row
    def retire_story(self,run,identity):
        identifier(run)
        if type(identity) is not str or not re.fullmatch('[1-9][0-9]{0,9}',identity):raise ValueError('Invalid original Snapshot story identity')
        with self.lock:
            row=self.retirement_ready(run);value=row['stories'][identity]
            if value['retired'] is not None:raise ValueError('Snapshot story was already fixture-retired')
            value['retired']=self.clock();self.event(run,'fixture-story-retired',story=identity)
    def retire_upload(self,run,identity):
        identifier(run);identifier(identity)
        with self.lock:
            row=self.retirement_ready(run);value=row['uploads'][identity]
            if value['retired'] is not None or any(story['upload']==identity and story['deleted'] is story['retired'] is None for story in row['stories'].values()):
                raise ValueError('Snapshot upload still has owned story responsibility')
            # Memory bytes are an actual owned backend resource. This does not
            # assert socket, listener, native process or SDK retirement.
            value['body']=None;value['retired']=self.clock();self.event(run,'fixture-upload-retired',upload=identity,file=value['file'])
    def assert_retired(self,run):
        identifier(run)
        with self.lock:
            row=self.retirement_ready(run)
            if any(upload['retired'] is None or upload['body'] is not None for upload in row['uploads'].values()) or any(story['deleted'] is story['retired'] is None for story in row['stories'].values()):
                raise ValueError('Snapshot backend still owns original bodies or stories')
            return True
