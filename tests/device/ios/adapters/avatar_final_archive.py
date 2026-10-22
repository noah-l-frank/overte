"""CAS-retire fixed Avatar metadata only after immutable original validation.

No SDK, native query, credential, backend mutation or normal input is delivered.
Every actual metadata value is retained before its original path can retire.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
from adapters.native_clock_join import digest
from adapters.native_feature_observation import exact,integer,need
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.original_frame_store import OriginalFrameStore
from adapters.script_feature.history import pack,unpack,same
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.contract import identifier
from feature_journeys.phase_fixture import validate as phase_original
from ios.adapters.avatar_whole_snapshots import AvatarWholeSnapshots
from ios.adapters.emote_original_lease import EmoteOriginalLease

VERSION=1


class ArchiveSnapshots(AvatarWholeSnapshots):
    def __init__(self,root,binding,run,role,entries,guard,save):
        self.entries,self.save=entries,save
        self.originals=OriginalFrameStore(root,binding,run,role,guard,self.storage,
            namespace='avatar-final-copy',schema_prefix='avatarFinalCopy')
    def validate(self):
        rows=self.entries();need(type(rows) is list and len(rows)<=256)
        for index,value in enumerate(rows,1):need(value['index']==index);self.inspect(value)
    def retain(self,value):
        need(type(value) is dict);self.validate()
        for original in self.entries():
            if self.inspect(original) and same(self.originals.read(original),value):return dict(index=original['index'],sha256=original['sha256'])
        need(len(self.entries())<256);compact=self.originals.write(len(self.entries())+1,value)
        return {key:compact[key] for key in ('index','sha256')}


class IOSAvatarFinalArchive:
    def __init__(self,store,root,binding,run,role,locks,paths,guard,validate):
        need(isinstance(store,PrivateFeatureState) and role in ('primary','actor') and type(locks) is dict and set(locks)=={'primary','actor'}
            and all(isinstance(lock,ScriptSourceLock) for lock in locks.values()) and all(callable(fn) for fn in (guard,validate)))
        self.store,self.root,self.binding,self.run,self.role=store,Path(root),context(binding),identifier(run),role
        self.locks,self.guard,self.validate=locks,guard,validate
        need(store.path==locks[role].path.with_name('ios-avatar-'+role+'-'+run+'-finalization.json')
            and self.root.is_absolute() and self.root.resolve(strict=True)==self.root and self.root.is_dir()
            and type(paths) is list and 1<=len(paths)<=128 and all(isinstance(path,PrivateFeatureState) for path in paths)
            and len({str(path.path) for path in paths})==len(paths) and all(path.path!=store.path for path in paths))
        self.paths=paths;self.previous=store.read();self.state=None;self.qualified=None
        if self.previous is not None:self.state=self.decode(self.previous)
    def envelope(self,state):return dict(iosAvatarFinalArchiveVersion=VERSION,runId=self.run,role=self.role,binding=self.binding,
        artifactRoot=str(self.root),paths=[str(path.path) for path in self.paths],payload=pack([state]))
    def snapshots(self):return ArchiveSnapshots(self.root,self.binding,self.run,self.role,lambda:self.state['snapshots'],self.locked,self.save)
    def locked(self):
        for lock in self.locks.values():lock.assert_held()
    def copy(self,ref):
        exact(ref,{'index','original'});need(integer(ref['index'],1,len(self.paths)));value=self.snapshots().read(ref['original'])
        exact(value,{'iosAvatarFinalCopyVersion','runId','role','binding','index','path','value'})
        need(type(value['iosAvatarFinalCopyVersion']) is int and value['iosAvatarFinalCopyVersion']==VERSION and value['runId']==self.run
            and value['role']==self.role and same(value['binding'],self.binding) and value['index']==ref['index']
            and value['path']==str(self.paths[ref['index']-1].path) and (value['value'] is None or type(value['value']) is dict))
        return value['value']
    def copies(self):return {str(self.paths[ref['index']-1].path):self.copy(ref) for ref in self.state['records']}
    def decode(self,value):
        exact(value,{'iosAvatarFinalArchiveVersion','runId','role','binding','artifactRoot','paths','payload'});rows=unpack(value['payload'])
        need(len(rows)==1 and same(value,self.envelope(rows[0])));state=rows[0]
        exact(state,{'phase','phaseOriginal','hashes','snapshots','records','pending','retired'})
        need(state['phase'] in ('freezing','validated','retiring','complete') and type(state['hashes']) is list and len(state['hashes'])==len(self.paths)
            and type(state['records']) is list and len(state['records'])<=len(self.paths) and integer(state['retired'],0,len(self.paths)))
        status=state['phaseOriginal'];phase_original(status,run=self.run,area='avatar-people',request=status['requestId'],epoch=status['capturedEpochMs']);need(not status['active'])
        old=self.state;self.state=state
        try:
            self.snapshots().validate()
            for index,ref in enumerate(state['records'],1):need(ref['index']==index and digest(self.copy(ref))==state['hashes'][index-1])
            p=state['pending']
            if p is not None:
                exact(p,{'index','value'});need(state['phase']=='freezing' and p['index']==len(state['records'])+1
                    and integer(p['index'],1,len(self.paths)) and digest(p['value'])==state['hashes'][p['index']-1])
            if state['phase']!='freezing':need(len(state['records'])==len(self.paths) and p is None)
            if state['phase'] in ('freezing','validated'):need(state['retired']==0)
            if state['phase']=='complete':need(state['retired']==len(self.paths))
            return deepcopy(state)
        finally:self.state=old
    def bound(self):
        self.locked();need(self.guard() is not False)
        actual=self.store.read()
        if not same(actual,self.previous):need(self.state is not None and same(actual,self.envelope(self.state)));self.previous=deepcopy(actual)
    def save(self):
        self.bound();value=self.envelope(self.state);self.store.write(value,self.previous);need(same(self.store.read(),value));self.previous=deepcopy(value)
    def begin(self,status):
        self.bound();need(self.state is None)
        phase_original(status,run=self.run,area='avatar-people',request=status['requestId'],epoch=status['capturedEpochMs']);need(not status['active'])
        self.state=dict(phase='freezing',phaseOriginal=deepcopy(status),hashes=[digest(path.read()) for path in self.paths],snapshots=[],records=[],pending=None,retired=0);self.save()
    def freeze(self):
        self.bound();need(self.state is not None)
        if self.state['phase']!='freezing':return
        while len(self.state['records'])<len(self.paths):
            index=len(self.state['records'])+1
            if self.state['pending'] is None:
                value=self.paths[index-1].read();need(digest(value)==self.state['hashes'][index-1])
                self.state['pending']=dict(index=index,value=value);self.save()
            p=self.state['pending'];value=dict(iosAvatarFinalCopyVersion=VERSION,runId=self.run,role=self.role,binding=self.binding,
                index=index,path=str(self.paths[index-1].path),value=p['value'])
            ref=dict(index=index,original=self.snapshots().retain(value));need(same(self.copy(ref),p['value']))
            self.state['records'].append(ref);self.state['pending']=None;self.save()
        self.qualify();self.state['phase']='validated';self.save()
    def qualify(self):
        lease=EmoteOriginalLease(self.root,[path.path for path in self.paths]+[self.store.path])
        result=self.validate(self.copies());lease.guard();self.qualified=lease;return result
    def retire(self):
        self.bound();self.freeze();need(self.state['phase'] in ('validated','retiring','complete'))
        if self.qualified is None:self.qualify()
        self.qualified.guard()
        if self.state['phase']=='complete':need(all(path.read() is None for path in self.paths));return dict(performed=True)
        self.state['phase']='retiring';self.save()
        while self.state['retired']<len(self.paths):
            index=self.state['retired'];path=self.paths[index];original=self.copy(self.state['records'][index]);current=path.read()
            need(current is None or same(current,original));self.bound();self.qualified.guard()
            if current is not None:path.discard(current)
            need(path.read() is None);self.qualified.guard();self.state['retired']+=1;self.save()
        self.state['phase']='complete';self.save();return dict(performed=True)
