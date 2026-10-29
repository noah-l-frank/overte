"""Independent paired postlogout originals and measured native quiet.

Scene/pixel retirement remains a separate original. This owner observes both
actual SDKs without requesting a World after the product resets NodeList.
It publishes nothing and never replays an input or an interrupted query.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
from pathlib import Path
from adapters.native_clock_join import digest
from adapters.native_feature_observation import exact,integer,need,number
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.original_file_reads import active as reading,scope as read_scope
from adapters.phase_retirement_publisher import PhaseRetirementPublisher
from adapters.script_feature.history import pack,unpack,same,canonical
from feature_journeys.contract import identifier
from ios.adapters.avatar_authority import AvatarAuthorityReader
from ios.adapters.avatar_postlogout_reads import IOSAvatarPostLogoutReads
from ios.adapters.avatar_postlogout_tail import IOSAvatarPostLogoutTail
from ios.adapters.avatar_pointers import IOSAvatarPointers
from ios.adapters.avatar_final_quiet import account_equal
from ios.adapters import world_web_keys
from ios.adapters.emote_native_prefix import follow
from ios.adapters.emote_original_lease import EmoteOriginalLease

VERSION=1
ROLES=('primary','actor')
_ROUND=ContextVar('ios_avatar_final_original_round',default=None)
_PREFIX_ROUND=ContextVar('ios_avatar_final_immutable_prefix_round',default=False)


@contextmanager
def validation_round():
    """One synchronous historical traversal, with no live-query authority."""
    if _ROUND.get() is not None:yield;return
    token=_ROUND.set({})
    try:
        yield
        for entry in _ROUND.get().values():entry.guard(finished=True)
    finally:_ROUND.reset(token)


def checked(function):
    @wraps(function)
    def call(*args,**kwargs):
        with validation_round():return function(*args,**kwargs)
    return call


@contextmanager
def immutable_prefix_round():
    """Only read-only Avatar witness decoding may share equal old groups.

    Each complete owner prefix is still parsed literally. No quiet/effect,
    source acquisition, publisher result or changing metadata enters this memo.
    The ordinary Final1/Final2 cache keeps its exact previous-envelope key.
    """
    token=_PREFIX_ROUND.set(True)
    try:
        with validation_round():yield
    finally:_PREFIX_ROUND.reset(token)


def group_context(owner,*,prefix=False):
    for lock in owner.locks.values():lock.assert_held()
    result=(type(owner),str(owner.root),str(owner.store.path),owner.run,owner.role,
        (type(owner.authority),id(owner.authority),owner.authority.run,type(owner.authority.client),id(owner.authority.client),owner.authority.client.url),
        tuple((role,id(owner.locks[role]),str(owner.locks[role].path)) for role in ROLES),
        canonical(dict(bindings=owner.bindings,inputs=owner.inputs)))
    if not prefix:return result+(canonical(owner.previous),)
    # A group depends on this exact immutable argument and these implementations,
    # not on later rows in another already parsed prefix of the same owner.
    methods=tuple((name,getattr(getattr(owner,name),'__func__',getattr(owner,name)))
        for name in ('_group','archives','component','input','record','components','component_prefix','envelope','parse','_parse'))
    children=tuple((cls,name,getattr(getattr(cls,name),'__func__',getattr(cls,name)))
        for cls,names in ((IOSAvatarPostLogoutReads,('archive','parse','proof','record')),
            (owner.Tail,('archive','parse','proof','record')),(IOSAvatarPointers,('archive','decode','original')))
        for name in names)
    if 'web' in owner.COMPONENTS:
        from ios.adapters.avatar_marker_web_receipts import IOSAvatarMarkerWebReceipts
        children+=tuple((IOSAvatarMarkerWebReceipts,name,getattr(getattr(IOSAvatarMarkerWebReceipts,name),'__func__',
            getattr(IOSAvatarMarkerWebReceipts,name))) for name in ('archive','parse','packet'))
    authority=getattr(owner.authority.validate,'__func__',owner.authority.validate)
    grammar=canonical(dict(version=owner.VERSION,components=owner.COMPONENTS,
        componentVersions=owner.COMPONENT_VERSIONS,tailReads=owner.TAIL_READS))
    return result+('immutable-prefix-v1',methods,children,authority,owner.Tail,grammar)


class _HistoricalGroup:
    """Already decoded original components, never a cached quiet verdict."""
    def __init__(self,owner,value,collector,*,prefix=False):
        need(owner.historical);self.prefix=prefix;self.owner,self.context,self.collector=owner,group_context(owner,prefix=prefix),collector
        self.owners={};self.watch(owner)
        roots={owner.root,owner.store.path.parent}
        for subject in ROLES:
            item=owner.input(subject);roots.add(Path(item['root']))
            roots.update(Path(path).parent for path in item['paths'].values())
        self.leases=[EmoteOriginalLease(root,[]) for root in sorted(roots)]
        with read_scope(fresh=True) as reads:self.parts=owner._group(value)
        self.pins={path:EmoteOriginalLease.signature(path.lstat()) for path in reads}
        self.guard()

    def watch(self,owner):
        if not self.prefix:return
        need(owner.historical and group_context(owner,prefix=self.prefix)==self.context)
        key=id(owner)
        if key not in self.owners:
            need(len(self.owners)<512);self.owners[key]=(owner,digest(owner.previous))
        expected_owner,original=self.owners[key]
        need(expected_owner is owner and digest(owner.previous)==original)
        if hasattr(owner,'state'):need(same(owner.envelope(owner.state),owner.previous))

    def guard(self,*,finished=False):
        owner=self.owner;need(owner.historical and group_context(owner,prefix=self.prefix)==self.context)
        for current,_original in tuple(self.owners.values()):self.watch(current)
        if finished:need(hasattr(owner,'state'))
        if hasattr(owner,'state'):need(same(owner.envelope(owner.state),owner.previous))
        for subject,parts in self.parts.items():
            for kind,version_key in owner.COMPONENT_VERSIONS.items():
                child=parts[kind];child.lock.assert_held();need(child.historical and same(child.store.read(),child.previous))
                need(child.lock is owner.locks[subject] and child.store.path==Path(owner.inputs[subject]['paths'][kind])
                    and child.root==Path(owner.inputs[subject]['root']) and child.run==owner.run and child.role==owner.role
                    and same(child.binding,owner.bindings[subject]))
                current=child.envelope(child.state) if version_key is None else child.envelope(child.state,version=child.previous[version_key])
                need(same(current,child.previous))
        for lease in self.leases:lease.guard()
        for path,pin in self.pins.items():
            PrivateFeatureState(path)._parent();need(EmoteOriginalLease.signature(path.lstat())==pin)

    def read(self,owner):
        self.watch(owner)
        self.guard()
        result={subject:{key:(value if key in self.owner.COMPONENTS else deepcopy(value)) for key,value in parts.items()}
            for subject,parts in self.parts.items()}
        self.guard()
        if self.collector is not None:self.collector.update(self.pins)
        return result


class Frozen(PrivateFeatureState):
    def __init__(self,path,value):super().__init__(path);self.value=deepcopy(value)
    def read(self):return deepcopy(self.value)
    def write(self,*_args,**_kwargs):need(False)
    def discard(self,*_args,**_kwargs):need(False)


class IOSAvatarFinal:
    VERSION=VERSION
    COMPONENTS=('post','tail','pointers')
    COMPONENT_VERSIONS=dict(post='iosAvatarPostLogoutReadsVersion',tail='iosAvatarPostLogoutTailVersion',pointers=None)
    TAIL_READS=(2,3)
    Tail=IOSAvatarPostLogoutTail
    def __init__(self,store,root,bindings,run,role,locks,guard,factory,authority,inputs,*,epoch_ms,monotonic,sleep):
        need(isinstance(store,PrivateFeatureState) and isinstance(authority,AvatarAuthorityReader) and authority.run==run
            and role in ROLES and all(callable(fn) for fn in (guard,factory,epoch_ms,monotonic,sleep)))
        exact(bindings,set(ROLES));exact(locks,set(ROLES));exact(inputs,set(ROLES))
        self.store,self.root,self.bindings,self.run,self.role,self.locks=store,Path(root),{k:context(v) for k,v in bindings.items()},identifier(run),role,locks
        need(store.path.name=='ios-avatar-'+role+'-final.json' and store.path.parent==locks[role].path.parent)
        self.guard,self.factory,self.authority,self.inputs=guard,factory,authority,deepcopy(inputs)
        self.epoch_ms,self.monotonic,self.sleep=epoch_ms,monotonic,sleep
        self.historical=False;self.previous=store.read();self.state=dict(rows=[],pending=None)
        self.bound()
        for subject in ROLES:self.input(subject)
        if self.previous is not None:self.state=self.parse(self.previous)

    def input(self,subject):
        value=self.inputs[subject];exact(value,{'root','paths','childRunId','fixtureUrl','ticket','baseline','logoutBefore'})
        identifier(value['childRunId']);identifier(value['ticket']);exact(value['baseline'],{'state','scripts','http'})
        exact(value['paths'],{'post','tail','pointers'})
        base=self.locks[subject].path.parent
        names=dict(post=self.role+'-'+subject+'-postlogout',tail=self.role+'-'+subject+'-postlogout-tail',pointers=self.role+'-pointers')
        need(all(Path(value['paths'][k])==base/('ios-avatar-'+v+'.json') for k,v in names.items()))
        return value

    def envelope(self,state):return dict(iosAvatarFinalVersion=self.VERSION,runId=self.run,role=self.role,bindings=self.bindings,
        artifactRoot=str(self.root),inputs=self.inputs,payload=pack([state]))
    def bound(self):
        need(not self.historical and self.guard() is not False)
        for lock in self.locks.values():lock.assert_held()
        need(same(self.store.read(),self.previous))
    def save(self):
        self.bound();value=self.envelope(self.state);self.parse(value);self.store.write(value,self.previous)
        need(same(self.store.read(),value));self.previous=deepcopy(value)
    def file(self,index):
        need(integer(index,1,128));return PrivateFeatureState(self.root/('avatar-final-'+self.run+'-'+self.role+'-'+str(index)+'.json'))
    def record(self,ref):
        exact(ref,{'index','sha256'});value=self.file(ref['index']).read();need(value is not None and digest(value)==ref['sha256'])
        exact(value,{'iosAvatarFinalOriginalVersion','runId','role','bindings','payload'})
        need(type(value['iosAvatarFinalOriginalVersion']) is int and value['iosAvatarFinalOriginalVersion']==self.VERSION
            and value['runId']==self.run and value['role']==self.role and same(value['bindings'],self.bindings))
        rows=unpack(value['payload']);need(len(rows)==1);return rows[0]

    def component(self,index,subject,kind,reference):
        need(integer(index,1,128) and subject in ROLES and kind in self.COMPONENTS)
        exact(reference,{'index','sha256'});need(reference['index']==index)
        path=self.root/('avatar-final-component-'+self.run+'-'+self.role+'-'+str(index)+'-'+subject+'-'+kind+'.json')
        value=PrivateFeatureState(path).read();need(value is not None and digest(value)==reference['sha256']);return value

    def retain_component(self,index,subject,kind,value):
        self.bound();p=self.state['pending'];need(p is not None and p['index']==index)
        key=subject+'-'+kind;ref=dict(index=index,sha256=digest(value))
        if key in p['components']:need(same(p['components'][key],ref))
        else:p['components'][key]=ref;self.save()
        store=PrivateFeatureState(self.root/('avatar-final-component-'+self.run+'-'+self.role+'-'+str(index)+'-'+subject+'-'+kind+'.json'))
        old=store.read()
        if old is None:store.write(value,None)
        else:need(same(old,value))
        self.component(index,subject,kind,ref);return ref

    def archives(self,subject,parts):
        self.locks[subject].assert_held();exact(parts,{'owners','rows'});exact(parts['owners'],{'post','tail','pointers'});exact(parts['rows'],{'post','tail','left','right'})
        original={kind:self.component(ref['index'],subject,kind,ref) for kind,ref in parts['owners'].items()}
        config=self.input(subject);shared=dict(root=Path(config['root']),binding=self.bindings[subject],run=self.run,role=self.role,lock=self.locks[subject])
        common=dict(child_run=config['childRunId'],fixture_url=config['fixtureUrl'],ticket=config['ticket'],logout_before=config['logoutBefore'],subject=subject)
        post=IOSAvatarPostLogoutReads.archive(original['post'],store=Frozen(config['paths']['post'],original['post']),
            baseline=config['baseline']['state'],historical_rows=getattr(self,'_postlogout_rows',None),**common,**shared)
        tail=self.Tail.archive(original['tail'],store=Frozen(config['paths']['tail'],original['tail']),
            baseline=config['baseline'],**common,**shared)
        pointer=IOSAvatarPointers.archive(original['pointers'],store=Frozen(config['paths']['pointers'],original['pointers']),**shared)
        need(all(owner.state['pending'] is None for owner in (post,tail,pointer)))
        need(integer(parts['rows']['post'],1,len(post.state['rows'])) and integer(parts['rows']['tail'],1,len(tail.state['rows'])))
        a,b=post.state['rows'][parts['rows']['post']-1],tail.state['rows'][parts['rows']['tail']-1];post.proof(a);proof=tail.proof(b)
        need(parts['rows']['left'] in pointer.state['records'] and parts['rows']['right'] in pointer.state['records'])
        need(proof['iosAvatarPostLogoutTailProofVersion'] in self.TAIL_READS)
        left,right=pointer.original(parts['rows']['left']),pointer.original(parts['rows']['right']);body=post.record(a);ui=tail.record(b['reference'])
        before=post.account(body['before']);after=post.account(body['after'])
        follow(left['clockJoin']['nativeAfter'],before);follow(after,ui['clockJoin']['nativeBefore']);follow(ui['clockJoin']['nativeAfter'],right['clockJoin']['nativeBefore'])
        return dict(post=post,tail=tail,pointers=pointer,model=body['model'],ui=ui,left=left,right=right,proof=proof)

    def group(self,value):
        if self.VERSION==2:
            from ios.adapters.avatar_final_pure_round import scope
            with scope(self,value):return self._checked_group(value)
        return self._checked_group(value)

    def _checked_group(self,value):
        current=_ROUND.get()
        if not self.historical or current is None:return self._group(value)
        collector=None
        if reading():
            with read_scope() as collector:pass
        prefix=_PREFIX_ROUND.get()
        key=(group_context(self,prefix=prefix),canonical(value),id(collector))
        if key not in current:
            need(len(current)<256);current[key]=_HistoricalGroup(self,value,collector,prefix=prefix)
        entry=current[key];need(entry.collector is collector);return entry.read(self)

    def _group(self,value):
        exact(value,{'ticket','phaseInstance','sequence','subjects','provider','providerClock','acquisition'})
        identifier(value['ticket']);identifier(value['phaseInstance']);need(integer(value['sequence'],1));exact(value['subjects'],set(ROLES))
        a=PhaseRetirementPublisher.acquisition(value['acquisition']);p=PhaseRetirementPublisher.acquisition(value['providerClock'])
        need(a['hostBeforeEpochMs']<=p['hostBeforeEpochMs']<=p['hostAfterEpochMs']<=a['hostAfterEpochMs']
            and a['hostBeforeMonotonic']<=p['hostBeforeMonotonic']<=p['hostAfterMonotonic']<=a['hostAfterMonotonic'])
        status=self.authority.validate(value['provider'],p['hostAfterEpochMs'])
        need(status['phase']=='revoking' and status['ticket']==value['ticket'])
        for row in status['accounts'].values():
            need(not row['grantsEnabled'] and not row['armedHold'] and all(row[k]==0 for k in ('heldRequests','inflightRequests','accessTokens','refreshTokens'))
                and p['hostBeforeEpochMs']<=row['capturedEpochMs']<=p['hostAfterEpochMs'])
        actual={subject:self.archives(subject,parts) for subject,parts in value['subjects'].items()}
        for subject,parts in actual.items():
            need(status['accounts'][subject]['runId']==self.inputs[subject]['childRunId'] and value['ticket']==self.inputs[subject]['ticket'])
            for join in (parts['left']['clockJoin'],parts['ui']['clockJoin'],parts['right']['clockJoin']):
                need(a['hostBeforeEpochMs']<=join['hostBeforeEpochMs']<=join['hostAfterEpochMs']<=a['hostAfterEpochMs']
                    and a['hostBeforeMonotonic']<=join['hostBeforeMonotonic']<=join['hostAfterMonotonic']<=a['hostAfterMonotonic'])
        return actual

    @staticmethod
    def component_prefix(before,after):
        need(set(before)==set(after) and all(same(before[k],after[k]) for k in before if k!='payload'))
        old,new=unpack(before['payload']),unpack(after['payload']);need(len(old)==len(new)==1)
        a,b=old[0],new[0];need(a['pending'] is None)
        for key in ('rows','records','abandoned'):
            if key in a:need(key in b and same(a[key],b[key][:len(a[key])]))

    def parse(self,value):
        if self.VERSION==2:
            from ios.adapters.avatar_final_pure_round import scope
            from ios.adapters.avatar_api_entry import original_cache
            from ios.adapters.avatar_record_cache import AvatarRecordCache
            existing=getattr(self,'_postlogout_rows',None)
            if existing is None:self._postlogout_rows=original_cache('postlogout-parts') or AvatarRecordCache()
            try:
                with scope(self,value):return self._parse(value)
            finally:
                if existing is None:del self._postlogout_rows
        return self._parse(value)

    def _parse(self,value):
        exact(value,{'iosAvatarFinalVersion','runId','role','bindings','artifactRoot','inputs','payload'})
        rows=unpack(value['payload']);need(len(rows)==1 and same(value,self.envelope(rows[0])));state=rows[0];exact(state,{'rows','pending'})
        need(type(state['rows']) is list and len(state['rows'])<=128);last={};sequence=0;components={};skip=0
        prefix=getattr(self,'_capture_prefix',None)
        if prefix is not None:
            need(not self.historical);skip,summary=prefix.resume(state)
            last,sequence,components=summary['last'],summary['sequence'],summary['components']
        for index,row in enumerate(state['rows'],1):
            if index<=skip:continue
            exact(row,{'index','reference','components'});need(type(row['index']) is int and row['index']==index)
            self.components(row['components'],index,complete=True)
            for key,ref in row['components'].items():
                current=self.component(index,*key.split('-',1),ref)
                if key in components:self.component_prefix(components[key],current)
                components[key]=current
            if row['reference'] is None:continue
            need(index==row['reference']['index']);record=self.record(row['reference']);actual=self.group(record)
            need(same(row['components'],{subject+'-'+kind:ref for subject,parts in record['subjects'].items() for kind,ref in parts['owners'].items()}))
            need(record['sequence']>sequence);sequence=record['sequence']
            for subject,parts in actual.items():
                if subject in last:follow(last[subject],parts['left']['clockJoin']['nativeBefore'])
                last[subject]=parts['right']['clockJoin']['nativeAfter']
        p=state['pending']
        if p is not None:
            exact(p,{'index','value','components'});need(p['index']==len(state['rows'])+1);self.components(p['components'],p['index'],complete=False)
            if p['value'] is not None:need(type(p['value']) is dict)
        elif not self.historical and len(state['rows'])<128:need(self.file(len(state['rows'])+1).read() is None)
        if prefix is not None:prefix.guard(state)
        if getattr(self,'_prefix_building',False):
            need(prefix is None and not self.historical)
            self._prefix_summary=deepcopy(dict(last=last,sequence=sequence,components=components))
        return deepcopy(state)

    def components(self,values,index,*,complete):
        need(type(values) is dict and set(values)<={s+'-'+k for s in ROLES for k in self.COMPONENTS})
        for key,ref in values.items():
            exact(ref,{'index','sha256'});need(ref['index']==index)
            if complete:self.component(index,*key.split('-',1),ref)

    def finish(self):
        self.bound();p=self.state['pending'];need(p is not None and p['value'] is not None);store=self.file(p['index']);old=store.read()
        if old is None:store.write(p['value'],None)
        else:need(same(old,p['value']))
        ref=dict(index=p['index'],sha256=digest(p['value']));self.group(self.record(ref))
        self.state['rows'].append(dict(index=p['index'],reference=ref,components=deepcopy(p['components'])));self.state['pending']=None;self.save();return ref

    def recover(self):
        self.bound();p=self.state['pending']
        if p is None:return None
        if p['value'] is not None:return self.finish()
        # A snapshot intent can be durable before its local file write. Only
        # the exact unchanged current subordinate metadata can fill that file;
        # no source query or transport is needed to recover the missing return.
        for key,ref in p['components'].items():
            subject,kind=key.split('-',1)
            path=self.root/('avatar-final-component-'+self.run+'-'+self.role+'-'+str(p['index'])+'-'+subject+'-'+kind+'.json')
            if PrivateFeatureState(path).read() is None:
                value=PrivateFeatureState(self.input(subject)['paths'][kind]).read()
                need(value is not None and digest(value)==ref['sha256'])
                self.retain_component(p['index'],subject,kind,value)
        # No operation is resent. Every subordinate sampler owns its exact
        # query/partial inode; reconstruction validates its append-only history.
        for subject in ROLES:
            actual=self.factory(subject)
            actual['post'].recover();actual['tail'].recover();actual['pointers'].abandon();self.recover_extra(actual)
        # Retain every actually written component, even if its return was
        # lost. Missing declared files remain owned and block abandonment.
        self.components(p['components'],p['index'],complete=True)
        self.state['rows'].append(dict(index=p['index'],reference=None,components=deepcopy(p['components'])))
        self.state['pending']=None;self.save();return None

    def capture(self,*,ticket,phase_instance,sequence):
        from ios.adapters.avatar_final_prefix import FinalCapturePrefix
        self.bound();self.recover()
        with FinalCapturePrefix(self):reference=self._capture(ticket=ticket,phase_instance=phase_instance,sequence=sequence)
        self.fresh(self.record(reference));return reference

    def _capture(self,*,ticket,phase_instance,sequence):
        self.bound();need(len(self.state['rows'])<128);identifier(ticket);identifier(phase_instance);need(integer(sequence,1))
        self.state['pending']=dict(index=len(self.state['rows'])+1,value=None,components={});self.save()
        a=dict(hostBeforeEpochMs=self.epoch_ms(),hostBeforeMonotonic=self.monotonic());subjects={}
        for subject in ROLES:
            actual=self.factory(subject);exact(actual,set(self.COMPONENTS))
            post,tail,pointer=actual['post'],actual['tail'],actual['pointers']
            need(isinstance(post,IOSAvatarPostLogoutReads) and isinstance(tail,IOSAvatarPostLogoutTail) and isinstance(pointer,IOSAvatarPointers)
                and all(owner.lock is self.locks[subject] for owner in actual.values())
                and all(same(owner.binding,self.bindings[subject]) and owner.role==self.role and owner.run==self.run for owner in actual.values()))
            pointer.abandon();left=pointer.capture();model=post.capture();ui=tail.capture();extra=self.capture_extra(actual);right=pointer.capture()
            subjects[subject]=dict(rows=dict(post=model['index'],tail=ui['index'],left=left,right=right,**extra),owners={key:self.retain_component(self.state['pending']['index'],subject,key,owner.previous) for key,owner in actual.items()})
        p=dict(hostBeforeEpochMs=self.epoch_ms(),hostBeforeMonotonic=self.monotonic());provider=self.authority.read()
        p.update(hostAfterEpochMs=self.epoch_ms(),hostAfterMonotonic=self.monotonic());a.update(hostAfterEpochMs=self.epoch_ms(),hostAfterMonotonic=self.monotonic())
        group=dict(ticket=ticket,phaseInstance=phase_instance,sequence=sequence,subjects=subjects,provider=provider,providerClock=p,acquisition=a);self.group(group)
        self.state['pending']['value']=dict(iosAvatarFinalOriginalVersion=self.VERSION,runId=self.run,role=self.role,bindings=self.bindings,payload=pack([group]));self.save()
        ref=self.finish();self.fresh(group);return ref

    @staticmethod
    def capture_extra(actual):return {}

    @staticmethod
    def recover_extra(actual):return None

    def subject_quiet(self,samples,binding):
        from ios.adapters.avatar_final_quiet import subject_quiet
        return subject_quiet(samples,binding,run=self.run,role=self.role)

    def fresh(self,record):
        self.bound();a=record['acquisition'];now,mono=self.epoch_ms(),self.monotonic()
        need(a['hostAfterEpochMs']<=now<a['hostBeforeEpochMs']+1500 and a['hostAfterMonotonic']<=mono<a['hostBeforeMonotonic']+1.5
            and abs(now-a['hostBeforeEpochMs']-(mono-a['hostBeforeMonotonic'])*1000)<=250)

    def quiet(self,references,*,sequence):
        """File-only postlogout component; no scene or whole cleanup verdict."""
        for lock in self.locks.values():lock.assert_held()
        need(type(references) is list and len(references)>=3 and all(any(row['reference']==ref for row in self.state['rows']) for ref in references))
        groups=[self.record(ref) for ref in references];actual=[self.group(row) for row in groups];first,last=groups[0],groups[-1]
        need(all(row['ticket']==last['ticket'] and row['phaseInstance']==last['phaseInstance'] for row in groups)
            and all(b['sequence']>a['sequence'] for a,b in zip(groups,groups[1:])) and integer(sequence,last['sequence']))
        quiets={subject:self.subject_quiet([row[subject] for row in actual],self.bindings[subject]) for subject in ROLES}
        acquisition=deepcopy(last['acquisition']);native=actual[-1][self.role]['right']['clockJoin']['nativeAfter']
        ref=references[-1]
        return dict(iosAvatarFinalProofVersion=self.VERSION,runId=self.run,ticket=last['ticket'],phaseInstance=last['phaseInstance'],sequence=sequence,
            capturedEpochMs=acquisition['hostAfterEpochMs'],lifecycle=deepcopy(native['lifecycle']),acquisition=acquisition,bilateralQuiet=quiets,
            originalSha256=ref['sha256'],provenance=dict(version=1,namespace='ios-avatar-final-original',reference=deepcopy(ref),originalSha256=ref['sha256']))

    @classmethod
    def archive(cls,value,*,store,root,bindings,run,role,locks,authority,inputs):
        result=object.__new__(cls);result.store=Frozen(store.path,value);result.root=Path(root);result.bindings={k:context(v) for k,v in bindings.items()}
        result.run,result.role,result.locks,result.authority,result.inputs=identifier(run),role,locks,authority,deepcopy(inputs)
        result.historical=True;result.previous=deepcopy(value);result.state=result.parse(value);return result
