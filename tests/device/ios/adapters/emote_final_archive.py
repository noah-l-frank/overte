"""Retain validated Emote originals before retiring fixed host metadata.

This owner sends no SDK/native command or normal input. Phase/run retirement
permits only metadata retirement after a separate historical native proof.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
from adapters.native_clock_join import digest
from adapters.native_feature_observation import exact,integer,need
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.script_feature.history import pack,unpack,same
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.contract import identifier
from feature_journeys.phase_fixture import validate as phase_packet

VERSION=1


class IOSEmoteFinalArchive:
    def __init__(self,store,root,binding,run,role,lock,primary_lock,paths,guard,validate):
        need(isinstance(store,PrivateFeatureState) and isinstance(lock,ScriptSourceLock) and isinstance(primary_lock,ScriptSourceLock)
            and all(callable(fn) for fn in (guard,validate)))
        self.store,self.root,self.binding,self.run,self.role=store,Path(root),deepcopy(context(binding)),identifier(run),role
        self.lock,self.primary_lock,self.guard,self.validate=lock,primary_lock,guard,validate
        need(role in ('primary','actor') and self.root.is_absolute() and self.root.resolve()==self.root and self.root.is_dir()
            and type(paths) is list and 1<=len(paths)<=256 and all(isinstance(path,PrivateFeatureState) for path in paths)
            and len({str(path.path) for path in paths})==len(paths))
        self.paths=paths;self.previous=store.read();self.state=None
        if self.previous is not None:self.state=self.decode(self.previous)
    def envelope(self,state):return dict(iosEmoteFinalArchiveVersion=VERSION,runId=self.run,role=self.role,binding=self.binding,
        artifactRoot=str(self.root),paths=[str(path.path) for path in self.paths],payload=pack([state]))
    def record_store(self,index):
        need(integer(index,1,len(self.paths)));return PrivateFeatureState(self.root/('emote-final-'+self.run+'-'+self.role+'-'+str(index)+'.json'))
    def copy(self,ref):
        exact(ref,{'index','sha256'});value=self.record_store(ref['index']).read();need(value is not None and digest(value)==ref['sha256'])
        exact(value,{'iosEmoteFinalCopyVersion','runId','role','binding','index','path','payload'})
        need(type(value['iosEmoteFinalCopyVersion']) is int and value['iosEmoteFinalCopyVersion']==VERSION and value['runId']==self.run and value['role']==self.role
            and same(value['binding'],self.binding) and value['index']==ref['index'] and value['path']==str(self.paths[ref['index']-1].path))
        rows=unpack(value['payload']);need(len(rows)==1 and (rows[0] is None or type(rows[0]) is dict));return rows[0]
    def copies(self):return {str(self.paths[ref['index']-1].path):self.copy(ref) for ref in self.state['records']}
    def decode(self,value):
        exact(value,{'iosEmoteFinalArchiveVersion','runId','role','binding','artifactRoot','paths','payload'});rows=unpack(value['payload'])
        need(len(rows)==1 and same(value,self.envelope(rows[0])));state=rows[0]
        exact(state,{'phase','phaseOriginal','hashes','records','pending','retired'})
        need(state['phase'] in ('freezing','validated','retiring','complete') and type(state['hashes']) is list and len(state['hashes'])==len(self.paths)
            and type(state['records']) is list and len(state['records'])<=len(self.paths)
            and type(state['retired']) is int and 0<=state['retired']<=len(self.paths))
        status=state['phaseOriginal'];phase_packet(status,run=self.run,area='emotes',request=status['requestId'],epoch=status['capturedEpochMs']);need(not status['active'])
        for index,ref in enumerate(state['records'],1):need(ref['index']==index and digest(self.copy(ref))==state['hashes'][index-1])
        if state['pending'] is not None:
            p=state['pending'];exact(p,{'index','value'});need(state['phase']=='freezing' and p['index']==len(state['records'])+1
                and digest(p['value'])==state['hashes'][p['index']-1])
        if state['phase']!='freezing':need(len(state['records'])==len(self.paths) and state['pending'] is None)
        if state['phase'] in ('freezing','validated'):need(state['retired']==0)
        if state['phase']=='complete':need(state['retired']==len(self.paths))
        return deepcopy(state)
    def bound(self):
        self.lock.assert_held();self.primary_lock.assert_held();need(self.guard() is not False)
        actual=self.store.read()
        if not same(actual,self.previous):need(self.state is not None and same(actual,self.envelope(self.state)));self.previous=deepcopy(actual)
    def save(self):
        self.bound();value=self.envelope(self.state);self.store.write(value,self.previous);need(same(self.store.read(),value));self.previous=deepcopy(value)
    def begin(self,phase):
        self.bound();need(self.state is None)
        phase_packet(phase,run=self.run,area='emotes',request=phase['requestId'],epoch=phase['capturedEpochMs']);need(not phase['active'])
        self.state=dict(phase='freezing',phaseOriginal=deepcopy(phase),hashes=[digest(path.read()) for path in self.paths],records=[],pending=None,retired=0);self.save()
    def freeze(self):
        self.bound();need(self.state is not None)
        if self.state['phase']!='freezing':return
        while len(self.state['records'])<len(self.paths):
            index=len(self.state['records'])+1
            if self.state['pending'] is None:
                value=self.paths[index-1].read();need(digest(value)==self.state['hashes'][index-1])
                self.state['pending']=dict(index=index,value=value);self.save()
            pending=self.state['pending'];value=dict(iosEmoteFinalCopyVersion=VERSION,runId=self.run,role=self.role,binding=self.binding,
                index=index,path=str(self.paths[index-1].path),payload=pack([pending['value']]))
            store=self.record_store(index);old=store.read()
            if old is None:store.write(value,None)
            else:need(same(old,value))
            ref=dict(index=index,sha256=digest(value));need(same(self.copy(ref),pending['value']))
            self.state['records'].append(ref);self.state['pending']=None;self.save()
        self.validate(self.copies());self.state['phase']='validated';self.save()
    def retire(self):
        self.bound();self.freeze();need(self.state['phase'] in ('validated','retiring','complete'))
        self.validate(self.copies())
        if self.state['phase']=='complete':
            need(all(path.read() is None for path in self.paths));return {'performed':True}
        self.state['phase']='retiring';self.save()
        while self.state['retired']<len(self.paths):
            index=self.state['retired'];path=self.paths[index];original=self.copy(self.state['records'][index])
            current=path.read();need(current is None or same(current,original))
            self.validate(self.copies());self.bound()
            if current is not None:path.discard(current)
            need(path.read() is None);self.state['retired']+=1;self.save()
        self.state['phase']='complete';self.save();return {'performed':True}
