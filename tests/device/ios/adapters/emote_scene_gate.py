"""Private two-role scene preconditions, bound to actual original owners.

This channel carries input ordering metadata. It has no HTTP authority and
publishes no feature projection. Waiting never acquires either SDK lock.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import os
import time
from pathlib import Path
from adapters.native_feature_observation import exact,integer,need
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.normal_ui import NativeUIError
from adapters.original_file_reads import record as record_original_read
from adapters.original_frame_store import OriginalFrameStore
from adapters.script_feature.history import pack,unpack,same
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.contract import identifier
from ios.adapters.emote_native_prefix import follow
from ios.adapters.peer_admission import validate as admission_original
from ios.adapters.emote_scene_proof import validate as scene_original,ack as ack_original
from ios.adapters.emote_original_lease import EmoteOriginalLease

VERSION=1
STAGES=('initial','scene-retired')


class IOSEmoteSceneGate:
    @classmethod
    def archive(cls,value,*,store,root,binding,run,role,instance,admission,peer_store,lock,primary_lock,validate_original=scene_original,validate_ack=ack_original):
        class Frozen(PrivateFeatureState):
            def read(self):return deepcopy(value)
            def write(self,*_args):need(False)
        result=cls(Frozen(store.path),root,binding,run,role,instance,admission,peer_store,lock,primary_lock,lambda:True,
            check=lambda:None,monotonic=time.monotonic,validate_original=validate_original,validate_ack=validate_ack)
        result.historical=True;return result

    def __init__(self,store,root,binding,run,role,instance,admission,peer_store,lock,primary_lock,guard,*,check,monotonic,validate_original=scene_original,validate_ack=ack_original):
        need(isinstance(store,PrivateFeatureState) and isinstance(peer_store,PrivateFeatureState)
            and isinstance(lock,ScriptSourceLock) and isinstance(primary_lock,ScriptSourceLock)
            and role in ('primary','actor') and all(callable(fn) for fn in (guard,check,monotonic,validate_original,validate_ack)))
        self.store,self.root,self.binding,self.run,self.role,self.instance=store,Path(root),deepcopy(context(binding)),identifier(run),role,identifier(instance)
        self.admission=deepcopy(admission);self.peer_binding=admission_original(admission,binding);self.peer_role='actor' if role=='primary' else 'primary'
        self.peer_store,self.lock,self.primary_lock,self.guard=peer_store,lock,primary_lock,guard
        self.check,self.monotonic,self.validate_original,self.validate_ack=check,monotonic,validate_original,validate_ack
        self.historical=False;self.replayed={};self.foreign_leases=[];self.previous=store.read();self.state=dict(own=[],peer=[],abandoned=[],pending=None,serial=0)
        self.files=self.file_owner(self.root,self.binding,self.role,self.intent)
        if self.previous is not None:self.state=self.decode(self.previous)

    def file_owner(self,root,binding,role,intent):
        return OriginalFrameStore(root,binding,self.run,role,lambda:True,intent,namespace='emote-scene-ready',schema_prefix='emoteSceneReady',
            kind='inputs',monotonic=self.monotonic)
    def envelope(self,state):
        return dict(iosEmoteSceneGateVersion=VERSION,runId=self.run,role=self.role,binding=self.binding,artifactRoot=str(self.root),
            phaseInstance=self.instance,peerAdmission=self.admission,peerStatePath=str(self.peer_store.path),payload=pack([state]))
    def bound(self):self.lock.assert_held();self.check();need(not self.historical and self.guard() is not False and same(self.store.read(),self.previous))
    def save(self):
        self.bound();value=self.envelope(self.state);self.store.write(value,self.previous);need(same(self.store.read(),value));self.previous=deepcopy(value)
    def intent(self,event,original):
        need(event=='original' and self.state['pending'] is not None);self.files.original(original)
        self.state['pending']['original']=deepcopy(original);self.save();return True
    def wrap(self,kind,stage,ticket,original):
        need(kind in ('own','peer') and stage in STAGES);identifier(ticket)
        return dict(iosEmoteSceneReadyVersion=VERSION,runId=self.run,role=self.role,binding=self.binding,phaseInstance=self.instance,
            kind=kind,stage=stage,ticket=ticket,original=deepcopy(original))
    def header(self,value,*,binding,role):
        exact(value,{'iosEmoteSceneReadyVersion','runId','role','binding','phaseInstance','kind','stage','ticket','original'})
        need(type(value['iosEmoteSceneReadyVersion']) is int and value['iosEmoteSceneReadyVersion']==VERSION
            and value['runId']==self.run and value['role']==role and same(value['binding'],binding) and value['phaseInstance']==self.instance
            and value['kind'] in ('own','peer') and value['stage'] in STAGES);identifier(value['ticket']);return value
    def own_original(self,value,*,root=None,binding=None,role=None,state_root=None):
        binding=self.binding if binding is None else binding;role=self.role if role is None else role
        root=self.root if root is None else root;state_root=self.store.path.parent if state_root is None else state_root
        self.header(value,binding=binding,role=role);need(value['kind']=='own')
        return self.validate_original(value['original'],stage=value['stage'],root=root,binding=binding,run=self.run,role=role,
            instance=self.instance,ticket=value['ticket'],state_root=state_root,lock=self.lock)
    def peer_envelope(self,value):
        exact(value,{'iosEmoteSceneGateVersion','runId','role','binding','artifactRoot','phaseInstance','peerAdmission','peerStatePath','payload'})
        need(type(value['iosEmoteSceneGateVersion']) is int and value['iosEmoteSceneGateVersion']==VERSION and value['runId']==self.run
            and value['role']==self.peer_role and same(value['binding'],self.peer_binding) and value['phaseInstance']==self.instance
            and Path(value['peerStatePath'])==self.store.path)
        need(same(admission_original(value['peerAdmission'],self.peer_binding),self.binding))
        root=Path(value['artifactRoot']);need(root.is_absolute() and root.resolve()==root and root!=self.root)
        rows=unpack(value['payload']);need(len(rows)==1);state=rows[0];self.structure(state)
        return root,state
    def read_peer(self,snapshot,reference):
        root,state=self.peer_envelope(snapshot);need(reference in state['own']);lease=EmoteOriginalLease(root,[])
        files=self.file_owner(root,self.peer_binding,self.peer_role,lambda *_:need(False));value=files.read(reference)
        actual=self.own_original(value,root=root,binding=self.peer_binding,role=self.peer_role,state_root=self.peer_store.path.parent)
        lease.guard();self.foreign_leases.append(lease);return value,actual
    def original(self,reference):
        value=self.files.read(reference);self.header(value,binding=self.binding,role=self.role)
        if value['kind']=='own':actual=self.own_original(value)
        else:
            body=value['original'];exact(body,{'snapshot','reference','ack'});other,actual=self.read_peer(body['snapshot'],body['reference'])
            actual['ownEndpoint']=self.validate_ack(body['ack'],root=self.root,binding=self.binding,run=self.run,role=self.role,state_root=self.store.path.parent,lock=self.lock)
            need(other['stage']==value['stage'] and other['ticket']==value['ticket'])
        return value,actual
    @staticmethod
    def structure(state):
        exact(state,{'own','peer','abandoned','pending','serial'})
        need(integer(state['serial'],0,1024) and all(type(state[k]) is list and len(state[k])<=512 for k in ('own','peer','abandoned')))
    def partial(self,original):
        self.files.original(original);path=self.files.path(original)
        if original['phase']=='planned':need(not path.exists());return None
        descriptor=os.open(path,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0)|getattr(os,'O_NONBLOCK',0))
        with os.fdopen(descriptor,'rb') as stream:
            self.files.file(path,stream.fileno(),original);raw=stream.read(original['bytes']+1);self.files.file(path,stream.fileno(),original)
        need(len(raw)<=original['bytes']);complete=len(raw)==original['bytes'] and hashlib.sha256(raw).hexdigest()==original['sha256']
        if original['phase']=='saved':need(complete)
        record_original_read(path)
        return dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),complete=complete)
    def decode(self,value):
        exact(value,set(self.envelope(self.state)));rows=unpack(value['payload']);need(len(rows)==1 and same(value,self.envelope(rows[0])))
        state=rows[0];self.structure(state);indices=[];replayed={};self.foreign_leases=[];lease=EmoteOriginalLease(self.root,[])
        for kind in ('own','peer'):
            prior=None;peer_prefix=None;prior_ack=None
            for ref in state[kind]:
                self.files.original(ref);indices.append(ref['index']);item,actual=self.original(ref);need(item['kind']==kind)
                replayed[ref['sha256']]=(deepcopy(item),deepcopy(actual))
                if prior is not None and not same(prior['nativeEndpoint'],actual['nativeEndpoint']):follow(prior['nativeEndpoint'],actual['nativeEndpoint'])
                if kind=='peer':
                    if prior_ack is not None:follow(prior_ack,actual['ownEndpoint'])
                    prior_ack=actual['ownEndpoint']
                if kind=='peer':
                    current=item['original']['snapshot'];_root,new=self.peer_envelope(current)
                    if peer_prefix is not None:
                        _oldroot,old=self.peer_envelope(peer_prefix)
                        need(_oldroot==_root and new['own'][:len(old['own'])]==old['own'] and len(new['own'])>=len(old['own']))
                    peer_prefix=current
                prior=actual
        for ref in state['abandoned']:
            exact(ref,{'index','kind','stage','ticket','original','footprint'});indices.append(ref['index'])
            need(ref['kind'] in ('own','peer') and ref['stage'] in STAGES);identifier(ref['ticket'])
            if ref['original'] is None:need(ref['footprint'] is None)
            else:need(same(ref['footprint'],self.partial(ref['original'])))
        pending=state['pending']
        if pending is not None:
            exact(pending,{'index','kind','stage','ticket','original'});indices.append(pending['index'])
            need(pending['kind'] in ('own','peer') and pending['stage'] in STAGES);identifier(pending['ticket'])
            if pending['original'] is not None:self.files.original(pending['original']);need(pending['original']['index']==pending['index'])
        need(sorted(indices)==list(range(1,state['serial']+1)));lease.guard()
        for foreign in self.foreign_leases:foreign.guard()
        self.replayed=replayed;self.replay_lease=lease;return deepcopy(state)
    def resolve(self):
        self.bound();pending=self.state['pending']
        if pending is None:return True
        original=pending['original']
        if original is None or original['phase']=='planned':return False
        footprint=self.partial(original)
        if not footprint['complete']:return False
        value,_actual=self.original(original);need(all(value[k]==pending[k] for k in ('kind','stage','ticket')))
        self.state[pending['kind']].append(deepcopy(original));self.state['pending']=None;self.save();return True
    def abandon(self):
        self.bound()
        if self.resolve():return True
        pending=self.state['pending'];original=pending['original'];footprint=None if original is None else self.partial(original)
        self.state['abandoned'].append(dict(pending,footprint=footprint));self.state['pending']=None;self.save();return True
    def retain(self,kind,stage,ticket,original):
        self.bound();need(self.resolve() and self.state['serial']<1024)
        value=self.wrap(kind,stage,ticket,original)
        if kind=='own':self.own_original(value)
        else:
            body=original;exact(body,{'snapshot','reference','ack'});other,_actual=self.read_peer(body['snapshot'],body['reference'])
            self.validate_ack(body['ack'],root=self.root,binding=self.binding,run=self.run,role=self.role,state_root=self.store.path.parent,lock=self.lock)
            need(other['stage']==stage and other['ticket']==ticket)
        for ref in reversed(self.state[kind]):
            old,_actual=self.original(ref)
            if (same(old,value) or kind=='peer' and old['original']['reference']==value['original']['reference']
                and old['original']['snapshot']['artifactRoot']==value['original']['snapshot']['artifactRoot']
                and same(old['original']['ack'],value['original']['ack'])):return deepcopy(ref)
        self.state['serial']+=1;self.state['pending']=dict(index=self.state['serial'],kind=kind,stage=stage,ticket=ticket,original=None);self.save()
        compact=self.files.write(self.state['serial'],value);original=self.files.expand(compact)
        need(self.resolve());return deepcopy(original)
    def candidate(self,stage,ticket,*,retired=False):
        """Read a peer's actual file while the caller holds neither SDK lock."""
        need(not self.historical and self.lock._owner is None and self.primary_lock._owner is None);self.check()
        need(type(retired) is bool)
        try:snapshot=self.peer_store.read()
        except NativeUIError:
            if not retired or self.peer_store.path.exists():raise
            snapshot=None
        if snapshot is None:
            if retired and stage=='scene-retired':
                for ref in reversed(self.state['peer']):
                    value=self.files.read(ref);self.header(value,binding=self.binding,role=self.role)
                    if value['stage']==stage and value['ticket']==ticket:
                        return {key:deepcopy(value['original'][key]) for key in ('snapshot','reference')}
            return None
        _root,state=self.peer_envelope(snapshot)
        # A candidate is merely input metadata until admit() replays its full
        # original under the caller's own source lease.
        for ref in reversed(state['own']):
            files=self.file_owner(_root,self.peer_binding,self.peer_role,lambda *_:need(False));value=files.read(ref)
            self.header(value,binding=self.peer_binding,role=self.peer_role);need(value['kind']=='own')
            if value['stage']==stage and value['ticket']==ticket:return dict(snapshot=deepcopy(snapshot),reference=deepcopy(ref))
        return None
    def admit(self,stage,ticket,candidate,ack):return self.retain('peer',stage,ticket,dict(candidate,ack=ack))
    def ready(self,stage,ticket):self.bound();return self.qualified(stage,ticket)
    def qualified(self,stage,ticket):
        self.lock.assert_held();own=[self.original(ref) for ref in self.state['own']];peer=[self.original(ref) for ref in self.state['peer']]
        left=[(ref,pair) for ref,pair in zip(self.state['own'],own) if pair[0]['stage']==stage and pair[0]['ticket']==ticket]
        right=[(ref,pair) for ref,pair in zip(self.state['peer'],peer) if pair[0]['stage']==stage and pair[0]['ticket']==ticket]
        need(left and right);a,b=left[-1],right[-1];follow(a[1][1]['nativeEndpoint'],b[1][1]['ownEndpoint'])
        old,new=a[1][1]['nativeEndpoint']['animation'],b[1][1]['ownEndpoint']['animation']
        need(new['overrideActive'] is False)
        if 'history' in old:need(new['history']['callSequence']==old['history']['callSequence'])
        return dict(own=deepcopy(a[0]),peer=deepcopy(b[0]),nativeEndpoint=deepcopy(b[1][1]['ownEndpoint']))
