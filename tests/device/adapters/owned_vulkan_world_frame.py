"""Durable ownership of one original Vulkan PNG, chunks and retained consumers.

The caller must retain this owner's private path until whole-run cleanup. This
component retains original evidence; it never publishes a feature verdict.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import hashlib
import os
from adapters.original_file_reads import record as record_original_read
from pathlib import Path
import re
import stat
import time
import uuid

from adapters.native_completed_frame import _validate_storage
from adapters.native_vulkan_world_frame import NativeVulkanWorldFrame,command,validate,storage,absent,original_pixels,PNG_LIMIT
from adapters.native_feature_observation import exact,fresh,integer,need,number
from adapters.native_clock_join import digest
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import pack,unpack,same
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.contract import identifier

VERSION=1
CHUNK_VERSION=1


def owns_slot(value):
    """Original proven-empty inspection required before a read or release.

    This prefix predicate does not replace full owner/receipt validation.
    An occupied, retired or unknown first inspection grants no authority.
    """
    if value is None:return False
    rows=unpack(value['transcript'])
    return bool(rows and rows[0]['command']['operation']=='inspect' and rows[0]['receipt'] is not None
        and rows[0]['receipt']['source']==dict(retired=False,present=False,callbacks=0,gpuPending=False,
            metadataBytes=0,pngBytes=0,gpuBufferBytes=0))


def chunk_summary(packet,query,pid):
    storage(packet,query,pid,packet['capturedEpochMs'])
    raw=base64.b64decode(packet['source']['data'],validate=True)
    header=deepcopy(packet);del header['source']['data']
    return dict(chunkSummaryVersion=CHUNK_VERSION,originalSha256=digest(packet),dataSha256=hashlib.sha256(raw).hexdigest(),
                dataBytes=len(raw),packet=header)


def validate_summary(value,query,pid,raw=None):
    exact(value,{'chunkSummaryVersion','originalSha256','dataSha256','dataBytes','packet'})
    need(type(value['chunkSummaryVersion']) is int and value['chunkSummaryVersion']==CHUNK_VERSION
         and integer(value['dataBytes'],1,65536))
    for key in ('originalSha256','dataSha256'):need(type(value[key]) is str and re.fullmatch('[0-9a-f]{64}',value[key]))
    packet=value['packet'];_validate_storage(packet,query,pid,packet['capturedEpochMs'],'vulkanWorldStorageVersion',
                                             ('pngBytes','gpuBufferBytes','offset'))
    source=packet['source']
    need(source['present'] and not source['retired'] and integer(source['pngBytes'],1,PNG_LIMIT)
         and integer(source['gpuBufferBytes'],0,67108864) and integer(source['offset'],0,source['pngBytes']-1)
         and source['offset']==query['offset'] and value['dataBytes']==min(65536,source['pngBytes']-source['offset']))
    if raw is not None:
        chunk=raw[source['offset']:source['offset']+value['dataBytes']]
        need(len(raw)==source['pngBytes'] and hashlib.sha256(chunk).hexdigest()==value['dataSha256'])
        original=deepcopy(packet);original['source']['data']=base64.b64encode(chunk).decode()
        need(digest(original)==value['originalSha256']);storage(original,query,pid,packet['capturedEpochMs'])
    return packet


class VulkanWorldFrameOwner:
    @classmethod
    def archive_original(cls,value,root,binding,run,role,stage,request_id,lock):
        """Read an immutable original owner copy and its actual retained PNG.

        No live metadata, SDK/native command, mutable owner or current fact is
        exposed. The owning feature keeps the exact original copy in its
        private evidence archive before retiring runtime metadata.
        """
        need(isinstance(lock,ScriptSourceLock));lock.assert_held()
        original=deepcopy(value)
        class Archive(PrivateFeatureState):
            def read(self):return deepcopy(original)
            def write(self,*_args):need(False)
            def discard(self,*_args):need(False)
        path=lock.path.with_name('graphics-world-frame-'+role+'-'+str(stage)+'-'+request_id[4:]+'.json')
        owner=cls(Archive(path),root,binding,run,role,stage,request_id,lambda *_:need(False),lambda:True,source_lock=lock)
        raw=owner.archive();need(owner.state['phase']=='released' and absent(owner.state['absence']))
        return raw

    def __init__(self,store,root,binding,run,role,stage,request_id,factory,guard,*,source_lock=None,
                 monotonic=time.monotonic,sleep=time.sleep):
        self.store,self.root,self.binding=store,Path(root),deepcopy(context(binding))
        self.run,self.role,self.stage=identifier(run),role,stage
        need(role in ('primary','actor') and type(stage) is int and stage in (0,1)
             and type(request_id) is str and request_id.startswith('ios-'))
        identifier(request_id[4:]);self.request_id=request_id;self.pid=int(binding['processIdentity']);need(self.pid>0)
        need(all(callable(fn) for fn in (factory,guard,monotonic,sleep)))
        self.factory,self.guard,self.monotonic,self.sleep=factory,guard,monotonic,sleep
        self.lock=source_lock or ScriptSourceLock(store.path.with_name('script-feature-sources.lock'))
        need(isinstance(self.lock,ScriptSourceLock) and self.lock.path==store.path.with_name('script-feature-sources.lock'))
        self.name='vulkan-world-'+run+'-'+role+'-'+str(stage)+'-'+request_id[4:]+'.png'
        PrivateFeatureState(self.root/self.name)._parent()

    def _load(self):
        self.lock.assert_held();need(self.guard() is not False)
        self.state=self.store.read();self.events=[]
        if self.state is None:return
        exact(self.state,{'vulkanWorldOwnerVersion','binding','runId','role','stage','requestId','root','name',
                          'ticket','phase','file','frame','absence','transcript'})
        need(type(self.state['vulkanWorldOwnerVersion']) is int and self.state['vulkanWorldOwnerVersion']==VERSION
             and same(self.state['binding'],self.binding) and self.state['runId']==self.run and self.state['role']==self.role
             and type(self.state['stage']) is int and self.state['stage']==self.stage and self.state['requestId']==self.request_id
             and self.state['root']==str(self.root) and self.state['name']==self.name
             and self.state['phase'] in ('planned','opened','captured','released','removed'))
        identifier(self.state['ticket']);identity=self.state['file']
        if identity is None:need(self.state['phase'] in ('planned','released','removed'))
        else:
            exact(identity,{'device','inode'});need(integer(identity['device'],0,2**64-1) and integer(identity['inode'],1,2**64-1))
        self.events=unpack(self.state['transcript']);seen=set();cursor=None;frame=None;release=False;proof=None;offset=0;read=False
        for row in self.events:
            exact(row,{'command','receipt'});query=command(row['command']);receipt=row['receipt']
            need(query['requestId']==self.request_id and query['commandId'] not in seen);seen.add(query['commandId'])
            op=query['operation']
            if op in ('read','release'):need(owns_slot(self.state))
            if op=='read':need(not read and cursor is not None);read=True
            if op=='release':need(not release);release=True
            if op in ('read','read-bytes'):need(not release)
            if receipt is None:continue
            if op=='read':
                validate(receipt,query,self.pid,receipt['capturedEpochMs']);frame=receipt;packet=receipt
            elif op=='read-bytes':
                need(frame is not None and query['offset']==offset)
                packet=validate_summary(receipt,query,self.pid);offset+=receipt['dataBytes']
                need(packet['source']['pngBytes']==frame['source']['image']['bytes'])
            else:
                storage(receipt,query,self.pid,receipt['capturedEpochMs']);packet=receipt
                if proof is not None:need(absent(receipt))
                if absent(receipt):need(release);proof=receipt
            if cursor is not None:
                need(packet['instance']==cursor['instance'] and packet['sequence']>cursor['sequence']
                     and packet['requestedEpochMs']>=cursor['capturedEpochMs'])
            cursor=packet
        need(same(self.state['frame'],frame) and same(self.state['absence'],proof))
        if self.state['phase'] in ('captured','released','removed') and frame is not None:
            need(offset==frame['source']['image']['bytes'] or self.state['phase'] in ('released','removed'))
        if self.state['phase']=='captured':need(frame is not None and identity is not None)
        if self.state['phase'] in ('captured','released','removed'):need(owns_slot(self.state))
        if self.state['phase'] in ('released','removed'):need(proof is not None)

    def _write(self,value=None):
        need(self.guard() is not False and same(self.store.read(),self.state))
        value=deepcopy(self.state if value is None else value);value['transcript']=pack(self.events)
        self.store.write(value,self.state);need(same(self.store.read(),value) and self.guard() is not False);self.state=value

    def _reader(self):
        def intent(query):
            command(query);need(query['requestId']==self.request_id and all(row['command']['commandId']!=query['commandId'] for row in self.events))
            self.events.append(dict(command=deepcopy(query),receipt=None));self._write()
        def received(query,packet):
            need(self.events and same(self.events[-1]['command'],query) and self.events[-1]['receipt'] is None)
            value=deepcopy(self.state)
            if value['absence'] is not None:need(query['operation']=='inspect' and absent(packet))
            self.events[-1]['receipt']=chunk_summary(packet,query,self.pid) if query['operation']=='read-bytes' else deepcopy(packet)
            if query['operation']=='read':value['frame']=deepcopy(packet)
            elif query['operation']!='read-bytes' and absent(packet):value['absence']=deepcopy(packet)
            self._write(value)
        reader=self.factory(intent,received);need(isinstance(reader,NativeVulkanWorldFrame) and reader.pid==self.pid)
        for row in self.events:
            packet=row['receipt']
            if packet is not None:
                if row['command']['operation']=='read-bytes':packet=packet['packet']
                reader.instance,reader.sequence,reader.epoch=packet['instance'],packet['sequence'],packet['capturedEpochMs']
        return reader

    def _query(self,operation):
        return dict(schemaVersion=1,action='feature-vulkan-world-frame',commandId='ios-'+uuid.uuid4().hex,
                    requestId=self.request_id,operation=operation)

    def _file(self,descriptor):
        PrivateFeatureState(self.root/self.name)._parent();identity=self.state['file'];need(identity is not None)
        opened,current=os.fstat(descriptor),(self.root/self.name).lstat()
        for info in (opened,current):
            need(stat.S_ISREG(info.st_mode) and info.st_nlink==1 and info.st_uid==os.geteuid()
                 and stat.S_IMODE(info.st_mode)==0o600 and 0<=info.st_size<=PNG_LIMIT)
        need((opened.st_dev,opened.st_ino)==(current.st_dev,current.st_ino)==(identity['device'],identity['inode']))

    def capture(self,ticket):
        try:
            with self.lock.held():
                self._load();need(self.state is None);identifier(ticket)
                started=self.monotonic();need(number(started,0,1e15))
                initial=dict(vulkanWorldOwnerVersion=VERSION,binding=self.binding,runId=self.run,role=self.role,stage=self.stage,
                    requestId=self.request_id,root=str(self.root),name=self.name,ticket=ticket,phase='planned',file=None,frame=None,absence=None)
                self._write(initial)
                descriptor=os.open(self.root/self.name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,'O_NOFOLLOW',0),0o600)
                with os.fdopen(descriptor,'wb') as stream:
                    info=os.fstat(stream.fileno());value=deepcopy(self.state);value.update(phase='opened',file=dict(device=info.st_dev,inode=info.st_ino))
                    self._write(value);self._file(stream.fileno())
                    need(number(self.monotonic(),started,started+1.5) and self.guard() is not False)
                    reader=self._reader()
                    before=reader.perform(self._query('inspect'))['source']
                    need(before==dict(retired=False,present=False,callbacks=0,gpuPending=False,metadataBytes=0,pngBytes=0,gpuBufferBytes=0))
                    frame=reader.perform(self._query('read'));raw=reader.image(frame)
                    need(stream.write(raw)==len(raw));stream.flush();os.fsync(stream.fileno());self._file(stream.fileno())
                value=deepcopy(self.state);value['phase']='captured';self._write(value)
                need(self._read()==raw and self.monotonic()-started<1.5 and self.guard() is not False)
                fresh(frame['capturedEpochMs'],reader.clock_ms())
                return deepcopy(frame),raw
        except Exception:
            raise NativeUIError('Vulkan world image acquisition failed; durable file/command ownership remains') from None

    def _read(self):
        need(self.state['phase'] in ('captured','released') and self.state['frame'] is not None)
        descriptor=os.open(self.root/self.name,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0)|getattr(os,'O_NONBLOCK',0))
        with os.fdopen(descriptor,'rb') as stream:
            self._file(stream.fileno());before=os.fstat(stream.fileno());raw=stream.read(PNG_LIMIT+1)
            self._file(stream.fileno());after=os.fstat(stream.fileno())
            need((before.st_size,before.st_mtime_ns,before.st_ctime_ns)==(after.st_size,after.st_mtime_ns,after.st_ctime_ns))
        original_pixels(self.state['frame'],raw)
        for event in self.events:
            if event['command']['operation']=='read-bytes' and event['receipt'] is not None:
                validate_summary(event['receipt'],event['command'],self.pid,raw)
        record_original_read(self.root/self.name)
        return raw

    def archive(self):
        with self.lock.held():
            self._load();raw=self._read();need(same(self.store.read(),self.state) and self.guard() is not False);return raw

    def verify_owned_artifact(self):
        """Inspect retained file ownership after native release, without pixels.

        Interrupted/abandoned acquisitions may own an empty or partial file.
        Its inode is cleanup responsibility; this is never PNG/content proof.
        No native command, file mutation or metadata retirement is performed.
        """
        with self.lock.held():
            self._load();need(self.state is not None and self.state['phase']=='released' and absent(self.state['absence']))
            path=self.root/self.name
            if self.state['file'] is None:
                try:path.lstat()
                except FileNotFoundError:pass
                else:need(False)
            else:
                descriptor=os.open(path,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0)|getattr(os,'O_NONBLOCK',0))
                with os.fdopen(descriptor,'rb') as stream:self._file(stream.fileno())
            need(same(self.store.read(),self.state) and self.guard() is not False)
            return True

    def release(self):
        """Retire native resources; preserve the original host PNG and ledger."""
        try:
            started=previous=self.monotonic();need(number(started,0,1e15))
            with self.lock.held():
                self._load();need(self.state is not None and owns_slot(self.state));reader=self._reader()
                if not any(row['command']['operation']=='release' for row in self.events):
                    proof=reader.perform(self._query('release'))
                else:proof=reader.perform(self._query('inspect'))
                for attempt in range(81):
                    current=self.monotonic();need(number(current,previous,1e15) and current-started<20);previous=current
                    if absent(proof):
                        value=deepcopy(self.state)
                        if value['phase']!='removed':value['phase']='released'
                        self._write(value);return deepcopy(proof)
                    if attempt<80:self.sleep(.25)
                    proof=reader.perform(self._query('inspect'))
                need(False)
        except Exception:
            raise NativeUIError('Vulkan world resources remain unresolved; ownership is retained') from None

    def remove_image(self):
        """Explicit artifact removal, only after fresh real native retirement."""
        with self.lock.held():
            self.release();self._load();path=self.root/self.name
            try:descriptor=os.open(path,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0)|getattr(os,'O_NONBLOCK',0))
            except FileNotFoundError:descriptor=None
            if descriptor is not None:
                with os.fdopen(descriptor,'rb') as stream:
                    need(self.state['phase']!='removed');self._file(stream.fileno());path.unlink()
            try:path.lstat()
            except FileNotFoundError:pass
            else:need(False)
            value=deepcopy(self.state);value['phase']='removed';self._write(value)
            return True
