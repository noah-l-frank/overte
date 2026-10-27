"""Parent intent for the original explicit marker child, never image success.

The child keeps its actual normal input, partial-read, callback/weak and quiet
ownership. This wrapper neither copies that implementation nor retires Model,
peer, cache, renderer or OS responsibility when its marker alone is released.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import time
from adapters.native_feature_observation import exact,need
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.script_feature.history import pack,unpack,same
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.contract import identifier
from ios.adapters.assets_budget import operation
from ios.adapters.create_marker_scope import CreateMarkerScope,marker_name
from ios.adapters.create_marker_recovery import IOSCreateMarkerRecovery
from ios.adapters.create_marker_identity import PreparedCreateMarker

VERSION=1


class OwnedAssetsMarker:
    @classmethod
    def from_archive(cls,value,store,*,artifact_root,binding,run,role,fixture_url,ticket,lock):
        """Independently authorized paths/context; no live constructor or SDK.

        This is a historical parent lease, not a current marker or pixel
        observation. Marker/Model/OS responsibility must stay separate.
        """
        need(isinstance(store,PrivateFeatureState) and isinstance(lock,ScriptSourceLock) and role in ('primary','actor'))
        lock.assert_held();binding=deepcopy(context(binding));identifier(run);identifier(ticket)
        need(store.path.name=='ios-assets-marker-'+run+'-'+role+'.json' and lock.path==store.path.with_name('script-feature-sources.lock')
            and same(store.read(),value))
        scope=object.__new__(CreateMarkerScope);scope.root=Path(artifact_root);scope.binding=binding;scope.run,scope.role=run,role
        scope.namespace,scope._version,scope.lock='assets',3,lock;scope.fixture_url,scope.ticket=fixture_url,ticket
        scope.store=PrivateFeatureState(store.path.with_name(marker_name(role,'assets')));scope.failed=True
        owner=object.__new__(cls);owner.scope,owner.store,owner.lock,owner.run,owner.role=scope,store,lock,run,role
        owner.monotonic=time.monotonic;owner.previous=deepcopy(value);owner.state=owner.decode(value);return owner

    def __init__(self,scope,store):
        need(isinstance(scope,CreateMarkerScope) and getattr(scope,'namespace',None)=='assets' and scope._version==3
            and scope.store.path.name==marker_name(scope.role,'assets')
            and scope.files.store.path==scope.marker_store('files').path
            and isinstance(store,PrivateFeatureState) and store.path.parent==scope.store.path.parent
            and store.path.name=='ios-assets-marker-'+scope.run+'-'+scope.role+'.json')
        self.scope,self.store,self.lock,self.run,self.role=scope,store,scope.lock,scope.run,scope.role
        self.monotonic=scope.monotonic;self.lock.assert_held();self.previous=store.read();self.state=None
        if self.previous is not None:self.state=self.decode(self.previous)

    def identity(self):
        PrivateFeatureState(self.scope.root/'assets-marker-root-boundary.json')._parent();info=self.scope.root.stat()
        return dict(device=info.st_dev,inode=info.st_ino)

    def archive(self,value,*,ready=False):
        result=CreateMarkerScope.archive(value,root=self.scope.root,binding=self.scope.binding,run=self.run,role=self.role,
            lock=self.lock,namespace='assets',require_ready=ready)
        need(result.fixture_url==self.scope.fixture_url and result.ticket==self.scope.ticket)
        # Completed child frames do not replace abandoned read originals. The
        # original recovery decoder reopens its exact records and any retained
        # byte prefix without acquiring a live SDK or replaying that read.
        result.store=self.scope.store;IOSCreateMarkerRecovery(result)
        return result

    def prefix(self,before,after):
        need(after is not None);new=self.archive(after)
        if before is None:return new
        old=self.archive(before);need(len(old.frames)<=len(new.frames) and same(old.frames,new.frames[:len(old.frames)]))
        left,right=old.state,new.state;need(len(left['operations'])<=len(right['operations']))
        for a,b in zip(left['operations'],right['operations']):
            need(a['label']==b['label'] and (same(a,b) or a['phase']=='issued' and b['phase']=='returned'))
        replacement=(self.state['pending']=='cleanup' and left['phase']=='ready' and left['cleanupMode']=='full'
            and left['webAdmission'] is None and right['cleanupMode']=='partial-execution'
            and left['admission'] is not None and right['admission'] is not None
            and all(same(left['admission'][key],right['admission'][key]) for key in ('manager','code','sourceUrl','marker'))
            and right['admissionFrame']>left['admissionFrame'] and right['webAdmission']==right['admissionFrame'])
        for key in ('baseline','fileOwnership','directory','loadBarrier','admission','admissionFrame','webAdmission','stopBarrier'):
            if replacement and key in ('admission','admissionFrame'):continue
            if left[key] is not None:need(same(left[key],right[key]))
        return new

    def envelope(self):
        return dict(iosAssetsMarkerOwnerVersion=VERSION,binding=self.scope.binding,runId=self.run,role=self.role,
            artifactRoot=str(self.scope.root),artifactRootIdentity=self.identity(),fixtureUrl=self.scope.fixture_url,initialTicket=self.scope.ticket,
            childFile=self.scope.store.path.name,payload=pack([self.state]))

    def decode(self,value):
        exact(value,{'iosAssetsMarkerOwnerVersion','binding','runId','role','artifactRoot','artifactRootIdentity','fixtureUrl','initialTicket','childFile','payload'})
        need(type(value['iosAssetsMarkerOwnerVersion']) is int and value['iosAssetsMarkerOwnerVersion']==VERSION
            and same(value['binding'],self.scope.binding) and value['runId']==self.run and value['role']==self.role
            and value['artifactRoot']==str(self.scope.root) and same(value['artifactRootIdentity'],self.identity())
            and value['fixtureUrl']==self.scope.fixture_url and value['initialTicket']==self.scope.ticket
            and value['childFile']==self.scope.store.path.name)
        rows=unpack(value['payload']);need(len(rows)==1);state=rows[0];exact(state,{'phase','pending','child'})
        need(state['phase'] in ('reserved','preparing','ready','cleaning','released') and state['pending'] in (None,'prepare','render','cleanup'))
        child=None if state['child'] is None else self.archive(state['child'])
        if state['phase']=='reserved':need(state['pending'] is None and child is None)
        if state['pending'] in ('prepare','render'):need(state['phase']=='preparing')
        if state['pending']=='cleanup':need(state['phase']=='cleaning')
        if state['phase']=='cleaning':need(state['pending']=='cleanup')
        if state['phase']=='preparing' and state['pending'] is None:
            need(child is not None and child.state['phase']=='ready' and child.state['cleanupMode']=='full')
        if state['pending']=='render':need(child is not None and child.state['phase']=='ready' and child.state['cleanupMode']=='full')
        if state['phase']=='ready':need(state['pending'] is None and child is not None);self.archive(state['child'],ready=True)
        if state['phase']=='released':need(state['pending'] is None and child is not None and child.state['phase']=='released')
        if state['pending'] is None:need(same(self.scope.store.read(),state['child']))
        return state

    def guard(self):
        self.lock.assert_held();self.scope.bound();need(same(self.store.read(),self.previous))
        if self.state is not None:self.decode(self.previous)
        return True

    def save(self):
        self.lock.assert_held();need(same(self.store.read(),self.previous));value=self.envelope();self.decode(value)
        self.store.write(value,self.previous);self.previous=deepcopy(value)

    @operation
    def reserve(self):
        self.guard();need(self.state is None and self.scope.previous is None and self.scope.state['phase']=='new'
            and self.scope.files.store.read() is None and self.scope.marker_store('script').read() is None and self.scope.marker_store('recovery').read() is None)
        prefixes=('assets-marker-frame-inputs-'+self.run+'-'+self.role+'-',
            'assets-marker-index-inputs-'+self.run+'-'+self.role+'-','assets-marker-read-abandoned-'+self.run+'-'+self.role+'-')
        entries=list(self.scope.root.iterdir());need(len(entries)<=4096 and not any(path.name.startswith(prefixes) for path in entries))
        self.state=dict(phase='reserved',pending=None,child=None);self.save()

    def adopt(self):
        current=self.scope.store.read()
        if current is None:need(self.state['child'] is None);return None
        self.prefix(self.state['child'],current);self.state['child']=deepcopy(current);return self.archive(current)

    def complete(self,label,child):
        if child is None:return False
        if label=='prepare':return child.state['phase']=='ready' and child.state['cleanupMode']=='full'
        if label=='render':return child.state['phase']=='ready' and child.state['webAdmission'] is not None
        return child.state['phase']=='released'

    def perform(self,label,function):
        self.guard();need(self.state is not None and self.state['pending'] in (None,label))
        if self.state['pending'] is None:
            self.state.update(phase='cleaning' if label=='cleanup' else 'preparing',pending=label);self.save()
        child=self.adopt()
        if not self.complete(label,child):
            try:function()
            except BaseException as primary:
                try:self.adopt();self.save()
                except BaseException as secondary:primary.add_note('Retaining original Assets marker child also failed: '+type(secondary).__name__)
                raise
            child=self.adopt();need(self.complete(label,child))
        self.state['pending']=None
        self.state['phase']='released' if label=='cleanup' else 'ready' if label=='render' else 'preparing';self.save()

    @operation
    def prepare(self):
        self.guard();need(self.state is not None and self.state['phase'] in ('reserved','preparing','ready'))
        if self.state['phase']!='ready':
            if self.state['pending']!='render':self.perform('prepare',self.scope.prepare)
            self.perform('render',self.scope.admit_rendered)
        return self.prepared()

    def prepared(self):
        self.guard();need(self.state is not None and self.state['phase']=='ready')
        child=self.archive(self.state['child'],ready=True);state=child.state
        before=child.frames[state['baseline']-1];after=child.frames[state['admissionFrame']-1]
        return PreparedCreateMarker(child.binding,child.run,child.fixture_url,before=before['create'],after=after['create'],
            scripts=after['world']['source']['scriptOriginal'],files=state['fileOwnership'],directory=state['directory'],
            after_epoch=state['loadBarrier'],domain_before=before['world'],domain_after=after['world'])

    @operation
    def cleanup(self):
        self.guard();need(self.state is not None)
        if self.state['pending'] in ('prepare','render'):
            # The issued original child owns any uncertain load/read. Switch
            # only the parent cleanup intent; the child resolves its actual
            # callbacks/returns and never replays that mutating command.
            self.adopt();self.state.update(phase='cleaning',pending='cleanup');self.save()
        if self.state['phase']!='released':self.perform('cleanup',self.scope.cleanup)
        return dict(performed=True)
