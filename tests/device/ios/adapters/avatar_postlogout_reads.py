"""Owned account/model/account acquisition after ordinary Avatar logout.

Queries, native clock originals and returned model bytes survive interruption.
Only a fully retained closed decoder can qualify the resulting property proof.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import time

from adapters.native_clock_join import digest
from adapters.native_feature_observation import NativeFeatureObservation,decode,exact,integer,need,number,validate as native
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.original_frame_store import OriginalFrameStore
from adapters.script_feature.history import pack,unpack,same,canonical
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.contract import identifier
from ios.adapters import avatar_state,avatar_postlogout
from ios.adapters.avatar_account_reads import IOSAvatarAccountReads
from ios.adapters.avatar_postlogout_parts import AvatarPostLogoutParts
from ios.adapters.authentication_causality import check as account_causality
from ios.adapters.emote_native_prefix import follow as native_prefix
from ios.adapters import avatar_postlogout_row_cache as row_cache
from ios.adapters import avatar_account_reads as account_source
from ios.adapters.avatar_record_cache import AvatarRecordCache

VERSION=2
READS=(1,2)

def _archived_guard():return True


class IOSAvatarPostLogoutReads(AvatarPostLogoutParts):
    def __init__(self,store,root,binding,run,role,subject,lock,guard,accounts_factory,model_factory,*,
                 child_run,fixture_url,ticket,baseline,logout_before,epoch_ms=lambda:time.time()*1000,monotonic=time.monotonic,historical=False,historical_rows=None):
        need(isinstance(store,PrivateFeatureState) and isinstance(lock,ScriptSourceLock) and role in ('primary','actor') and subject in ('primary','actor')
            and type(historical) is bool and all(callable(fn) for fn in (guard,accounts_factory,model_factory,epoch_ms,monotonic)))
        self.store,self.root,self.binding,self.run,self.role,self.subject,self.lock=store,root,context(binding),identifier(run),role,subject,lock
        need(store.path.name=='ios-avatar-'+role+'-'+subject+'-postlogout.json' and store.path.parent==lock.path.parent);lock.assert_held()
        self.guard,self.accounts_factory,self.model_factory,self.epoch_ms,self.monotonic=guard,accounts_factory,model_factory,epoch_ms,monotonic
        need(historical_rows is None or historical and type(historical_rows) is AvatarRecordCache)
        self.historical,self.historical_rows=historical,historical_rows
        if historical_rows is not None:self.part_cache=historical_rows
        self.inputs=dict(childRunId=identifier(child_run),fixtureUrl=fixture_url,ticket=identifier(ticket),baseline=deepcopy(baseline),logoutBefore=deepcopy(logout_before))
        avatar_state.original(baseline);need(baseline['runId']==run and baseline['processId']==int(binding['processIdentity']))
        self.originals=OriginalFrameStore(root,binding,run,role,guard,self.storage,namespace='avatar-'+subject+'-postlogout',
            schema_prefix='avatar'+subject.title()+'PostLogout',monotonic=monotonic)
        self.parts_init();self.previous=store.read();self.state=dict(rows=[],pending=None,nextSegment=1)
        if self.previous is not None:self.state=self.parse(self.previous)

    def envelope(self,state,version=VERSION):
        state=deepcopy(state)
        if version>=2:state.setdefault('nextSegment',1)
        return dict(iosAvatarPostLogoutReadsVersion=version,runId=self.run,role=self.role,subject=self.subject,
            binding=self.binding,artifactRoot=str(self.root),inputs=deepcopy(self.inputs),payload=pack([state]))

    def bound(self):self.lock.assert_held();need(not self.historical and self.guard() is not False and same(self.store.read(),self.previous))

    def accounts(self):
        owner=self.accounts_factory();need(isinstance(owner,IOSAvatarAccountReads) and same(owner.binding,self.binding)
            and owner.run==self.run and owner.role==self.role and owner.subject==self.subject and owner.lock is self.lock
            and owner.store.path.parent==self.store.path.parent and str(owner.root)==str(self.root))
        pending_round=getattr(self,'_pending_round',None)
        if pending_round is not None:
            original=owner.guard
            def guard():pending_round.transport_guard();return original()
            owner.guard=guard
        return owner

    def account(self,value):
        from ios.adapters.avatar_record_cache import AvatarRecordCache
        if not hasattr(self,'account_cache'):
            from ios.adapters.avatar_api_entry import original_cache
            self.account_cache=original_cache('postlogout-account') or AvatarRecordCache()
        key=dict(context=digest(dict(binding=self.binding,runId=self.run,role=self.role,subject=self.subject,
            root=str(self.root),store=str(self.store.path),inputs=self.inputs)),boundary=value)
        return self.account_cache.read(key,lambda:self.account_original(value))

    def account_original(self,value):
        exact(value,{'owner','row'});raw=value['owner'];row=value['row']
        path=self.store.path.with_name('ios-avatar-'+self.role+'-'+self.subject+'-account-reads.json')
        class Frozen(PrivateFeatureState):
            def read(_self):return deepcopy(raw)
            def write(_self,*_args):need(False)
            def discard(_self,*_args):need(False)
        owner=IOSAvatarAccountReads(Frozen(path),self.root,self.binding,self.run,self.role,self.subject,self.lock,lambda:True,historical=True)
        need(row in owner.state['rows'] and row['status']=='observed');return owner.packet(row)

    def part(self,value,previous=None):
        need(type(value) is dict and set(value)<={'before','modelQuery','model','modelAcquisition','clocks','after'})
        before=None
        if 'before' in value:
            before=self.account(value['before']);account_causality(dict(contractVersion=16,runId=self.inputs['childRunId'],fixtureUrl=self.inputs['fixtureUrl'],
                ticket=self.inputs['ticket'],verb='logout',inputs={}),self.inputs['logoutBefore'],before,before['capturedEpochMs'])
        if 'modelQuery' in value:avatar_state.command(value['modelQuery']);need(value['modelQuery']['runId']==self.run and 'before' in value)
        if 'model' in value:
            need('modelQuery' in value);avatar_state._validate(value['model'],value['modelQuery'],int(self.binding['processIdentity']),previous=previous,postlogout=True)
        if 'clocks' in value:
            clocks=value['clocks'];need(type(clocks) is list and len(clocks)<=64 and before is not None);last=before
            for row in clocks:
                exact(row,{'query','packet'});IOSAvatarAccountReads.command(row['query'])
                if row['packet'] is not None:
                    packet=row['packet'];native(packet,row['query']['commandId'],int(self.binding['processIdentity']),packet.get('capturedEpochMs'),require_account=True)
                    native_prefix(last,packet);last=packet
                else:need(row is clocks[-1])
        if 'modelAcquisition' in value:
            a=value['modelAcquisition'];exact(a,{'iosAvatarStateAcquisitionVersion','hostBeforeMonotonic','hostAfterMonotonic',
                'nativeRequestedEpochMs','nativeAfterEpochMs','originalSha256'})
            need(type(a['iosAvatarStateAcquisitionVersion']) is int and a['iosAvatarStateAcquisitionVersion']==1 and 'model' in value
                and a['originalSha256']==digest(value['model']) and number(a['hostBeforeMonotonic'],0,1e15)
                and number(a['hostAfterMonotonic'],a['hostBeforeMonotonic'],a['hostBeforeMonotonic']+1.5)
                and a['hostAfterMonotonic']-a['hostBeforeMonotonic']<1.5
                and integer(a['nativeRequestedEpochMs'],1) and integer(a['nativeAfterEpochMs'],a['nativeRequestedEpochMs'])
                and a['nativeRequestedEpochMs']<=value['model']['clockBefore']['epochMs']
                <=value['model']['clockAfter']['epochMs']<=a['nativeAfterEpochMs'])
            need(len(value['clocks'])>=2 and all(row['packet'] is not None for row in value['clocks'])
                and value['clocks'][0]['packet']['capturedEpochMs']==a['nativeRequestedEpochMs']
                and value['clocks'][-1]['packet']['capturedEpochMs']==a['nativeAfterEpochMs'])
        if 'after' in value:
            after=self.account(value['after']);need('modelAcquisition' in value);native_prefix(value['clocks'][-1]['packet'],after)
        return value.get('model',previous)

    def parse(self,value):
        exact(value,{'iosAvatarPostLogoutReadsVersion','runId','role','subject','binding','artifactRoot','inputs','payload'})
        version=value['iosAvatarPostLogoutReadsVersion'];need(type(version) is int and version in READS)
        rows=unpack(value['payload']);need(len(rows)==1 and same(value,self.envelope(rows[0],version)));state=rows[0]
        exact(state,{'rows','pending'}|({'nextSegment'} if version>=2 else set()))
        need(type(state['rows']) is list and len(state['rows'])<=64);previous=None;materials={}
        for index,row in enumerate(state['rows'],1):
            exact(row,{'index','status','original','acquisition','partsCarrier' if 'partsCarrier' in row else 'parts'})
            need(integer(row['index'],1,64) and row['index']==index and row['status'] in ('observed','abandoned'))
            if 'partsCarrier' in row:need(version>=2)
            material=self.row_material(row) if 'partsCarrier' in row else dict(partial=row,parts=row['parts'])
            materials[index]=material
            previous=self._historical_row(row,material,previous,index)
        if state['pending'] is not None:
            row=state['pending'];fields={'index','parts','original','acquisition'}
            if 'partsStorageVersion' in row:
                need(version>=2 and type(row['partsStorageVersion']) is int and row['partsStorageVersion']==1)
                fields|={'partsStorageVersion','partialOriginal','orphanPartials'}
                need(type(row['orphanPartials']) is list and len(row['orphanPartials'])<=64)
                for orphan in row['orphanPartials']:
                    exact(orphan,{'parent','snapshots'});need(orphan['parent']['label']=='partial' and orphan['parent']['tag']==self.part_tag(row['index'],'partial'))
                    self.segments.retained(orphan['parent'],orphan['snapshots'])
                if row['partialOriginal'] is not None:
                    self.segments.parent(row['partialOriginal']);need(row['partialOriginal']['label']=='partial' and row['partialOriginal']['tag']==self.part_tag(row['index'],'partial'))
            exact(row,fields);need(integer(row['index'],1,64) and row['index']==len(state['rows'])+1);self.part(self.row_parts(row),previous)
            if row['original'] is not None:self.originals.original(row['original']);need(row['original']['index']==row['index'])
            if row['acquisition'] is not None:self.acquisition(row['acquisition'])
        if version>=2:
            self.parts_inventory(state,materials)
            # The local material is used only inside this synchronous parse.
            # Recheck its complete actual read/absence inventory at the end;
            # Per-row historical reuse never supplies a current/quiet verdict.
            for row in state['rows']:
                if 'partsCarrier' in row:self.row_material(row,check_only=True)
        return deepcopy(state)

    def _historical_row(self,row,material,previous,index):
        def decode():
            model=self.part(material['parts'],previous)
            if row['original'] is not None:self.originals.original(row['original']);need(row['original']['index']==index)
            if row['acquisition'] is not None:self.acquisition(row['acquisition'])
            if row['status']=='observed':self._record_fields(row,material)
            return model
        def policy():
            # arguments() actually reads only this area's current steps. Use
            # exact builtin lookups before metadata scanning; never invoke an
            # opaque scenario container or cache an actions()/verdict result.
            scenarios=vars(feature_contract)['SCENARIOS']
            if type(scenarios) is not dict or not all(type(key) is str for key in scenarios):raise row_cache._Unsupported
            area=dict.get(scenarios,'authentication')
            if type(area) is not dict or not all(type(key) is str for key in area):raise row_cache._Unsupported
            steps=dict.get(area,'steps')
            if type(steps) is not list:raise row_cache._Unsupported
            return (VERSION,READS,avatar_state.VERSION,avatar_state.READS,account_source.VERSION,feature_contract.VERSION,steps)
        return row_cache.read(self,row,material,previous,index,policy,decode)

    def save(self):
        pending_round=getattr(self,'_pending_round',None)
        if pending_round is not None:pending_round.guard()
        self.bound();value=self.envelope(self.state)
        if pending_round is None:self.parse(value)
        else:pending_round.validate(value)
        self.store.write(value,self.previous)
        need(same(self.store.read(),value));self.previous=deepcopy(value)
        if pending_round is not None:pending_round.accepted()

    def storage(self,kind,value):
        self.bound();p=self.state['pending'];need(kind=='original' and p is not None);self.originals.original(value);old=p['original']
        need(value['index']==p['index'] and (value['phase']=='planned' if old is None else value['phase']=={'planned':'opened','opened':'saved'}.get(old['phase'])
            and all(same(value[key],old[key]) for key in value if key not in ('phase','file')) and (old['phase']=='planned' or same(value['file'],old['file']))))
        p['original']=deepcopy(value);self.save()

    def record(self,row):
        material=self.row_material(row) if 'partsCarrier' in row else dict(partial=row,parts=row['parts'])
        self.part(material['parts']);p=self._record_fields(row,material)
        if 'partsCarrier' in row:self.row_material(row,check_only=True)
        return p

    def _record_fields(self,row,material):
        self.lock.assert_held();need(row['original'] is not None)
        current='partsCarrier' in row
        if current:need(self.native_file(row['original'])['complete'])
        else:need(row['original']['phase']=='saved')
        record=self.originals.read(row['original']);exact(record,{'iosAvatarPostLogoutRecordVersion','index','parts','acquisition'})
        version=record['iosAvatarPostLogoutRecordVersion'];need(type(version) is int and version in READS and version==(2 if current else 1))
        raw=material['partial']['parts'];need(record['index']==row['index'] and same(record['parts'],raw) and same(record['acquisition'],row['acquisition']))
        p=material['parts'];exact(p,{'before','modelQuery','model','modelAcquisition','clocks','after'})
        a=self.acquisition(row['acquisition'])
        for boundary in ('before','after'):
            inner=p[boundary]['row']['acquisition']
            for first,last in (('hostBeforeEpochMs','hostAfterEpochMs'),('hostBeforeMonotonic','hostAfterMonotonic')):
                need(a[first]<=inner[first]<=inner[last]<=a[last])
        inner=p['modelAcquisition'];need(a['hostBeforeMonotonic']<=inner['hostBeforeMonotonic']<=inner['hostAfterMonotonic']<=a['hostAfterMonotonic'])
        return p

    @staticmethod
    def acquisition(a):
        exact(a,{'hostBeforeEpochMs','hostAfterEpochMs','hostBeforeMonotonic','hostAfterMonotonic'})
        need(number(a['hostBeforeEpochMs'],1,1e15) and number(a['hostAfterEpochMs'],a['hostBeforeEpochMs'],a['hostBeforeEpochMs']+1500)
            and number(a['hostBeforeMonotonic'],0,1e15) and number(a['hostAfterMonotonic'],a['hostBeforeMonotonic'],a['hostBeforeMonotonic']+1.5)
            and a['hostAfterEpochMs']-a['hostBeforeEpochMs']<1500 and a['hostAfterMonotonic']-a['hostBeforeMonotonic']<1.5
            and abs(a['hostAfterEpochMs']-a['hostBeforeEpochMs']-(a['hostAfterMonotonic']-a['hostBeforeMonotonic'])*1000)<=250)
        return a

    def proof(self,row):
        need(getattr(self,'_pending_round',None) is None and self.previous is not None)
        self.lock.assert_held();need(same(self.store.read(),self.previous))
        decoded=self.parse(self.previous)
        decoded.setdefault('nextSegment',1)
        current=deepcopy(self.state);current.setdefault('nextSegment',1);need(same(decoded,current))
        need(row in self.state['rows'] and row['status']=='observed')
        p=self.record(row)
        return avatar_postlogout.restored(p['model'],self.inputs['baseline'],self.account(p['before']),self.account(p['after']),self.inputs['logoutBefore'],
            binding=self.binding,child_run=self.inputs['childRunId'],fixture_url=self.inputs['fixtureUrl'],ticket=self.inputs['ticket'])

    def recover(self):
        self.bound();p=self.state['pending']
        if p is None:return None
        if 'partsStorageVersion' not in p:
            status='observed' if p['original'] is not None and p['original']['phase']=='saved' and p['acquisition'] is not None else 'abandoned'
            if p['original'] is not None:need(p['original']['phase']=='saved')
            row=dict(deepcopy(p),status=status)
        else:
            original=self.native_file(p['original'])
            status='observed' if original is not None and original['complete'] and p['acquisition'] is not None else 'abandoned'
            if p['partialOriginal'] is not None and not self.part_complete(p['partialOriginal']):
                old=deepcopy(p['partialOriginal']);p['orphanPartials'].append(dict(parent=old,snapshots=self.segments.inspect(old)))
                p['partialOriginal']=None;self.save()
            partial=self.part_partial(p)
            if p['partialOriginal'] is None:self.remember_part('partial',partial)
            else:need(self.segments.read(p['partialOriginal'])==canonical(partial))
            row=dict(index=p['index'],status=status,partsCarrier=deepcopy(p['partialOriginal']),original=deepcopy(p['original']),acquisition=deepcopy(p['acquisition']))
        self.state['rows'].append(row);self.state['pending']=None;self.save();return deepcopy(row)

    def capture(self):
        need(getattr(self,'_pending_round',None) is None)
        self.bound();self.recover();self.state.setdefault('nextSegment',1);need(len(self.state['rows'])<64 and self.state['nextSegment']+72<=1024)
        from ios.adapters.avatar_postlogout_incremental import AvatarPendingRound
        self._pending_round=AvatarPendingRound(self)
        try:return self._capture_pending()
        finally:self._pending_round=None

    def _capture_pending(self):
        p=dict(index=len(self.state['rows'])+1,parts={},original=None,acquisition=None,partsStorageVersion=1,partialOriginal=None,orphanPartials=[]);self.state['pending']=p;self.save()
        started,mono=self.epoch_ms(),self.monotonic();accounts=self.accounts()
        before=accounts.read();self.remember_part('before',dict(owner=deepcopy(accounts.previous),row=before));self.part(self.row_parts(p))
        model,clock=self.model_factory();need(isinstance(model,avatar_state.IOSAvatarState) and isinstance(clock,NativeFeatureObservation)
            and clock.ios and clock.pid==int(self.binding['processIdentity']))
        previous=next((self.row_parts(row)['model'] for row in reversed(self.state['rows']) if 'model' in self.row_parts(row)),None);model.last=deepcopy(previous)
        model._validate=lambda value,query,pid,epoch=None,previous=None:avatar_state._validate(value,query,pid,epoch,previous,postlogout=True)
        send,original,clock_send,clock_original=model.send,model.original,clock.send,clock.original;p['parts']['clocks']=[];self.save()
        def owned_send(query):
            need(self.state['nextSegment']+8<=1024 and 'modelQuery' not in p['parts']);p['parts']['modelQuery']=deepcopy(avatar_state.command(query));self.save()
            self._pending_round.transport_guard();return send(query)
        def owned_original():
            need(self.state['nextSegment']+8<=1024);self._pending_round.transport_guard();raw=original();value=decode(raw) if raw else None
            if type(value) is dict and 'modelQuery' in p['parts'] and value.get('requestId')==p['parts']['modelQuery']['commandId']:
                need('model' not in p['parts']);self.remember_part('model',value)
            return raw
        def owned_clock_send(query):
            need(len(p['parts']['clocks'])<64 and self.state['nextSegment']+8<=1024)
            p['parts']['clocks'].append(dict(query=deepcopy(IOSAvatarAccountReads.command(query)),packet=None));self.save()
            self._pending_round.transport_guard();return clock_send(query)
        def owned_clock_original():
            need(self.state['nextSegment']+8<=1024);self._pending_round.transport_guard();raw=clock_original();value=decode(raw) if raw else None;row=p['parts']['clocks'][-1]
            if type(value) is dict and value.get('requestId')==row['query']['commandId']:
                if row['packet'] is None:self.remember_part('clock',value,len(p['parts']['clocks'])-1)
                else:need(same(self.part_value(row['packet'],p['index'],'clock-'+str(len(p['parts']['clocks'])-1),required=True),value))
            return raw
        model.send,model.original,clock.send,clock.original=owned_send,owned_original,owned_clock_send,owned_clock_original
        try:
            model.read(self.run);p['parts']['modelAcquisition']=deepcopy(model.acquisition);self.save()
        finally:model.send,model.original,clock.send,clock.original=send,original,clock_send,clock_original
        accounts=self.accounts();after=accounts.read();self.remember_part('after',dict(owner=deepcopy(accounts.previous),row=after))
        p['acquisition']=dict(hostBeforeEpochMs=started,hostAfterEpochMs=self.epoch_ms(),hostBeforeMonotonic=mono,hostAfterMonotonic=self.monotonic());self.save()
        self.originals.write(p['index'],dict(iosAvatarPostLogoutRecordVersion=VERSION,index=p['index'],parts=deepcopy(p['parts']),acquisition=deepcopy(p['acquisition'])))
        # Recover/partial-carrier/completed-row qualification always uses the
        # complete decoder again, followed by the unchanged fresh-return guard.
        self._pending_round.guard();self._pending_round=None;self.parse(self.previous)
        row=self.recover();self.proof(row);epoch,last=self.epoch_ms(),self.monotonic()
        need(number(epoch,started,started+1500) and epoch-started<1500 and number(last,mono,mono+1.5) and last-mono<1.5
            and abs(epoch-started-(last-mono)*1000)<=250)
        return row

    @classmethod
    def archive(cls,value,store,root,binding,run,role,subject,lock,*,child_run,fixture_url,ticket,baseline,logout_before,historical_rows=None):
        class Frozen(PrivateFeatureState):
            def read(_self):return deepcopy(value)
            def write(_self,*_args):need(False)
            def discard(_self,*_args):need(False)
        return cls(Frozen(store.path),root,binding,run,role,subject,lock,_archived_guard,lambda:need(False),lambda:need(False),
            child_run=child_run,fixture_url=fixture_url,ticket=ticket,baseline=baseline,logout_before=logout_before,historical=True,historical_rows=historical_rows)


# These are the actual skipped parser dependencies, not a source inventory.
from adapters import native_feature_observation as native_source,native_account_observation as account_native
from adapters import native_animation_history as animation_native,recorded_preview_history as recorded_native
from adapters import native_clock_join as clock_source
from adapters.script_feature import history as history_source
from ios.adapters import avatar_bookmarks as bookmark_source,places_model as places_source
from ios.adapters import authentication_causality as causality_source,emote_native_prefix as prefix_source
from ios.adapters import authentication_origin as origin_source,login_source as login_parser
from feature_journeys import contract as feature_contract,scenarios as scenario_source
from ios.adapters import location_bookmarks as file_bookmarks
import re as parser_re
import json as parser_json
import hashlib as parser_hashlib

row_cache.bind(IOSAvatarPostLogoutReads,_archived_guard,
    [(IOSAvatarPostLogoutReads,name) for name in ('part','_record_fields','_historical_row','row_material','row_partial_original',
        'resolved_parts','retained_partial','account','account_original','acquisition','native_file','part_parents','part_tag','part_value','part_complete')]
    +[(IOSAvatarAccountReads,name) for name in ('__init__','parse','packet','_pending','pending','command','partial_file','envelope')]
    +[(avatar_state,name) for name in ('_validate','command','history','text','identity','session','tree','exact','integer','number','need','fresh')]
    +[(bookmark_source,'original_bytes'),(bookmark_source,'stable_file'),(file_bookmarks,'original_bytes'),(places_source,'tree'),(places_source,'text')]
    +[(native_source,name) for name in ('validate','exact','integer','number','fresh','need')]
    +[(account_native,name) for name in ('validate','accept')]
    +[(animation_native,name) for name in ('validate','_validate','accept','clip')]
    +[(recorded_native,name) for name in ('validate_history','accept_history','phases')]
    +[(causality_source,name) for name in ('check','arguments','identifier','need','validate','source_nonce','accept','fixture_origin')]
    +[(origin_source,'origin'),(login_parser,'nonce')]
    +[(prefix_source,name) for name in ('follow','_follow')]
    +[(feature_contract,name) for name in ('arguments','identifier','operation_parts','actions','expand','context','typed_equal','exact')]
    +[(scenario_source,'actions'),(scenario_source,'expand')]
    +[(clock_source,'digest')]
    +[(history_source,name) for name in ('canonical','same','pack','unpack')]
    +[(account_source,name) for name in ('validate','exact','integer','need','number','digest','pack','unpack','same','context','identifier')]
    +[(parser_re,'fullmatch'),(parser_json,'dumps'),(parser_json,'loads')]
    +[(globals(),name) for name in ('native','native_prefix','account_causality','exact','integer','need','number','canonical','same','digest')]
    +[(OriginalFrameStore,name) for name in ('__init__','read','original','file','path','key','bound','now')]
    +[(PrivateFeatureState,name) for name in ('read','_parent')]
    +[(AvatarRecordCache,name) for name in ('read','_read','signatures','absent')],
    [(module,name,'data') for module,names in (
        (avatar_state,('VERSION','READS','ACTION','LIMIT')),(account_source,('VERSION',)),
        (native_source,('LIMIT','BOUND_CLOCK_VERSION')),
        (account_native,('VERSION','SIGNALS','REPLIES','FIELDS','BOOLEANS','EVENT_FIELDS')),
        (recorded_native,('FIELDS','ACTIVE','TERMINAL','NEXT')),(causality_source,('VERSION','EMPTY')),
        (bookmark_source,('VERSION','SOURCE')),(places_source,('VERSION','LIMIT')),
        (feature_contract,('VERSION',)),(file_bookmarks,('FILE_LIMIT','REASONS')))
        for name in names]
    +[(globals(),name,'identity') for name in ('IOSAvatarAccountReads','avatar_state','account_source','native','native_prefix','account_causality','OriginalFrameStore','PrivateFeatureState','AvatarRecordCache')]
    +[(module,name,'identity') for module,names in (
        (parser_re,('fullmatch',)),(parser_json,('dumps','loads')),(parser_hashlib,('sha256',)),
        (avatar_state,('json','re','IOSPlacesModel')),(native_source.math,('isfinite',)),
        (feature_contract,('HEX','SCENARIOS')),(scenario_source,('SCENARIOS',)),(account_source,('validate','_native')))
        for name in names])
