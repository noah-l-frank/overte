"""Immutable native file-source originals and exact legacy owner migration.

Native observations are never rebuilt from controlled input or refreshed from
history. Local failed writes retain their exact opened prefix and ownership.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import base64
import hashlib
import os
from pathlib import Path
import stat
from adapters.native_feature_observation import decode,exact,integer,need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.original_file_reads import record as record_original_read
from adapters.original_frame_store import OriginalFrameStore
from adapters.script_feature.history import canonical,same

VERSION=1


def sha(raw):return hashlib.sha256(raw).hexdigest()


def node(info):return dict(device=info.st_dev,inode=info.st_ino,bytes=info.st_size,modifiedNs=info.st_mtime_ns,changedNs=info.st_ctime_ns)


def sync(directory):
    fd=os.open(directory,os.O_RDONLY|os.O_DIRECTORY|os.O_CLOEXEC)
    try:os.fsync(fd)
    finally:os.close(fd)


def private_original(path,limit):
    path=Path(path);PrivateFeatureState(path)._parent();fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC)
    try:
        before=os.fstat(fd);need(stat.S_ISREG(before.st_mode) and before.st_uid==os.geteuid() and stat.S_IMODE(before.st_mode)==0o600 and before.st_nlink==1 and 0<before.st_size<=limit)
        raw=b''
        while len(raw)<=limit:
            part=os.read(fd,min(65536,limit+1-len(raw)))
            if not part:break
            raw+=part
        after=path.lstat();need(stat.S_ISREG(after.st_mode) and node(before)==node(os.fstat(fd))==node(after) and len(raw)==before.st_size)
        record_original_read(path);return raw,node(before)
    finally:os.close(fd)


class FileSources:
    NAMESPACE='assets-files-native'
    SCHEMA_PREFIX='iosAssetsFilesSource'
    MIGRATION_PREFIX='assets-files-migration-'
    RECORD_KEY='iosAssetsFilesSourceRecordVersion'
    MIGRATION_KEY='iosAssetsFilesSourceMigrationVersion'
    MAX_REFS=129

    def __init__(self,owner,role,guard,save):
        need(role in ('primary','actor') and callable(guard) and callable(save));self.owner,self.role,self.guard,self.save_owner=owner,role,guard,save
        self.refs=[];self.pending=None;self.migration=None;self.migrating=False;self.active=False;self.migration_value=None;self.migration_previous=None
        self.store=OriginalFrameStore(owner.store.path.parent,owner.binding,owner.run,role,guard,self.intent,namespace=self.NAMESPACE,schema_prefix=self.SCHEMA_PREFIX,monotonic=owner.native.monotonic)
        self.migration_store=PrivateFeatureState(owner.store.path.parent/(self.MIGRATION_PREFIX+owner.run+'-'+role+'.json'))

    def manifest(self):return dict(refs=deepcopy(self.refs),pending=deepcopy(self.pending),migration=deepcopy(self.migration))

    def load(self,value):
        exact(value,{'refs','pending','migration'});need(type(value['refs']) is list and len(value['refs'])<=self.MAX_REFS)
        for index,reference in enumerate(value['refs'],1):need(self.store.expand(reference)['index']==index)
        self.refs,self.pending,self.migration=deepcopy(value['refs']),deepcopy(value['pending']),deepcopy(value['migration'])
        if self.pending is not None:
            exact(self.pending,{'queryId','querySha256','rawSha256','rawBytes','original','snapshot'})
            need(type(self.pending['queryId']) is str and __import__('re').fullmatch('ios-[a-f0-9]{32}',self.pending['queryId']) is not None and integer(self.pending['rawBytes'],1,262144))
            for key in ('querySha256','rawSha256'):need(type(self.pending[key]) is str and __import__('re').fullmatch('[a-f0-9]{64}',self.pending[key]) is not None)
            if self.pending['original'] is not None:
                self.store.original(self.pending['original']);need(self.pending['original']['index']==len(self.refs)+1)
                current=self.inspect(self.pending['original'])
                if self.pending['snapshot'] is not None:need(same(current,self.pending['snapshot']))
            else:need(self.pending['snapshot'] is None)
        if self.migration is not None:self.migration_original()

    def inspect(self,reference):
        self.store.original(reference);path=self.store.path(reference)
        if reference['phase']=='planned':need(not os.path.lexists(path));return None
        fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC)
        try:
            self.store.file(path,fd,reference);raw=b''
            while len(raw)<=reference['bytes']:
                chunk=os.read(fd,min(65536,reference['bytes']+1-len(raw)))
                if not chunk:break
                raw+=chunk
            self.store.file(path,fd,reference);need(len(raw)<=reference['bytes'])
        finally:os.close(fd)
        result=dict(bytes=len(raw),sha256=sha(raw),complete=len(raw)==reference['bytes'] and sha(raw)==reference['sha256'])
        need(reference['phase']!='saved' or result['complete']);return result

    def intent(self,kind,reference):
        need(kind=='original');self.store.original(reference)
        if self.migrating:
            need(reference['index']==1 and self.migration_value is not None);self.migration_value['original']=deepcopy(reference);self.save_migration();return True
        need(self.pending is not None and reference['index']==len(self.refs)+1);self.pending['original']=deepcopy(reference);self.save_owner();return True

    def read_record(self,reference):
        body=self.store.read(self.store.expand(reference));need(type(body) is dict and type(body.get(self.RECORD_KEY)) is int and body[self.RECORD_KEY]==VERSION)
        kind=body.get('kind')
        if kind=='native':
            exact(body,{self.RECORD_KEY,'kind','query','raw'});need(type(body['raw']) is str and 0<len(body['raw'].encode())<=262144)
        else:
            need(kind=='legacy-owner');exact(body,{self.RECORD_KEY,'kind','rawBase64','identity'})
            raw=base64.b64decode(body['rawBase64'],validate=True);need(base64.b64encode(raw).decode()==body['rawBase64'] and 0<len(raw)<=65536)
            exact(body['identity'],{'device','inode','bytes','modifiedNs','changedNs'});need(all(integer(item,0,2**64-1) for item in body['identity'].values()) and body['identity']['bytes']==len(raw))
        return body

    def capture(self,query,raw):
        need(self.pending is None and not self.active and type(raw) is str and 0<len(raw.encode())<=262144)
        self.pending=dict(queryId=query['commandId'],querySha256=sha(canonical(query)),rawSha256=sha(raw.encode()),rawBytes=len(raw.encode()),original=None,snapshot=None);self.save_owner()
        self.active=True
        try:
            self.store.write(len(self.refs)+1,{self.RECORD_KEY:VERSION,'kind':'native','query':deepcopy(query),'raw':raw})
        except BaseException as primary:
            self.active=False
            if self.pending is not None and self.pending['original'] is not None:
                try:self.pending['snapshot']=self.inspect(self.pending['original']);self.save_owner()
                except BaseException as secondary:primary.add_note('Freezing the retained source prefix also failed: '+type(secondary).__name__)
            raise
        finally:self.active=False

    def completed_capture(self):
        need(not self.active and self.pending is not None and self.pending['original'] is not None and self.pending['original']['phase']=='saved')
        reference=self.store.compact(self.pending['original']);record=self.read_record(reference)
        need(record['kind']=='native' and record['query']['commandId']==self.pending['queryId'] and sha(canonical(record['query']))==self.pending['querySha256']
            and sha(record['raw'].encode())==self.pending['rawSha256'] and len(record['raw'].encode())==self.pending['rawBytes'])
        return reference,record

    def accept_capture(self):
        reference,record=self.completed_capture();self.refs.append(reference);self.pending=None;return record

    def save_migration(self):
        self.migration_codec(self.migration_value);self.migration_store.write(self.migration_value,self.migration_previous);sync(self.migration_store.path.parent);self.migration_previous=deepcopy(self.migration_value)

    def migration_codec(self,value):
        exact(value,{self.MIGRATION_KEY,'binding','runId','role','legacy','original','snapshot'})
        need(type(value[self.MIGRATION_KEY]) is int and value[self.MIGRATION_KEY]==VERSION and same(value['binding'],self.owner.binding)
            and value['runId']==self.owner.run and value['role']==self.role)
        exact(value['legacy'],{'sha256','identity'});need(type(value['legacy']['sha256']) is str and __import__('re').fullmatch('[a-f0-9]{64}',value['legacy']['sha256']) is not None)
        exact(value['legacy']['identity'],{'device','inode','bytes','modifiedNs','changedNs'});need(all(integer(item,0,2**64-1) for item in value['legacy']['identity'].values()) and 0<value['legacy']['identity']['bytes']<=65536)
        if value['original'] is not None:
            self.store.original(value['original']);need(value['original']['index']==1)
            if value['snapshot'] is not None:need(same(self.inspect(value['original']),value['snapshot']))
        else:need(value['snapshot'] is None)
        return value

    def prepare_migration(self,previous):
        need(not self.refs and self.pending is None);raw,identity=private_original(self.owner.store.path,65536);need(same(decode(raw.decode('utf-8'),limit=65536),previous))
        prior=self.migration_store.read()
        if prior is None:
            value={self.MIGRATION_KEY:VERSION,'binding':self.owner.binding,'runId':self.owner.run,'role':self.role,
                'legacy':dict(sha256=sha(raw),identity=identity),'original':None,'snapshot':None}
            self.migration_value=value;self.migration_previous=None;self.save_migration();self.migrating=True
            try:self.store.write(1,{self.RECORD_KEY:VERSION,'kind':'legacy-owner','rawBase64':base64.b64encode(raw).decode(),'identity':identity})
            except BaseException as primary:
                if self.migration_value['original'] is not None:
                    try:self.migration_value['snapshot']=self.inspect(self.migration_value['original']);self.save_migration()
                    except BaseException as secondary:primary.add_note('Freezing the retained migration prefix also failed: '+type(secondary).__name__)
                raise
            finally:self.migrating=False
            prior=self.migration_store.read()
        self.migration_codec(prior);need(prior['legacy']==dict(sha256=sha(raw),identity=identity) and prior['original'] is not None and prior['original']['phase']=='saved')
        reference=self.store.compact(prior['original']);record=self.read_record(reference);need(record['kind']=='legacy-owner' and base64.b64decode(record['rawBase64'])==raw and record['identity']==identity)
        migration_raw,migration_identity=private_original(self.migration_store.path,65536)
        self.migration=dict(file=self.migration_store.path.name,sha256=sha(migration_raw),identity=migration_identity);self.refs=[reference]

    def migration_original(self):
        exact(self.migration,{'file','sha256','identity'});need(self.migration['file']==self.migration_store.path.name)
        raw,identity=private_original(self.migration_store.path,65536);need(identity==self.migration['identity'] and sha(raw)==self.migration['sha256']);value=self.migration_codec(decode(raw.decode('utf-8'),limit=65536))
        need(value['original'] is not None and value['original']['phase']=='saved' and self.refs and self.store.compact(value['original'])==self.refs[0])
        record=self.read_record(self.refs[0]);need(record['kind']=='legacy-owner' and sha(base64.b64decode(record['rawBase64']))==value['legacy']['sha256'] and record['identity']==value['legacy']['identity']);return value

    def owned_paths(self):
        result={self.store.path(self.store.expand(ref)) for ref in self.refs}
        if self.pending is not None and self.pending['original'] is not None and self.pending['original']['phase']!='planned':result.add(self.store.path(self.pending['original']))
        if self.migration is not None:result.add(self.migration_store.path)
        return result

    def legacy_migration_paths(self):
        """Inspect an interrupted v1 migration; never adopt or rewrite it."""
        value=self.migration_store.read()
        if value is None:return set()
        self.migration_codec(value);raw,identity=private_original(self.owner.store.path,65536)
        need(value['legacy']==dict(sha256=sha(raw),identity=identity));result={self.migration_store.path}
        reference=value['original']
        if reference is not None:
            self.inspect(reference)
            if reference['phase']!='planned':result.add(self.store.path(reference))
            if reference['phase']=='saved':
                record=self.read_record(self.store.compact(reference))
                need(record['kind']=='legacy-owner' and base64.b64decode(record['rawBase64'])==raw and record['identity']==identity)
        return result
