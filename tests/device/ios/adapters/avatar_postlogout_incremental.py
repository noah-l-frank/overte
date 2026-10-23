"""One owned pending record between complete postlogout decoder boundaries.

This admission helper supplies no facts or freshness. It binds actual immutable
old originals, exact old rows and complete owner context while the existing
decoder validates only the current pending record. Historical/proof paths never
use it, and a failed round cannot be resumed through this in-memory helper.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import os
from pathlib import Path
import stat
from adapters.native_feature_observation import exact,integer,need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.original_file_reads import record as actual_read,scope
from adapters.original_frame_store import OriginalFrameStore
from adapters.script_feature.history import canonical,same,unpack
from ios.adapters.avatar_record_cache import AvatarRecordCache
from ios.adapters.emote_original_lease import EmoteOriginalLease


class AvatarPendingRound:
    def __init__(self,owner):
        self.owner=owner;need(not owner.historical and owner.state['pending'] is None)
        self.context=self.owner_context();self.rows=canonical(owner.state['rows']);self.first=owner.state['nextSegment']
        self.last_pending=None;self.last_segment=self.first;self.metadata=canonical(owner.previous)
        self.missing=set();self.paths=set();self.previous_model=None
        with scope(fresh=True) as first:
            self.entry();self.declared()
        self.paths.update(set(first)-{owner.store.path});self.signatures=self.sign(self.paths);AvatarRecordCache.absent(self.missing)
        original_paths=set(self.paths);original_missing=set(self.missing)
        with scope(fresh=True) as second:
            self.entry();self.declared()
        self.paths.update(set(second)-{owner.store.path})
        need(self.paths==original_paths and self.missing==original_missing and self.sign(self.paths)==self.signatures)
        self.guard()

    def owner_context(self):
        o=self.owner
        def original(store):
            return dict(root=str(store.root),namespace=store.namespace,schema=store.schema_prefix,kind=store.kind,
                binding=store.binding,runId=store.run,role=store.role,guard=id(store.guard),intent=id(store.intent))
        return canonical(dict(binding=o.binding,runId=o.run,role=o.role,subject=o.subject,root=str(o.root),
            store=str(o.store.path),inputs=o.inputs,lock=str(o.lock.path),lockObject=id(o.lock),
            guard=id(o.guard),epoch=id(o.epoch_ms),monotonic=id(o.monotonic),historical=o.historical,
            accounts=id(o.accounts_factory),model=id(o.model_factory),originals=original(o.originals),
            segments=original(o.segments.store),parentKey=o.segments.parent_key,bodyKey=o.segments.body_key))

    @staticmethod
    def sign(paths):
        need(type(paths) is set and len(paths)<=2048 and all(isinstance(path,Path) and path.is_absolute() for path in paths))
        if not paths:return {}
        try:
            parents={path.parent for path in paths};before={};result={}
            for parent in parents:
                need(isinstance(parent,Path));PrivateFeatureState(parent/'avatar-original-inventory.json')._parent()
                before[parent]=EmoteOriginalLease.signature(parent.lstat())
            for path in paths:
                need(isinstance(path,Path) and path.is_absolute())
                value=path.lstat();need(stat.S_ISREG(value.st_mode) and value.st_uid==os.geteuid()
                    and value.st_nlink==1 and stat.S_IMODE(value.st_mode)==0o600)
                result[path]=EmoteOriginalLease.signature(value)
            # Only this synchronous inventory shares ancestry work. No parent
            # qualification survives a write, use, next inventory or round.
            for parent in parents:
                PrivateFeatureState(parent/'avatar-original-inventory.json')._parent()
                need(EmoteOriginalLease.signature(parent.lstat())==before[parent])
            return result
        except OSError:raise NativeUIError('Original Avatar file inventory is unavailable') from None

    def entry(self):
        o=self.owner;need(self.owner_context()==self.context and canonical(o.previous)==self.metadata)
        o.bound()
        decoded=dict(rows=[],pending=None,nextSegment=1) if o.previous is None else o.parse(o.previous)
        decoded.setdefault('nextSegment',1)
        need(same(decoded,o.state) and decoded['pending'] is None and canonical(decoded['rows'])==self.rows
            and decoded['nextSegment']==self.first)

    def original(self,store,reference):
        if reference is None:return
        store.original(reference);path=store.path(reference)
        if reference['phase']=='planned':self.missing.add(path);need(not os.path.lexists(path));return
        fd=os.open(path,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0)|getattr(os,'O_NONBLOCK',0))
        with os.fdopen(fd,'rb') as stream:
            store.file(path,stream.fileno(),reference);raw=stream.read(reference['bytes']+1);store.file(path,stream.fileno(),reference)
        need(len(raw)<=reference['bytes'])
        if reference['phase']=='saved':need(len(raw)==reference['bytes'] and hashlib.sha256(raw).hexdigest()==reference['sha256'])
        self.paths.add(path);actual_read(path)

    def declared(self):
        o=self.owner
        account=OriginalFrameStore(o.root,o.binding,o.run,o.role,lambda:True,lambda *_:False,
            namespace='avatar-'+o.subject+'-account-read',schema_prefix='avatar'+o.subject.capitalize()+'AccountRead',monotonic=o.monotonic)
        for row in o.state['rows']:
            partial=o.row_partial(row)
            if 'partsCarrier' in row:
                for parent in [*o.part_parents(partial),row['partsCarrier']]:
                    for ref in parent['chunks']:self.original(o.segments.store,ref)
            self.original(o.originals,row['original'])
            parts=o.row_parts(row)
            if 'model' in parts:self.previous_model=deepcopy(parts['model'])
            for name in ('before','after'):
                if name not in parts:continue
                nested=unpack(parts[name]['owner']['payload']);need(len(nested)==1 and nested[0]['pending'] is None)
                for native in nested[0]['rows']:self.original(account,native['original'])

    def guard(self):
        o=self.owner;need(self.owner_context()==self.context and canonical(o.state['rows'])==self.rows)
        o.lock.assert_held();o.store._parent();PrivateFeatureState(o.root/'avatar-pending-round-boundary.json')._parent()
        need(self.sign(set(self.signatures))==self.signatures);AvatarRecordCache.absent(self.missing)
        for path in self.signatures:actual_read(path)

    @staticmethod
    def reference(before,after):
        if before is None:need(after is None or after['phase']=='planned');return
        need(after is not None)
        need(all(same(before[key],after[key]) for key in before if key not in ('phase','file')))
        if before['phase']==after['phase']:need(same(before,after));return
        need((before['phase'],after['phase']) in (('planned','opened'),('opened','saved')))
        if before['file'] is not None:need(same(before['file'],after['file']))

    def parent(self,before,after):
        o=self.owner
        if before is None:
            need(after is None or not after['complete'] and after['first']==self.last_segment
                and (not after['chunks'] or len(after['chunks'])==1 and after['chunks'][0]['phase']=='planned'))
            return
        need(after is not None);o.segments.parent(before);o.segments.parent(after)
        need(all(same(before[key],after[key]) for key in before if key not in ('chunks','complete')))
        a,b=before['chunks'],after['chunks'];need(len(a)<=len(b)<=len(a)+1)
        for index,reference in enumerate(a):self.reference(reference,b[index])
        if len(b)>len(a):need(b[-1]['phase']=='planned' and all(ref['phase']=='saved' for ref in a))
        if before['complete']:need(after['complete'])

    def transition(self,p):
        old=self.last_pending
        if old is None:
            need(p==dict(index=len(self.owner.state['rows'])+1,parts={},original=None,acquisition=None,
                partsStorageVersion=1,partialOriginal=None,orphanPartials=[]));return
        need(p['index']==old['index'] and p['partsStorageVersion']==old['partsStorageVersion']
            and p['partialOriginal'] is None and old['partialOriginal'] is None and not p['orphanPartials'] and not old['orphanPartials'])
        a,b=old['parts'],p['parts'];need(set(a)<=set(b) and len(set(b)-set(a))<=1)
        changed=sum(key not in a or not same(a[key],b[key]) for key in b)
        changed+=int(not same(old['original'],p['original']))+int(not same(old['acquisition'],p['acquisition']))
        need(changed<=1)
        for key in ('modelQuery','modelAcquisition'):
            if key in a:need(same(a[key],b[key]))
        for key in ('before','model','after'):
            if key in b:self.parent(a.get(key),b[key])
        if 'clocks' in a:
            need('clocks' in b and len(a['clocks'])<=len(b['clocks'])<=len(a['clocks'])+1)
            for index,row in enumerate(a['clocks']):
                need(same(row['query'],b['clocks'][index]['query']));self.parent(row['packet'],b['clocks'][index]['packet'])
            if len(b['clocks'])>len(a['clocks']):
                need(b['clocks'][-1]['packet'] is None and all(row['packet'] is not None and row['packet']['complete'] for row in a['clocks']))
        elif 'clocks' in b:need(b['clocks']==[])
        if old['acquisition'] is not None:need(same(old['acquisition'],p['acquisition']))
        self.reference(old['original'],p['original'])

    def validate(self,value):
        o=self.owner;self.guard();need(canonical(o.previous)==self.metadata);o.bound()
        need(type(value['iosAvatarPostLogoutReadsVersion']) is int and value['iosAvatarPostLogoutReadsVersion']==2)
        state=o.state;exact(state,{'rows','pending','nextSegment'});p=state['pending'];need(p is not None)
        exact(p,{'index','parts','original','acquisition','partsStorageVersion','partialOriginal','orphanPartials'})
        need(type(p['partsStorageVersion']) is int and p['partsStorageVersion']==1 and p['partialOriginal'] is None and p['orphanPartials']==[]
            and integer(p['index'],1,64) and p['index']==len(state['rows'])+1 and integer(state['nextSegment'],self.first,1025))
        self.transition(p);o.part(o.row_parts(p),self.previous_model)
        if p['original'] is not None:
            o.originals.original(p['original']);need(p['original']['index']==p['index'] and p['acquisition'] is not None);o.native_file(p['original'])
        if p['acquisition'] is not None:
            o.acquisition(p['acquisition']);need(set(o.row_parts(p))=={'before','modelQuery','model','modelAcquisition','clocks','after'})
        seen={}
        for parent in o.part_parents(p):
            o.segments.parent(parent)
            for ref in parent['chunks']:
                need(ref['index']>=self.first)
                identity=canonical({key:parent[key] for key in parent if key not in ('chunks','complete')})
                if ref['index'] in seen:need(same(seen[ref['index']][0],ref) and seen[ref['index']][1]==identity)
                else:seen[ref['index']]=(deepcopy(ref),identity)
        need(set(seen)==set(range(self.first,state['nextSegment'])) and self.last_segment<=state['nextSegment']<=self.last_segment+1)
        self.guard()

    def accepted(self):
        self.guard();self.last_pending=deepcopy(self.owner.state['pending']);self.last_segment=self.owner.state['nextSegment']
        self.metadata=canonical(self.owner.previous)

    def transport_guard(self):
        self.guard();need(canonical(self.owner.previous)==self.metadata and same(self.owner.state['pending'],self.last_pending))
        self.owner.bound();return True
