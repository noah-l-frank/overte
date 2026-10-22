"""Independent separate-UID DocumentsProvider originals and actual retirement.

A normal OS picker creates the file and the actual Phone output stream writes
it. DUMP-only controls arm IDs or retire an already empty original owner; they
cannot create content, supply measured identities or delete a destination.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
import re
import time
import threading
import uuid
from urllib.parse import urlsplit
from adapters.native_feature_observation import exact,fresh,integer,need,number
from adapters.normal_ui import NativeUIError
from overte_phone_snapshot_consumer import SnapshotConsumerTransport,PACKAGE,AUTHORITY,ROOTS
from overte_phone_snapshot_readbacks import nonce
from overte_phone_snapshot_documents_ui import resolution

DOCUMENTS_AUTHORITY=PACKAGE+'.documents'
MAX_BYTES=32*1024*1024
MAX_SOURCE=1024*1024


def document_id(value,run,arm):
    return type(value) is str and re.fullmatch('doc-'+re.escape(run)+'-'+re.escape(arm)+'-[0-9a-f]{32}',value) is not None


def sha(value):return type(value) is str and re.fullmatch('[0-9a-f]{64}',value) is not None


def installed(value):
    exact(value,{'package','apkSha256','uid','processId','processIdentity'})
    need(value['package']==PACKAGE and sha(value['apkSha256']) and integer(value['uid'],1) and integer(value['processId'],1)
        and type(value['processIdentity']) is str and re.fullmatch(str(value['processId'])+':[0-9]+',value['processIdentity']))
    return value


def decode(raw):
    need(type(raw) is bytes and 0<len(raw)<=MAX_SOURCE)
    def pairs(items):
        value={}
        for key,item in items:need(key not in value);value[key]=item
        return value
    return json.loads(raw.decode('utf-8'),object_pairs_hook=pairs,parse_constant=lambda _value:need(False))


def source(value,run,arm,observation,identity,epoch):
    exact(value,{'snapshotDocumentsVersion','runId','armId','observationId','instance','sequence','capturedEpochMs','processId',
        'providerUid','providerPackage','complete','root','plans','documents','fdLifetimes','retired','workersTerminated'})
    need(type(value['snapshotDocumentsVersion']) is int and value['snapshotDocumentsVersion']==1 and value['runId']==run and value['armId']==arm
        and nonce(run) and nonce(arm) and value['observationId']==observation and nonce(observation) and nonce(value['instance'])
        and integer(value['sequence'],1) and type(value['processId']) is int and value['processId']==identity['processId']
        and type(value['providerUid']) is int and value['providerUid']==identity['uid'] and value['providerPackage']==PACKAGE
        and all(type(value[key]) is bool for key in ('complete','retired','workersTerminated')))
    fresh(value['capturedEpochMs'],epoch);captured=value['capturedEpochMs']
    root=value['root'];exact(root,{'rootId','path','device','inode','present','checkedEpochMs'})
    need(root['rootId']=='root-'+run and root['path'] in {prefix+'overte-snapshot-documents-'+run for prefix in ROOTS}
        and integer(root['device']) and integer(root['inode'],1) and type(root['present']) is bool
        and root['present']==(not value['retired']) and integer(root['checkedEpochMs'],1,captured))
    need(all(type(value[key]) is list and len(value[key])<=maximum for key,maximum in (('plans',64),('documents',64),('fdLifetimes',4096))))
    plans={}
    for row in value['plans']:
        exact(row,{'documentId','createUid','createdEpochMs','displayName','mimeType','phase'})
        need(document_id(row['documentId'],run,arm) and row['documentId'] not in plans and integer(row['createUid'],1)
            and integer(row['createdEpochMs'],1,captured) and row['mimeType']=='image/png'
            and type(row['displayName']) is str and re.fullmatch('e2e-'+run+r'-[A-Za-z0-9_-]{1,160}\.png',row['displayName'])
            and row['phase'] in ('planned','created','failed'))
        plans[row['documentId']]=row
    documents={}
    for row in value['documents']:
        exact(row,{'documentId','uri','displayName','mimeType','createUid','createdEpochMs','device','inode','bytes','sha256','writerUid',
            'writeOpenedEpochMs','writeClosedEpochMs','deleteCalls','deletedEpochMs','absent','checkedEpochMs'})
        id=row['documentId'];plan=plans.get(id)
        need(plan is not None and id not in documents and plan['phase']=='created'
            and all(row[key]==plan[key] for key in ('displayName','mimeType','createUid','createdEpochMs'))
            and row['uri']=='content://'+DOCUMENTS_AUTHORITY+'/document/'+id and integer(row['device']) and integer(row['inode'],1)
            and integer(row['bytes'],0,MAX_BYTES) and integer(row['writerUid']) and integer(row['writeOpenedEpochMs'],0,captured)
            and integer(row['writeClosedEpochMs'],0,captured) and integer(row['deleteCalls'],0,1)
            and integer(row['deletedEpochMs'],0,captured) and type(row['absent']) is bool and integer(row['checkedEpochMs'],0,captured))
        if row['writerUid']==0:need(row['writeOpenedEpochMs']==row['writeClosedEpochMs']==row['bytes']==0 and row['sha256']=='')
        else:
            need(row['writeOpenedEpochMs']>=row['createdEpochMs'])
            if row['writeClosedEpochMs']:
                need(row['writeClosedEpochMs']>=row['writeOpenedEpochMs'] and row['bytes']>0 and sha(row['sha256']))
            else:need(row['bytes']==0 and row['sha256']=='')
        if row['deleteCalls']:
            need(row['deletedEpochMs']>=row['writeClosedEpochMs']>0 and row['absent'] and row['checkedEpochMs']>=row['deletedEpochMs'])
        else:need(row['deletedEpochMs']==row['checkedEpochMs']==0 and not row['absent'])
        documents[id]=row
    fds={};writers={}
    for row in value['fdLifetimes']:
        exact(row,{'id','documentId','mode','callerUid','openedEpochMs','closedEpochMs','closed','error'})
        need(nonce(row['id']) and row['id'] not in fds and row['documentId'] in documents and row['mode'] in ('r','w')
            and integer(row['callerUid'],1) and integer(row['openedEpochMs'],0,captured) and integer(row['closedEpochMs'],0,captured)
            and type(row['closed']) is bool and type(row['error']) is bool)
        if row['closed']:need(row['closedEpochMs']>0 and row['closedEpochMs']>=row['openedEpochMs'])
        else:need(row['closedEpochMs']==0 and not row['error'])
        if value['complete']:need(row['openedEpochMs']>0 and not row['error'])
        if row['mode']=='w':
            need(row['documentId'] not in writers);writers[row['documentId']]=row
            doc=documents[row['documentId']]
            if row['openedEpochMs']:
                need(doc['writerUid']==row['callerUid'] and doc['writeOpenedEpochMs']==row['openedEpochMs'])
            if row['closed'] and not row['error']:need(doc['writeClosedEpochMs']==row['closedEpochMs'])
        fds[row['id']]=row
    for id,row in documents.items():
        need(row['writerUid']==0 or id in writers)
        if row['absent']:need(all(fd['closed'] for fd in fds.values() if fd['documentId']==id))
    if value['complete']:need(set(documents)==set(plans) and all(row['phase']=='created' for row in plans.values()))
    if value['retired']:need(all(row['absent'] for row in documents.values()) and all(row['closed'] for row in fds.values()))
    if value['workersTerminated']:need(value['retired'])
    return value


def continuity(before,after):
    need(all(after[key]==before[key] for key in ('runId','armId','instance','processId','providerUid','providerPackage'))
        and after['sequence']>before['sequence'] and after['capturedEpochMs']>=before['capturedEpochMs']
        and (not before['retired'] or after['retired']) and (not before['workersTerminated'] or after['workersTerminated']))
    need(all(after['root'][key]==before['root'][key] for key in ('rootId','path','device','inode'))
        and after['root']['checkedEpochMs']>=before['root']['checkedEpochMs'])
    for key,id in (('plans','documentId'),('documents','documentId'),('fdLifetimes','id')):
        current={row[id]:row for row in after[key]};need(len(current)==len(after[key]))
        for row in before[key]:
            new=current.get(row[id]);need(new is not None)
            if key=='plans':
                need(all(new[field]==row[field] for field in ('documentId','createUid','createdEpochMs','displayName','mimeType')))
                if row['phase']!='planned':need(new['phase']==row['phase'])
            elif key=='documents':
                need(all(new[field]==row[field] for field in ('documentId','uri','displayName','mimeType','createUid','createdEpochMs','device','inode')))
                if row['writerUid']:need(new['writerUid']==row['writerUid'] and new['writeOpenedEpochMs']==row['writeOpenedEpochMs'])
                if row['writeClosedEpochMs']:need(all(new[field]==row[field] for field in ('writeClosedEpochMs','bytes','sha256')))
                need(new['deleteCalls']>=row['deleteCalls'] and (not row['absent'] or new['absent']) and new['checkedEpochMs']>=row['checkedEpochMs'])
                if row['deletedEpochMs']:need(new['deletedEpochMs']==row['deletedEpochMs'])
            else:
                need(all(new[field]==row[field] for field in ('id','documentId','mode','callerUid')))
                if row['openedEpochMs']:need(new['openedEpochMs']==row['openedEpochMs'])
                if row['closed']:need(new==row)


def join(identity,document,provider,phone_uid,documents_resolution):
    resolution(documents_resolution)
    exact(identity,{'uri','providerUid','providerPackage','ownerPackage','displayName','device','inode','storage','runId','armId',
        'providerInstance','documentId','createUid','createdEpochMs'})
    need(integer(phone_uid,1) and phone_uid!=provider['providerUid'] and identity['storage']=='documents'
        and identity['providerPackage']==identity['ownerPackage']==PACKAGE and identity['providerUid']==provider['providerUid']
        and identity['runId']==provider['runId'] and identity['armId']==provider['armId'] and identity['providerInstance']==provider['instance']
        and all(identity[key]==document[key] for key in ('documentId','uri','displayName','device','inode','createUid','createdEpochMs'))
        and document['createUid']==documents_resolution['uid'] and document['writerUid']==phone_uid
        and document['writeClosedEpochMs']>=document['writeOpenedEpochMs']>0 and document['bytes']>0 and sha(document['sha256'])
        and not document['absent'])
    return deepcopy(document)


class SnapshotDocumentsTransport(SnapshotConsumerTransport):
    def read(self,run,id):
        need(nonce(run) and nonce(id));return self._execute('content','read','--uri','content://'+AUTHORITY+'/documents-observations/'+run+'/'+id,binary=True)
    def binary(self,run,document,id):
        need(nonce(run) and nonce(id) and type(document) is str and re.fullmatch('doc-'+run+'-[0-9a-f]{32}-[0-9a-f]{32}',document))
        return self._execute('content','read','--uri','content://'+AUTHORITY+'/documents-originals/'+run+'/'+document+'/'+id,binary=True)
    def control(self,operation,run,arm=''):
        need(not self.read_only and nonce(run) and operation in ('arm','retire') and (nonce(arm) if operation=='arm' else arm==''))
        args=['content','call','--uri','content://'+AUTHORITY,'--method','documents-'+operation,'--extra','runId:s:'+run]
        if arm:args+=['--extra','armId:s:'+arm]
        before=self._installed();ack=self._execute(*args);need(self._installed()==before);return ack


class PhoneSnapshotDocuments:
    def __init__(self,transport,clock_ms,guard,run,arm,*,read_only=True,binding=None,monotonic=time.monotonic,sleep=time.sleep):
        need(nonce(run) and nonce(arm) and type(read_only) is bool and all(callable(fn) for fn in (clock_ms,guard,monotonic,sleep)))
        self.transport,self.clock_ms,self.guard,self.run,self.arm,self.read_only=transport,clock_ms,guard,run,arm,read_only
        self.monotonic,self.sleep,self.last,self.bound,self.instance,self.root,self.last_clock=monotonic,sleep,None,None,None,None,None
        self.floor=None
        self._lease_lock=threading.Lock();self._qualified=None;self._qualified_hash=None;self._qualified_started=None
        self._observation_lease=None;self._leased_key=None
        if binding is not None:
            exact(binding,{'snapshotDocumentsBindingVersion','installed','instance','runId','armId','root','floor'})
            need(type(binding['snapshotDocumentsBindingVersion']) is int and binding['snapshotDocumentsBindingVersion']==2
                and binding['runId']==run and binding['armId']==arm and nonce(binding['instance']))
            self.bound,self.instance,self.root=deepcopy(installed(binding['installed'])),binding['instance'],deepcopy(binding['root'])
            self.floor=self._historical(binding['floor'])
        need(not read_only or binding is not None)
    def binding(self):
        floor=self.last if self.last is not None else self.floor
        need(self.bound is not None and self.instance is not None and self.root is not None and floor is not None)
        return dict(snapshotDocumentsBindingVersion=2,installed=deepcopy(self.bound),instance=self.instance,
            runId=self.run,armId=self.arm,root=deepcopy(self.root),floor=deepcopy(floor))
    def _historical(self,row):
        try:
            value=deepcopy(row)
            source(value,self.run,self.arm,value['observationId'],installed(self.bound),value['capturedEpochMs'])
            need(value['instance']==self.instance
                and {key:value['root'][key] for key in ('rootId','path','device','inode')}==self.root)
            return value
        except Exception:raise NativeUIError('Original Snapshot Documents ownership floor is invalid') from None
    def restore_history(self,original_rows):
        try:
            need(self.last is None and self.floor is not None and type(original_rows) is list and 0<len(original_rows)<=512)
            previous=None;found_floor=False
            for row in original_rows:
                value=self._historical(row)
                if previous is not None:continuity(previous,value)
                found_floor=found_floor or value==self.floor
                previous=value
            need(found_floor);self.last=deepcopy(previous)
        except Exception:raise NativeUIError('Original Snapshot Documents history cannot be restored') from None
    def _identity(self):
        need(self.guard() is not False);value=self.transport.identity()
        installed(value)
        if self.bound is None:self.bound=deepcopy(value)
        else:need(self.bound==value)
        return value
    def observe(self):
        # A new acquisition attempt invalidates any earlier transaction token,
        # including attempts which later fail qualification. Historical floors
        # never populate the private live-observation slot.
        with self._lease_lock:self._observation_lease=None;self._qualified=None
        try:
            need(self.guard() is not False);start=previous=self.monotonic();requested=self.clock_ms()
            need(number(start,0,1e15) and (self.last_clock is None or start>=self.last_clock))
            identity=self._identity()
            for attempt in range(51):
                id=uuid.uuid4().hex;value=source(decode(self.transport.read(self.run,id)),self.run,self.arm,id,identity,self.clock_ms())
                need(value['capturedEpochMs']>=requested and self._identity()==identity)
                if self.instance is None:self.instance=value['instance']
                else:need(value['instance']==self.instance)
                root={key:value['root'][key] for key in ('rootId','path','device','inode')}
                if self.root is None:self.root=deepcopy(root)
                else:need(root==self.root)
                original=self.last if self.last is not None else self.floor
                if original is not None:continuity(original,value)
                need(self.guard() is not False);now=self.monotonic();need(number(now,previous,1e15) and now-start<5);previous=now
                self.last=deepcopy(value)
                if value['complete']:
                    fresh(value['capturedEpochMs'],self.clock_ms());need(self.guard() is not False)
                    final=self.monotonic();need(number(final,now,1e15) and final-start<5)
                    self.last_clock=final
                    with self._lease_lock:
                        self._qualified=deepcopy(value);self._qualified_hash=self._observation_hash(value);self._qualified_started=start
                    return deepcopy(value)
                need(attempt<50);self.sleep(.1)
        except Exception:raise NativeUIError('Original Snapshot Documents provider is unavailable, foreign or incomplete') from None
        raise NativeUIError('Original Snapshot Documents provider did not complete')
    def control(self,operation):
        with self._lease_lock:self._observation_lease=None;self._qualified=None
        try:
            need(not self.read_only and operation in ('arm','retire') and self.guard() is not False)
            self.transport.control(operation,self.run,self.arm if operation=='arm' else '')
            need(self.guard() is not False)
        except Exception:raise NativeUIError('Snapshot Documents control is unavailable or unauthorized') from None
    @staticmethod
    def _observation_hash(value):
        return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).digest()

    def acquisition_lease(self):
        """Mint an opaque, single-use handle for this reader's live original.

        No caller DTO, persisted floor or expected value can authorize a body
        read. All current guard/identity/freshness checks happen at consumption,
        immediately before the ordinary binary acquisition.
        """
        try:
            with self._lease_lock:
                value=self._qualified;need(value is not None and self.last==value
                    and self._observation_hash(value)==self._qualified_hash)
                key=(value['instance'],value['sequence'],value['observationId'])
                need(self._observation_lease is None and key!=self._leased_key)
                token=object();self._observation_lease=(token,deepcopy(value),self._qualified_hash,
                    self._qualified_started,deepcopy(self.bound));self._leased_key=key
                return token
        except Exception:raise NativeUIError('Live original Snapshot document acquisition lease is unavailable') from None

    def _consume_acquisition_lease(self,token):
        with self._lease_lock:
            held=self._observation_lease;self._observation_lease=None
            need(held is not None and held[0] is token)
            _token,before,digest,started,identity=held
            need(self._qualified==before and self.last==before and self._observation_hash(before)==digest
                and self._qualified_hash==digest and self.bound==identity)
        # Consumption is irreversible even if a later guard or identity check
        # fails. A retry needs a genuinely new original provider observation.
        need(self.guard() is not False)
        now=self.monotonic();need(number(now,started,1e15) and number(now,self.last_clock,1e15) and now-started<=1.5)
        epoch=self.clock_ms();source(before,self.run,self.arm,before['observationId'],installed(identity),epoch)
        need(self._identity()==identity)
        fresh(before['capturedEpochMs'],self.clock_ms())
        need(self.guard() is not False);final=self.monotonic()
        need(number(final,now,1e15) and final-started<=1.5)
        with self._lease_lock:
            need(self._qualified==before and self.last==before and self.bound==identity
                and self._observation_hash(self._qualified)==digest and self._qualified_hash==digest)
        return before

    def acquire(self,document_id,native_identity,capture,phone_uid,documents_resolution,*,observation_lease=None):
        try:
            start=self.monotonic()
            before=self.observe() if observation_lease is None else self._consume_acquisition_lease(observation_lease)
            need(not before['retired'])
            matches=[row for row in before['documents'] if row['documentId']==document_id];need(len(matches)==1)
            document=join(native_identity,matches[0],before,phone_uid,documents_resolution)
            need(all(fd['closed'] for fd in before['fdLifetimes'] if fd['documentId']==document_id))
            raw=self.transport.binary(self.run,document_id,uuid.uuid4().hex)
            need(type(raw) is bytes and 0<len(raw)<=MAX_BYTES and len(raw)==document['bytes'] and hashlib.sha256(raw).hexdigest()==document['sha256']
                and type(capture) is dict and capture.get('bytes')==len(raw) and capture.get('sha256')==document['sha256'])
            from snapshot_observation import inspect_snapshot
            inspect_snapshot(raw,mode='still',file_format='png')
            after=self.observe();need(not after['retired'] and next(row for row in after['documents'] if row['documentId']==document_id)==document)
            need(self.guard() is not False);now=self.monotonic();need(number(now,start,1e15) and now-start<5)
            return dict(source='snapshot-document-original',documentId=document_id,uri=document['uri'],bytes=len(raw),sha256=document['sha256'],
                capturedEpochMs=document['writeClosedEpochMs'],acquiredEpochMs=after['capturedEpochMs']),raw
        except Exception:raise NativeUIError('Original Snapshot document bytes or independent writer join is invalid') from None
    def require_retired(self):
        start=self.monotonic()
        value=self.observe();need(value['retired'] and value['workersTerminated'] and not value['root']['present']
            and all(row['absent'] for row in value['documents']) and all(row['closed'] for row in value['fdLifetimes']))
        fresh(value['root']['checkedEpochMs'],self.clock_ms());need(self.guard() is not False)
        now=self.monotonic();need(number(now,self.last_clock,1e15) and now-start<5)
        self.last_clock=now;return value
