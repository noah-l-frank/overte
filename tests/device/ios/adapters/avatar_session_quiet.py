"""Own SDK quiet after actual fixture retirement, with unchanged native DTOs.

This private component publishes nothing. Historical provider/Complete facts
remain in the whole owner; no removed account endpoint is called or retimed.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
from adapters.native_feature_observation import exact,integer,need
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.original_frame_store import OriginalFrameStore
from adapters.phase_retirement_publisher import PhaseRetirementPublisher
from adapters.script_feature.history import pack,unpack,same
from feature_journeys.contract import identifier
from feature_journeys.phase_fixture import PhaseFixtureReader,validate as phase_original
from ios.adapters.avatar_final import IOSAvatarFinal,Frozen
from ios.adapters.avatar_final_quiet import subject_quiet
from ios.adapters.avatar_postlogout_reads import IOSAvatarPostLogoutReads
from ios.adapters.avatar_postlogout_tail import IOSAvatarPostLogoutTail
from ios.adapters.avatar_pointers import IOSAvatarPointers
from ios.adapters.avatar_whole_snapshots import AvatarWholeSnapshots
from ios.adapters.emote_native_prefix import follow

VERSION=1
KINDS=('post','tail','pointers')


class SessionSnapshots(AvatarWholeSnapshots):
    def __init__(self,root,binding,run,role,entries,guard,save):
        self.entries,self.save=entries,save
        self.originals=OriginalFrameStore(root,binding,run,role,guard,self.storage,
            namespace='avatar-session-owned',schema_prefix='avatarSessionOwned')


class IOSAvatarSessionQuiet:
    def __init__(self,store,root,binding,run,role,lock,guard,factory,phase,inputs,*,epoch_ms,monotonic):
        need(isinstance(store,PrivateFeatureState) and isinstance(phase,PhaseFixtureReader)
            and phase.area=='avatar-people' and phase.run==run and role in ('primary','actor')
            and all(callable(fn) for fn in (guard,factory,epoch_ms,monotonic)))
        self.store,self.root,self.binding,self.run,self.role,self.lock=store,Path(root),context(binding),identifier(run),role,lock
        need(store.path==lock.path.with_name('ios-avatar-'+role+'-session-quiet.json'))
        self.guard,self.factory,self.phase,self.inputs=guard,factory,phase,deepcopy(inputs)
        self.epoch_ms,self.monotonic=epoch_ms,monotonic
        self.historical=False;self.previous=store.read();self.state=dict(snapshots=[],records=[],pending=None)
        self.bound();self.view({}).input(self.role);need(Path(self.inputs['root'])==self.root
            and self.inputs['fixtureUrl']==phase.client.url+'/runs/'+self.inputs['childRunId']+'/')
        if self.previous is not None:self.state=self.parse(self.previous)

    def envelope(self,state):
        return dict(iosAvatarSessionQuietVersion=VERSION,runId=self.run,role=self.role,binding=self.binding,
            artifactRoot=str(self.root),inputs=self.inputs,payload=pack([state]))

    def snapshots(self):
        return SessionSnapshots(self.root,self.binding,self.run,self.role,lambda:self.state['snapshots'],
            self.lock.assert_held,self.save)

    def bound(self):
        self.lock.assert_held();need(not self.historical and self.guard() is not False and same(self.store.read(),self.previous))

    def save(self):
        self.bound();value=self.envelope(self.state);self.store.write(value,self.previous)
        need(same(self.store.read(),value));self.previous=deepcopy(value)

    def snapshot(self,value):self.bound();return self.snapshots().retain(value)
    def kept(self,ref):return self.snapshots().read(ref)

    def view(self,owners):
        view=object.__new__(IOSAvatarFinal);view.role,view.run=self.role,self.run
        view.inputs={self.role:self.inputs};view.bindings={self.role:self.binding};view.locks={self.role:self.lock}
        def component(index,subject,kind,reference):
            need(index==reference['index'] and subject==self.role and kind in KINDS)
            ref=owners[kind];need(reference==dict(index=index,sha256=ref['sha256']))
            return self.kept(ref)
        view.component=component;return view

    def component_owner(self,kind,value):
        config=self.inputs;shared=dict(root=self.root,binding=self.binding,run=self.run,role=self.role,lock=self.lock)
        common=dict(child_run=config['childRunId'],fixture_url=config['fixtureUrl'],ticket=config['ticket'],logout_before=config['logoutBefore'],subject=self.role)
        store=Frozen(config['paths'][kind],value)
        if kind=='post':return IOSAvatarPostLogoutReads.archive(value,store=store,baseline=config['baseline']['state'],**common,**shared)
        if kind=='tail':return IOSAvatarPostLogoutTail.archive(value,store=store,baseline=config['baseline'],**common,**shared)
        need(kind=='pointers');return IOSAvatarPointers.archive(value,store=store,**shared)

    def actual(self):
        self.bound();actual=self.factory();exact(actual,set(KINDS))
        need(isinstance(actual['post'],IOSAvatarPostLogoutReads) and isinstance(actual['tail'],IOSAvatarPostLogoutTail)
            and isinstance(actual['pointers'],IOSAvatarPointers)
            and all(owner.lock is self.lock and owner.role==self.role and owner.run==self.run
                and same(owner.binding,self.binding) for owner in actual.values()))
        return actual

    def record(self,ref):
        value=self.kept(ref);exact(value,{'iosAvatarSessionQuietOriginalVersion','runId','role','binding','index','before','after','parts','acquisition'})
        need(type(value['iosAvatarSessionQuietOriginalVersion']) is int and value['iosAvatarSessionQuietOriginalVersion']==VERSION
            and value['runId']==self.run and value['role']==self.role and same(value['binding'],self.binding) and integer(value['index'],1,16))
        return value

    def phase_value(self,item,previous=None):
        exact(item,{'status','acquisition'});clock=PhaseRetirementPublisher.acquisition(item['acquisition']);status=item['status']
        phase_original(status,run=self.run,area='avatar-people',request=status['requestId'],epoch=clock['hostAfterEpochMs'],previous=previous)
        need(not status['active'] and status['activations'] and status['activations'][-1]['stimulus']==dict(verb='cleanup',inputs={}))
        return clock,status

    def original(self,value):
        exact(value['parts'],{'owners','rows'});exact(value['parts']['owners'],set(KINDS));exact(value['parts']['rows'],{'left','post','tail','right'})
        a=PhaseRetirementPublisher.acquisition(value['acquisition'])
        prior=None
        for name in ('before','after'):
            clock,status=self.phase_value(value[name],prior)
            need(a['hostBeforeEpochMs']<=clock['hostBeforeEpochMs']<=clock['hostAfterEpochMs']<=a['hostAfterEpochMs']
                and a['hostBeforeMonotonic']<=clock['hostBeforeMonotonic']<=clock['hostAfterMonotonic']<=a['hostAfterMonotonic'])
            prior=status
        owners=value['parts']['owners'];view=self.view(owners)
        parts=dict(rows=value['parts']['rows'],owners={key:dict(index=value['index'],sha256=ref['sha256']) for key,ref in owners.items()})
        result=view.archives(self.role,parts)
        before,after=value['before']['acquisition'],value['after']['acquisition']
        for key in ('hostBeforeEpochMs','hostBeforeMonotonic'):
            end=key.replace('Before','After')
            need(before[end]<=result['left']['clockJoin'][key] and result['right']['clockJoin'][end]<=after[key])
        need(self.inputs['ticket']==prior['activations'][-1]['ticket'])
        return result

    def parse(self,value):
        exact(value,{'iosAvatarSessionQuietVersion','runId','role','binding','artifactRoot','inputs','payload'})
        rows=unpack(value['payload']);need(len(rows)==1 and same(value,self.envelope(rows[0])))
        state=rows[0];exact(state,{'snapshots','records','pending'});need(type(state['records']) is list and len(state['records'])<=16)
        old=self.state;self.state=state
        try:
            self.snapshots().validate();last=None;owners={};phase=None
            for index,row in enumerate(state['records'],1):
                exact(row,{'index','reference','owners','partial'});need(row['index']==index and type(row['owners']) is dict and set(row['owners'])<=set(KINDS))
                for kind,ref in row['owners'].items():
                    current=self.kept(ref);self.component_owner(kind,current)
                    if kind in owners:IOSAvatarFinal.component_prefix(owners[kind],current)
                    owners[kind]=current
                if row['reference'] is None:
                    partial=row['partial'];exact(partial,{'before','rows'})
                    need(type(partial['rows']) is dict and set(partial['rows'])<={'left','post','tail','right'})
                    if partial['before'] is not None:self.phase_value(partial['before'])
                    continue
                need(row['partial'] is None and set(row['owners'])==set(KINDS))
                record=self.record(row['reference']);need(record['index']==index and same(row['owners'],record['parts']['owners']))
                current=self.original(record)
                if last is not None:follow(last,current['left']['clockJoin']['nativeBefore'])
                if phase is not None:
                    status=record['before']['status'];phase_original(status,run=self.run,area='avatar-people',request=status['requestId'],epoch=status['capturedEpochMs'],previous=phase)
                last=current['right']['clockJoin']['nativeAfter'];phase=record['after']['status']
            p=state['pending']
            if p is not None:
                exact(p,{'index','before','owners','rows','value'});need(p['index']==len(state['records'])+1 and integer(p['index'],1,16)
                    and type(p['owners']) is dict and set(p['owners'])<=set(KINDS) and type(p['rows']) is dict and set(p['rows'])<={'left','post','tail','right'})
                if p['before'] is not None:self.phase_value(p['before'])
                for kind,ref in p['owners'].items():self.component_owner(kind,self.kept(ref))
                if p['value'] is not None:self.original(p['value'])
            return deepcopy(state)
        finally:self.state=old

    def retain(self,kind,actual):
        p=self.state['pending'];need(p is not None and kind in KINDS and actual.previous is not None)
        p['owners'][kind]=self.snapshot(actual.previous);self.save()

    def finish(self):
        self.bound();p=self.state['pending'];need(p is not None and p['value'] is not None)
        self.original(p['value']);reference=self.snapshot(p['value'])
        self.state['records'].append(dict(index=p['index'],reference=reference,owners=deepcopy(p['owners']),partial=None))
        self.state['pending']=None;self.save();return reference

    def recover(self):
        self.bound();p=self.state['pending']
        if p is None:return None
        if p['value'] is not None:return self.finish()
        actual=self.actual();actual['post'].recover();actual['tail'].recover();actual['pointers'].abandon()
        for kind,owner in actual.items():
            if owner.previous is not None:self.retain(kind,owner)
        self.state['records'].append(dict(index=p['index'],reference=None,owners=deepcopy(p['owners']),
            partial=dict(before=deepcopy(p['before']),rows=deepcopy(p['rows']))))
        self.state['pending']=None;self.save();return None

    def phase_read(self):
        clock=dict(hostBeforeEpochMs=self.epoch_ms(),hostBeforeMonotonic=self.monotonic());status=self.phase.status()
        clock.update(hostAfterEpochMs=self.epoch_ms(),hostAfterMonotonic=self.monotonic())
        need(not status['active']);return dict(status=status,acquisition=clock)

    def capture(self):
        self.bound();self.recover();need(len(self.state['records'])<16)
        self.state['pending']=dict(index=len(self.state['records'])+1,before=None,owners={},rows={},value=None);self.save();p=self.state['pending']
        acquisition=dict(hostBeforeEpochMs=self.epoch_ms(),hostBeforeMonotonic=self.monotonic())
        p['before']=self.phase_read();self.save();actual=self.actual()
        actual['pointers'].abandon();left=actual['pointers'].capture();p['rows']['left']=left;self.retain('pointers',actual['pointers'])
        post=actual['post'].capture();p['rows']['post']=post['index'];self.retain('post',actual['post'])
        tail=actual['tail'].capture();p['rows']['tail']=tail['index'];self.retain('tail',actual['tail'])
        right=actual['pointers'].capture();p['rows']['right']=right;self.retain('pointers',actual['pointers'])
        after=self.phase_read();acquisition.update(hostAfterEpochMs=self.epoch_ms(),hostAfterMonotonic=self.monotonic())
        value=dict(iosAvatarSessionQuietOriginalVersion=VERSION,runId=self.run,role=self.role,binding=self.binding,index=p['index'],before=deepcopy(p['before']),
            after=after,parts=dict(owners=deepcopy(p['owners']),rows=deepcopy(p['rows'])),acquisition=acquisition)
        self.original(value);p['value']=value;self.save();reference=self.finish();self.fresh(value);return reference

    def fresh(self,value):
        self.bound();a=value['acquisition'];now,mono=self.epoch_ms(),self.monotonic()
        need(a['hostAfterEpochMs']<=now<a['hostBeforeEpochMs']+1500 and a['hostAfterMonotonic']<=mono<a['hostBeforeMonotonic']+1.5
            and abs(now-a['hostBeforeEpochMs']-(mono-a['hostBeforeMonotonic'])*1000)<=250)

    def quiet(self,references):
        self.lock.assert_held();need(type(references) is list and len(references)>=3
            and all(any(row['reference']==ref for row in self.state['records']) for ref in references))
        records=[self.record(ref) for ref in references];need(all(a['index']<b['index'] for a,b in zip(records,records[1:])))
        samples=[self.original(value) for value in records]
        for a,b in zip(samples,samples[1:]):follow(a['right']['clockJoin']['nativeAfter'],b['left']['clockJoin']['nativeBefore'])
        for a,b in zip(records,records[1:]):
            before=b['before']['status'];phase_original(before,run=self.run,area='avatar-people',request=before['requestId'],epoch=before['capturedEpochMs'],previous=a['after']['status'])
        quiet=subject_quiet(samples,self.binding,run=self.run,role=self.role)
        return dict(iosAvatarSessionQuietProofVersion=VERSION,runId=self.run,role=self.role,binding=self.binding,
            quiet=quiet,phase=deepcopy(records[-1]['after']['status']),references=deepcopy(references))

    @classmethod
    def archive(cls,value,*,store,root,binding,run,role,lock,inputs):
        result=object.__new__(cls);result.store=Frozen(store.path,value);result.root=Path(root);result.binding=context(binding)
        result.run,result.role,result.lock,result.inputs=identifier(run),role,lock,deepcopy(inputs)
        need(store.path==lock.path.with_name('ios-avatar-'+role+'-session-quiet.json'))
        result.historical=True;result.state=dict(snapshots=[],records=[],pending=None);result.previous=deepcopy(value)
        result.view({}).input(role);need(Path(inputs['root'])==result.root)
        result.state=result.parse(value);return result
