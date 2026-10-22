"""Durable private Snapshot bytes reconstructed only from retained originals.

This owns a host artifact, not image content, export success or product quiet.
The whole feature must retain the participating native/query owners until its
independent cleanup has finished. No uncertain create/write/unlink is replayed.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import os
import re
import secrets
import stat
from adapters.native_feature_observation import exact,integer,need
from adapters.native_clock_join import digest
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.normal_ui import NativeUIError
from adapters.original_frame_store import OriginalFrameStore
from adapters.script_feature.history import pack,unpack,same
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.contract import identifier
from snapshot_file_contract import MAX_FILE_BYTES
from ios.adapters.snapshot_manifest import SnapshotManifest
from ios.adapters.snapshot_chunk_owner import SnapshotChunk
from ios.adapters.snapshot_original_file import original


class SnapshotArtifact:
    def __init__(self,store,lock,binding,run,role,index,guard):
        need(isinstance(store,PrivateFeatureState) and isinstance(lock,ScriptSourceLock) and callable(guard))
        self.store,self.lock,self.binding,self.run,self.role,self.index,self.guard=store,lock,deepcopy(context(binding)),identifier(run),role,index,guard
        need(role in ('primary','actor') and integer(index,1,128) and re.fullmatch('[1-9][0-9]*',binding['processIdentity'])
            and store.path.name=='ios-snapshot-'+role+'-artifact-'+format(index,'04d')+'.json'
            and lock.path==store.path.with_name('script-feature-sources.lock'))
        lock.assert_held();self.previous=store.read();self.state=None if self.previous is None else self.decode(self.previous)

    def envelope(self):
        return dict(iosSnapshotArtifactVersion=1,binding=self.binding,runId=self.run,role=self.role,index=self.index,payload=pack([self.state]))

    def decode(self,value):
        exact(value,{'iosSnapshotArtifactVersion','binding','runId','role','index','payload'})
        need(type(value['iosSnapshotArtifactVersion']) is int and value['iosSnapshotArtifactVersion']==1
            and same(value['binding'],self.binding) and value['runId']==self.run and value['role']==self.role
            and type(value['index']) is int and value['index']==self.index)
        rows=unpack(value['payload']);need(len(rows)==1);state=rows[0]
        exact(state,{'phase','name','before','after','chunks','journals','work','fact','file'})
        need(state['phase'] in ('reserved','assembling','opened','copied','removing','removed')
            and integer(state['before'],1,128) and integer(state['after'],state['before']+1,128)
            and type(state['chunks']) is list and 1<=len(state['chunks'])<=1024
            and all(integer(index,1,1024) for index in state['chunks'])
            and state['chunks']==list(range(state['chunks'][0],state['chunks'][0]+len(state['chunks']))))
        need(type(state['name']) is str and re.fullmatch('snapshot-'+self.run+'-'+self.role+r'-[0-9a-f]{32}\.bytes',state['name']))
        need(type(state['journals']) is list and len(state['journals'])==len(state['chunks'])+2
            and all(type(value) is str and re.fullmatch('[0-9a-f]{64}',value) for value in state['journals']))
        if state['work'] is not None:self.frames().original(state['work']);need(state['work']['index']==self.index)
        if state['file'] is not None:
            exact(state['file'],{'device','inode'});need(integer(state['file']['device'],0) and integer(state['file']['inode'],1))
        if state['phase'] in ('opened','copied','removing'):need(state['file'] is not None)
        if state['phase'] not in ('reserved','removed'):need(state['work'] is not None and state['work']['phase']=='saved')
        if state['phase']=='reserved':need(state['fact'] is None and state['file'] is None)
        elif state['phase']!='removed' or state['fact'] is not None:
            need(type(state['fact']) is dict and type(state['fact'].get('iosSnapshotOriginalFileVersion')) is int
                and state['fact']['iosSnapshotOriginalFileVersion']==1)
        return state

    def bound(self):
        self.lock.assert_held();need(self.guard() is not False and same(self.store.read(),self.previous))

    def save(self):
        self.bound();value=self.envelope();self.decode(value);self.store.write(value,self.previous)
        need(same(self.store.read(),value));self.previous=deepcopy(value)

    def frames(self):
        return OriginalFrameStore(self.store.path.parent,self.binding,self.run,self.role,self.guard,self.storage,
            namespace='snapshot-artifact-work',schema_prefix='snapshotArtifactWork')

    def storage(self,kind,value):
        self.bound();need(kind=='original' and self.state['phase']=='reserved' and value['index']==self.index)
        self.frames().original(value);old=self.state['work']
        if old is None:need(value['phase']=='planned')
        else:need(value['phase']=={'planned':'opened','opened':'saved'}.get(old['phase'])
            and all(same(value[key],old[key]) for key in old if key not in ('phase','file'))
            and (old['phase']=='planned' or same(value['file'],old['file'])))
        self.state['work']=deepcopy(value);self.save()

    def owners(self):
        def owner(cls,kind,index):
            return cls.history(PrivateFeatureState(self.store.path.with_name('ios-snapshot-'+self.role+'-'+kind+'-'+format(index,'04d')+'.json')),
                self.lock,self.binding,self.run,self.role,index)
        before,after=owner(SnapshotManifest,'manifest',self.state['before']),owner(SnapshotManifest,'manifest',self.state['after'])
        chunks=[owner(SnapshotChunk,'chunk',index) for index in self.state['chunks']]
        need([digest(value.previous) for value in [before,after]+chunks]==self.state['journals'])
        return before,after,chunks

    def originals(self):
        self.bound();need(self.state is not None and self.state['work'] is not None)
        work=self.frames().read(self.state['work']);fact,raw=original(*self.owners(),work)
        if self.state['fact'] is not None:need(same(fact,self.state['fact']))
        return fact,raw

    def path(self):
        path=self.store.path.parent/self.state['name'];PrivateFeatureState(path)._parent();return path

    def identity(self,descriptor):
        need(self.state['file'] is not None);path=self.path();before,current=os.fstat(descriptor),path.lstat()
        for row in (before,current):
            need(stat.S_ISREG(row.st_mode) and row.st_nlink==1 and row.st_uid==os.geteuid()
                and stat.S_IMODE(row.st_mode)==0o600 and row.st_size<=MAX_FILE_BYTES
                and (row.st_dev,row.st_ino)==(self.state['file']['device'],self.state['file']['inode']))
        return before

    def capture(self,before,after,chunks,work):
        self.bound();need(self.state is None);original(before,after,chunks,work)
        need(before.store.path.parent==self.store.path.parent and same(before.binding,self.binding)
            and before.run==self.run and before.role==self.role and before.lock.path==self.lock.path)
        self.state=dict(phase='reserved',name='snapshot-'+self.run+'-'+self.role+'-'+secrets.token_hex(16)+'.bytes',
            before=before.index,after=after.index,chunks=[owner.index for owner in chunks],
            journals=[digest(value.previous) for value in [before,after]+chunks],work=None,fact=None,file=None);self.save()
        self.frames().write(self.index,work);fact,raw=self.originals()
        self.state.update(phase='assembling',fact=fact);self.save()
        descriptor=os.open(self.path(),os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,'O_NOFOLLOW',0),0o600)
        with os.fdopen(descriptor,'wb') as stream:
            info=os.fstat(stream.fileno());self.state.update(phase='opened',file=dict(device=info.st_dev,inode=info.st_ino));self.save()
            self.identity(stream.fileno());need(stream.write(raw)==len(raw));stream.flush();os.fsync(stream.fileno());self.identity(stream.fileno())
        self.state['phase']='copied';self.save();need(self.read()==raw);return deepcopy(self.state['fact'])

    def read(self,*,partial=False):
        self.bound();need(type(partial) is bool and self.state is not None and self.state['phase'] in ('opened','copied','removing'))
        _fact,original_raw=self.originals()
        descriptor=os.open(self.path(),os.O_RDONLY|getattr(os,'O_NOFOLLOW',0)|getattr(os,'O_NONBLOCK',0))
        with os.fdopen(descriptor,'rb') as stream:
            before=self.identity(stream.fileno());raw=stream.read(MAX_FILE_BYTES+1);after=self.identity(stream.fileno())
            need((before.st_size,before.st_mtime_ns,before.st_ctime_ns)==(after.st_size,after.st_mtime_ns,after.st_ctime_ns))
        need(original_raw.startswith(raw) if partial else raw==original_raw)
        if not partial:need(len(raw)==self.state['fact']['file']['size'] and hashlib.sha256(raw).hexdigest()==self.state['fact']['file']['sha256'])
        return raw

    def recover(self):
        """Adopt only a fully written existing inode; never repeat any write."""
        self.bound();need(self.state is not None)
        if self.state['phase']=='reserved':
            need(self.state['work'] is not None and self.state['work']['phase'] in ('opened','saved'))
            self.originals()
            # This can recover a completed raw-source write, but cannot issue a
            # new artifact create after an interrupted capture responsibility.
            if self.state['work']['phase']=='opened':self.storage('original',dict(self.state['work'],phase='saved'))
            raise NativeUIError('Snapshot source retained; artifact creation remains unresolved')
        need(self.state['phase'] in ('opened','copied'));self.read();self.state['phase']='copied';self.save()
        return deepcopy(self.state['fact'])

    def remove(self):
        """Caller must first prove independent paired product/native quiet."""
        self.bound();need(self.state is not None)
        if self.state['phase'] in ('removing','removed'):return self.removed()
        if self.state['phase'] in ('reserved','assembling'):
            try:self.path().lstat()
            except FileNotFoundError:pass
            else:raise NativeUIError('Unrecorded artifact inode remains owned')
        else:
            partial=self.state['phase']=='opened';self.read(partial=partial)
            self.state['phase']='removing';self.save();self.read(partial=partial);self.path().unlink()
        return self.removed()

    def removed(self):
        self.bound();need(self.state['phase'] in ('reserved','assembling','removing','removed'))
        try:self.path().lstat()
        except FileNotFoundError:pass
        else:raise NativeUIError('Snapshot artifact unlink is unresolved; it is never replayed')
        self.state['phase']='removed';self.save();return {'performed':True}
