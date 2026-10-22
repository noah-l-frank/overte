"""Owned Snapshot HTTPS endpoints and private original multipart wire receipts.

Only actual requests create uploads/stories. Fault controls choose transport
inputs; they never publish observations or manufacture a completed upload.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from copy import deepcopy
import base64
from email.parser import BytesParser
from email.policy import HTTP
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import stat
import time
from urllib.parse import parse_qsl,urlsplit
from adapters.normal_feature_state import PrivateFeatureState
from .account_provider import AccountProvider
from .contract import exact,identifier,json_document

SNAPSHOTS='/api/v1/snapshots'
STORIES='/api/v1/user_stories'
MAX_BODY=32*1024*1024


def digest(raw):return hashlib.sha256(raw).hexdigest()


def multipart(content_type,raw):
    if type(content_type) is not str or len(content_type)>256 or '\r' in content_type or '\n' in content_type or type(raw) is not bytes or not 0<len(raw)<=MAX_BODY:
        raise ValueError('Bounded original multipart bytes are required')
    message=BytesParser(policy=HTTP).parsebytes(('Content-Type: '+content_type+'\r\nMIME-Version: 1.0\r\n\r\n').encode('ascii')+raw)
    if message.defects or message.preamble not in (None,'') or message.epilogue not in (None,'') or message.get_content_type()!='multipart/form-data' or not message.is_multipart():raise ValueError('Invalid snapshot multipart')
    boundary=message.get_boundary()
    if type(boundary) is not str or re.fullmatch(r"[A-Za-z0-9'()+_,./:=?\-]{1,70}",boundary) is None:raise ValueError('Invalid multipart boundary')
    parts=list(message.iter_parts())
    if len(parts)!=1:raise ValueError('Exactly one original image part is required')
    part=parts[0]
    if part.defects or part.is_multipart() or len(part.get_all('Content-Disposition',[]))!=1 or len(part.get_all('Content-Type',[]))!=1 or part.get_all('Content-Transfer-Encoding',[]):raise ValueError('Invalid snapshot part headers')
    filename=part.get_filename()
    if part.get_content_disposition()!='form-data' or part.get_param('name',header='content-disposition')!='image' or type(filename) is not str or not 1<=len(filename)<=255 or re.search(r'[/\\\x00-\x1f\x7f"]',filename):raise ValueError('Invalid original image filename')
    mime=part.get_content_type();payload=part.get_payload(decode=True)
    if mime not in ('image/png','image/jpeg','image/webp','image/gif') or type(payload) is not bytes or not payload:raise ValueError('Invalid original image body')
    # The shared parser validates original encoded pixels, rather than a MIME
    # label or target-provided width/format claim.
    from snapshot_observation import inspect_snapshot
    kind={'image/png':'png','image/jpeg':'jpg','image/webp':'webp','image/gif':'gif'}[mime]
    try:inspect_snapshot(payload,mode='animated' if kind=='gif' else 'still',file_format=kind)
    except (ValueError,OSError):raise ValueError('Original snapshot image cannot be decoded') from None
    return dict(filename=filename,mime=mime,bytes=len(payload),sha256=digest(payload)),payload


class SnapshotUploadService:
    VERSION=1
    def __init__(self,accounts,domain_id,root,origin):
        if not isinstance(accounts,AccountProvider):raise ValueError('Snapshot service requires its original account provider')
        import uuid
        if str(uuid.UUID(domain_id))!=domain_id or uuid.UUID(domain_id).int==0:raise ValueError('An original domain UUID is required')
        url=urlsplit(origin)
        if url.scheme!='https' or not url.hostname or url.username or url.password or url.query or url.fragment or url.path not in ('','/') or url.port is None or origin!=f'https://{url.netloc}':raise ValueError('One exact prepared HTTPS origin is required')
        self.root=Path(root);PrivateFeatureState(self.root/'snapshot-boundary.json')._parent()
        if not self.root.is_absolute() or self.root.resolve()!=self.root:raise ValueError('Original private snapshot root is required')
        if any(self.root.glob('snapshot-*')):raise ValueError('Existing Snapshot originals require their original live owner')
        self.accounts,self.domain_id,self.origin=accounts,domain_id,origin
        self.instance=secrets.token_hex(16);self.runs={};self.retired={};self.sequence=0;self.authorization_owners={}

    def has_run(self,run):return run in self.runs or run in self.retired

    def provision(self,run):
        identifier(run)
        with self.accounts.changed:
            if self.runs or self.has_run(run) or len(self.retired)>=32:raise ValueError('One isolated Snapshot upload scope is required')
            self.accounts.provision(run)
            self.runs[run]=dict(active=True,ticket=None,activations=[],requests=[],uploads={},stories={},inflight=0,ingress=0,failedResponses=0,foreignRequests=0,lateRequests=0,domainOpen=True,fault='normal',held=False,release=False)

    def credentials(self,run):
        with self.accounts.changed:return self.accounts.credentials(identifier(run),'owned')

    def activate(self,run,ticket,verb):
        with self.accounts.changed:
            row=self.runs[identifier(run)];identifier(ticket)
            if not row['active'] or len(row['activations'])>=256:raise ValueError('Snapshot upload phase is unavailable')
            row['ticket']=ticket;row['activations'].append(dict(ticket=ticket,verb=verb,capturedEpochMs=self.accounts.now()))
            self.accounts.activate(run,ticket)
            if verb=='upload-fail':row['fault']='offline'
            elif verb=='upload':row['fault']='normal'

    def _owner(self,authorization):
        if type(authorization) is not str or len(authorization)>512 or not authorization.startswith('Bearer '):return None,False
        token=self.accounts.access.get(authorization[7:]);known=self.authorization_owners.get(digest(authorization.encode()))
        if token is not None and self.has_run(token['run']):
            run=token['run'];self.authorization_owners[digest(authorization.encode())]=run
            account=self.accounts.runs.get(run)
            return run,bool(account and account['active'] and token['expires']>self.accounts.now())
        return known,False

    @contextmanager
    def ingress(self,authorization):
        """An actual request being read cannot disappear behind body parsing."""
        row=None
        with self.accounts.changed:
            run,_accepted=self._owner(authorization)
            if run is None and len(self.runs)==1:run=next(iter(self.runs))
            if run is not None:
                row=self.runs.get(run) or self.retired[run]
                if not row['active']:row['lateRequests']+=1
                if row['ingress']>=4:raise ValueError('Snapshot ingress is full')
                row['ingress']+=1
        try:yield
        except BaseException:
            if row is not None:
                with self.accounts.changed:row['failedResponses']+=1
            raise
        finally:
            if row is not None:
                with self.accounts.changed:row['ingress']-=1;self.accounts.changed.notify_all()

    def _write(self,name,raw):
        path=self.root/name
        owner=PrivateFeatureState(path.with_name(name+'.json'));state=dict(snapshotUploadFileVersion=1,instance=self.instance,name=name,phase='planned',file=None)
        owner.write(state,None)
        descriptor=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        with os.fdopen(descriptor,'wb') as stream:
            info=os.fstat(stream.fileno());opened=dict(state,phase='opened',file=dict(name=name,device=info.st_dev,inode=info.st_ino,bytes=0,sha256=digest(b'')))
            owner.write(opened,state)
            if stream.write(raw)!=len(raw):raise ValueError('Incomplete original upload write')
            stream.flush();os.fsync(stream.fileno());info=os.fstat(stream.fileno())
        record=dict(name=name,device=info.st_dev,inode=info.st_ino,bytes=len(raw),sha256=digest(raw))
        self.original(record);owner.write(dict(opened,phase='saved',file=record),opened);return record

    def incomplete(self,authorization,method,target,content_type,raw):
        """Retain the actual bounded received prefix; it can never be an upload."""
        if type(raw) is not bytes or len(raw)>MAX_BODY:raise ValueError('Invalid original received prefix')
        with self.accounts.changed:
            run,_accepted=self._owner(authorization)
            if run is None and len(self.runs)==1:run=next(iter(self.runs))
            if run is None:return
            row=self.runs.get(run) or self.retired[run]
            if len(row['requests'])>=128:raise ValueError('Original Snapshot request journal is full')
            self.sequence+=1;request=secrets.token_hex(16);now=self.accounts.now()
            body=self._write('snapshot-'+run+'-'+request+'.body',raw)
            row['requests'].append(dict(sequence=self.sequence,requestId=request,ticket=row['ticket'],method=method,target=target,contentType=content_type,authenticated=_accepted,startedEpochMs=now,completedEpochMs=now,body=body,image=None,response=None,state='invalid'))

    def _owned(self,record):
        store=PrivateFeatureState(self.root/(record['name']+'.json'));value=store.read()
        exact(value,{'snapshotUploadFileVersion','instance','name','phase','file'},'owned original upload journal')
        if type(value['snapshotUploadFileVersion']) is not int or value['snapshotUploadFileVersion']!=1 or value['instance']!=self.instance or value['name']!=record['name'] or value['file']!=record or value['phase'] not in ('saved','retiring','retired'):raise ValueError('Incomplete original upload ownership')
        path=self.root/record['name']
        if path.exists() or path.is_symlink():
            if value['phase']=='retired':raise ValueError('Retired original upload reappeared')
            self.original(record)
        elif value['phase']=='saved':raise ValueError('Original upload is missing')
        return store,value

    def original(self,record):
        exact(record,{'name','device','inode','bytes','sha256'},'private original upload file')
        if re.fullmatch('snapshot-[0-9a-f]{32}-[0-9a-f]{32}\\.(?:body|reply)',record['name']) is None:raise ValueError('Invalid owned upload filename')
        path=self.root/record['name']
        with os.fdopen(os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK),'rb') as stream:
            before=os.fstat(stream.fileno());current=path.lstat()
            for info in (before,current):
                if not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode)!=0o600 or info.st_nlink!=1 or info.st_uid!=os.geteuid():raise ValueError('Original upload ownership changed')
            if (before.st_dev,before.st_ino,before.st_size)!=(record['device'],record['inode'],record['bytes']) or (current.st_dev,current.st_ino)!=(before.st_dev,before.st_ino):raise ValueError('Original upload inode changed')
            raw=stream.read(MAX_BODY+1);after=os.fstat(stream.fileno());last=path.lstat()
            if (after.st_dev,after.st_ino,after.st_size)!=(before.st_dev,before.st_ino,before.st_size) or (last.st_dev,last.st_ino,last.st_size)!=(before.st_dev,before.st_ino,before.st_size):raise ValueError('Original upload changed during acquisition')
        if len(raw)!=record['bytes'] or digest(raw)!=record['sha256']:raise ValueError('Original upload bytes changed')
        return raw

    def _apply(self,row,method,path,query,content_type,raw):
        pairs=parse_qsl(query,keep_blank_values=True,strict_parsing=True,max_num_fields=8);parameters=dict(pairs)
        if len(parameters)!=len(pairs):raise ValueError('Duplicate original Snapshot query')
        if path.startswith(STORIES+'/'):
            story_id=path[len(STORIES)+1:]
            if query or re.fullmatch('[1-9][0-9]{0,14}',story_id) is None or story_id not in row['stories']:return 404,dict(status='fail',error='not-found'),None
            if method=='GET':return 200,dict(status='success',user_story=deepcopy(row['stories'][story_id])),None
            if method=='DELETE':del row['stories'][story_id];return 200,dict(status='success'),None
            return 405,dict(status='fail',error='method-not-allowed'),None
        if path==STORIES and method=='GET':
            if parameters.get('domain_id')!=self.domain_id or parameters.get('restriction')!='open,hifi' or set(parameters)!={'now','include_actions','domain_id','restriction'} or parameters['include_actions']!='concurrency':return 403,dict(status='fail',error='foreign-domain'),None
            return 200,dict(status='success',total_entries=int(row['domainOpen']),user_stories=[]),None
        if query:return 400,dict(status='fail',error='unexpected-query'),None
        if path==SNAPSHOTS and method=='POST':
            if not row['domainOpen']:return 403,dict(status='fail',error='domain-denied'),None
            image,_payload=multipart(content_type,raw);snapshot=secrets.token_hex(16)
            row['uploads'][snapshot]=image
            url=self.image_url(snapshot,image)
            return 200,dict(status='success',data=dict(id=snapshot,thumbnail_url=url,image_url=url,original_image_file_name=image['filename'])),image
        if path==STORIES and method=='POST':
            if content_type.split(';')[0].strip().lower()!='application/json' or len(raw)>16384:raise ValueError('Invalid original story body')
            body=json_document(raw);exact(body,{'user_story'},'original story');story=body['user_story']
            exact(story,{'details','thumbnail_url','place_name','path','action','audience'},'original story fields')
            details=json_document(story['details'].encode()) if type(story['details']) is str else None
            exact(details,{'image_url','snapshot_id','original_image_file_name'}|({'shareable_url'} if 'shareable_url' in details else set()),'original story details')
            image=row['uploads'].get(details['snapshot_id']);url=self.image_url(details['snapshot_id'],image) if image is not None else None
            if image is None or story['action']!='snapshot' or story['audience']!='for_url' or story['thumbnail_url']!=url or details['image_url']!=url or details['original_image_file_name']!=image['filename'] or not row['domainOpen']:return 403,dict(status='fail',error='foreign-upload'),None
            if any(type(story[k]) is not str or len(story[k])>2048 for k in ('place_name','path')):raise ValueError('Invalid original story location')
            # snapshot.js applies parseInt before its ordinary DELETE path.
            # The real API's integer identity must therefore stay numeric.
            story_id=100000+self.sequence;result=deepcopy(story);result.update(id=story_id,details=details);row['stories'][str(story_id)]=result
            return 200,dict(status='success',user_story=result),image
        return 404,dict(status='fail',error='not-found'),None

    def image_url(self,snapshot,image):
        # snapshot.js distinguishes GIF from still using the actual image URL.
        suffix={'image/png':'.png','image/jpeg':'.jpg','image/gif':'.gif','image/webp':'.webp'}[image['mime']]
        return self.origin+'/snapshot-media/'+snapshot+suffix

    @contextmanager
    def response(self,authorization,method,target,content_type,raw):
        parsed=urlsplit(target)
        if parsed.scheme or parsed.netloc or parsed.fragment or len(target)>4096 or re.search(r'[\x00-\x20\x7f]',target) or type(raw) is not bytes or len(raw)>MAX_BODY:raise ValueError('Original bounded Snapshot request is required')
        if parsed.path not in (SNAPSHOTS,STORIES) and not parsed.path.startswith(STORIES+'/'):raise ValueError('Unknown original Snapshot route')
        with self.accounts.changed:
            run,accepted=self._owner(authorization)
            public_domain=(method=='GET' and parsed.path==STORIES and bool(parsed.query) and not authorization and len(self.runs)==1)
            if public_domain:run=next(iter(self.runs));accepted=True
            if run is None:
                if len(self.runs)==1:self.runs[next(iter(self.runs))]['foreignRequests']+=1
                yield (401,dict(status='fail',error='unauthorized'),None,None);return
            row=self.runs.get(run) or self.retired[run]
            if not row['active']:
                row['lateRequests']+=1;yield (410,dict(status='fail',error='retired'),None,None);return
            if not accepted:
                row['foreignRequests']+=1;yield (401,dict(status='fail',error='unauthorized'),None,None);return
            if row['activations'] and row['activations'][-1]['verb']=='cleanup' and method=='POST':
                row['lateRequests']+=1;yield (410,dict(status='fail',error='retired-input'),None,None);return
            if row['ticket'] is None or row['inflight']>=4 or len(row['requests'])+row['inflight']>=128:raise ValueError('Snapshot request source is unavailable')
            self.sequence+=1;request=secrets.token_hex(16);started=self.accounts.now();ticket=row['ticket'];row['inflight']+=1
            body=self._write('snapshot-'+run+'-'+request+'.body',raw)
            record=dict(sequence=self.sequence,requestId=request,ticket=ticket,method=method,target=target,contentType=content_type,authenticated=not public_domain,startedEpochMs=started,completedEpochMs=0,body=body,image=None,response=None,state='receiving')
            row['requests'].append(record)
            fault=(row['fault'] if row['fault']!='story-404' else 'normal') if parsed.path==SNAPSHOTS else ('404' if row['fault']=='story-404' else 'normal')
            if fault=='hold':
                row['held']=True;row['release']=False;deadline=time.monotonic()+5
                self.accounts.changed.notify_all()
                while not row['release'] and row['active'] and time.monotonic()<deadline:self.accounts.changed.wait(.05)
                row['held']=False;fault='normal' if row['release'] and row['active'] else 'offline'
            try:
                if fault=='offline':status,value,image=0,None,None
                elif fault in ('404','503'):status,value,image=int(fault),dict(status='fail',error='controlled-fault'),None
                else:status,value,image=self._apply(row,method,parsed.path,parsed.query,content_type,raw)
                record['image']=image
                response_id=secrets.token_hex(16) if status else None
                encoded=json.dumps(value).encode() if status else b''
                reply=self._write('snapshot-'+run+'-'+request+'.reply',encoded)
            except BaseException:
                row['inflight']-=1;row['failedResponses']+=1;record['state']='invalid';raise
        completed=False
        def observed(wire):
            nonlocal completed
            with self.accounts.changed:
                exact(wire,{'status','responseId','bytes','sha256'},'original snapshot response write')
                if completed or wire!=dict(status=status,responseId=response_id,bytes=len(encoded),sha256=digest(encoded)):raise ValueError('Original Snapshot response write changed')
                record.update(response=dict(responseId=response_id,status=status,body=reply,bodyBase64=base64.b64encode(encoded).decode()),completedEpochMs=self.accounts.now(),state='written');completed=True
        try:
            yield status,encoded,response_id,observed if status else None
            if not status:
                with self.accounts.changed:record.update(response=dict(responseId=None,status=0,body=reply,bodyBase64=''),completedEpochMs=self.accounts.now(),state='connection-closed');completed=True
        finally:
            with self.accounts.changed:
                row['inflight']-=1
                if not completed:record['state']='write-failed';row['failedResponses']+=1
                self.accounts.changed.notify_all()

    def snapshot(self,run,nonce):
        identifier(run);identifier(nonce)
        with self.accounts.changed:
            row=self.runs.get(run) or self.retired[run]
            for request in row['requests']:
                if request['state']!='retired':
                    self._owned(request['body'])
                    if request['response'] is not None:self._owned(request['response']['body'])
                else:
                    for item in (request['body'],request['response']['body']):
                        path=self.root/item['name']
                        if path.exists() or path.is_symlink():raise ValueError('Retired original upload reappeared')
                        if not row['active'] and (self.root/(item['name']+'.json')).exists():raise ValueError('Retired original upload journal reappeared')
            return dict(snapshotUploadServiceVersion=1,instance=self.instance,runId=run,requestId=nonce,capturedEpochMs=self.accounts.now(),domainId=self.domain_id,origin=self.origin,
                active=row['active'],ticket=row['ticket'],activations=deepcopy(row['activations']),inflight=row['inflight']+row['ingress'],held=row['held'],failedResponses=row['failedResponses'],foreignRequests=row['foreignRequests'],lateRequests=row['lateRequests'],requests=deepcopy(row['requests']),uploads=len(row['uploads']),stories=len(row['stories']))

    def control(self,run,operation):
        with self.accounts.changed:
            row=self.runs[identifier(run)]
            if operation in ('normal','offline','404','503','hold','story-404'):row['fault']=operation
            elif operation=='release':row['release']=True;self.accounts.changed.notify_all()
            elif operation in ('deny-domain','allow-domain'):row['domainOpen']=operation=='allow-domain'
            else:raise ValueError('Unknown Snapshot fixture input')

    def retire(self,run):
        identifier(run)
        with self.accounts.changed:
            row=self.runs.get(run) or self.retired[run]
            if row['inflight'] or row['ingress'] or row['held'] or row['failedResponses'] or row['foreignRequests'] or row['lateRequests']:raise ValueError('Snapshot upload retirement has unresolved original requests')
            for request in row['requests']:
                if request['state']=='retired':
                    for item in (request['body'],request['response']['body']):
                        path=self.root/item['name']
                        if path.exists() or path.is_symlink():raise ValueError('Retired original upload reappeared')
                        owner=PrivateFeatureState(self.root/(item['name']+'.json'))
                        if owner.read() is not None:
                            if not row['active']:raise ValueError('Retired original upload journal reappeared')
                            _store,owned=self._owned(item)
                            if owned['phase']!='retired':raise ValueError('Retired original upload lacks its deletion proof')
                    continue
                if request['state'] not in ('written','connection-closed') or request['response'] is None:raise ValueError('Original Snapshot request is incomplete')
                for item in (request['body'],request['response']['body']):self._owned(item)
            # Original checks precede deletion; partial deletion has explicit
            # durable file intent so a retry cannot bless missing input.
            for request in row['requests']:
                if request['state']=='retired':continue
                for item in (request['body'],request['response']['body']):
                    store,old=self._owned(item);state=dict(old,phase='retiring')
                    if old['phase']=='saved':store.write(state,old)
                    else:state=old
                    path=self.root/item['name']
                    if path.exists():self.original(item);path.unlink()
                    retired=dict(state,phase='retired');store.write(retired,state)
                request['state']='retired'
            for request in row['requests']:
                for item in (request['body'],request['response']['body']):
                    store=PrivateFeatureState(self.root/(item['name']+'.json'));owned=store.read()
                    if owned is not None:
                        self._owned(item);store.discard(owned)
            row['active']=False;row['uploads']={};row['stories']={}
            if run in self.accounts.runs:self.accounts.control(run,'cleanup');self.accounts.retire(run)
            self.retired[run]=row;self.runs.pop(run,None)
