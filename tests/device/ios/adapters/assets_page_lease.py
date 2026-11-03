"""Independent shared Asset Browser page authority across owned episodes.

Normal Picker captures remain the actual source. This parent owns only the
existing page root/window and original attachment/transfer history; it cannot
infer client files, callbacks, Model/server/OS retirement or whole completion.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import time
import secrets
import re
from adapters.native_feature_observation import exact,integer,need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.original_frame_store import OriginalFrameStore
from adapters.script_feature.history import same,pack,unpack
from ios.adapters.normal_input import observation
from adapters.script_feature.lock import ScriptSourceLock
from ios.adapters.assets_episodes import AssetsEpisodes,AssetsEpisodeScope,PLAN
from ios.adapters.assets_picker import OwnedAssetsPicker,root
from ios.adapters.assets_controls import project

VERSION=1
STABLE=('rootId','role','componentSource','ownerRootId','windowId','modelId','firstObservedEpochMs')


class OwnedAssetsPageLease:
    OWNER_VERSION=VERSION
    def archive_context(self,value):need(value is None)
    @classmethod
    def from_archive(cls,episodes,store,lock,pickers,*,context=None,snapshot_scope=None,monotonic=time.monotonic):
        # Pure codec assembly: no live/native constructors, source queries,
        # clocks, inputs, recovery or writes. Caller supplies typed Files4 and
        # Picker2 skeletons rooted in independently held episode scopes.
        need(type(episodes) is AssetsEpisodes and isinstance(store,PrivateFeatureState)
            and lock is episodes.locks['primary'] and type(pickers) is dict)
        owner=object.__new__(cls);owner.episodes,owner.store,owner.lock=episodes,store,lock
        owner.binding=deepcopy(episodes.context['roles']['primary']['binding'])
        owner.run,owner.role,owner.monotonic,owner.historical=episodes.run,'primary',monotonic,True
        owner.pickers=dict(pickers);owner.previous=store.read();owner.state=None;owner.archive_context(context)
        owner.snapshot_scope=snapshot_scope
        if snapshot_scope is not None:
            from ios.adapters.assets_historical_picker_snapshots import HistoricalPickerSnapshots
            need(type(snapshot_scope) is HistoricalPickerSnapshots);snapshot_scope.bind(owner)
        need(store.path==Path(episodes.context['roles']['primary']['stateRoot'])/('ios-assets-page-lease-'+owner.run+'-primary.json'))
        for picker in owner.pickers.values():picker.page_lease=owner
        owner.originals=OriginalFrameStore(store.path.parent,owner.binding,owner.run,'primary',owner.bound,owner.intent,
            namespace='assets-page-lease',schema_prefix='iosAssetsPageLeaseSource',monotonic=monotonic)
        owner.bound();need(owner.previous is not None);owner.state=owner.decode(owner.previous)
        for picker in owner.pickers.values():picker.state=owner.decode_picker_snapshot(picker,picker.previous)
        owner.state=owner.decode(owner.previous);return owner
    def __init__(self,episodes,store,lock,*,pickers=None,historical=False,monotonic=time.monotonic):
        need(type(episodes) is AssetsEpisodes and isinstance(store,PrivateFeatureState) and isinstance(lock,ScriptSourceLock)
            and lock is episodes.locks['primary'] and type(historical) is bool and callable(monotonic))
        self.episodes,self.store,self.lock=episodes,store,lock;self.binding=deepcopy(episodes.context['roles']['primary']['binding'])
        self.run,self.role,self.monotonic=episodes.run,'primary',monotonic;self.historical=historical
        self.pickers={} if pickers is None else dict(pickers);self.previous=store.read();self.state=None;self.snapshot_scope=None
        need(store.path==Path(episodes.context['roles']['primary']['stateRoot'])/('ios-assets-page-lease-'+self.run+'-primary.json'))
        self.originals=OriginalFrameStore(store.path.parent,self.binding,self.run,'primary',self.bound,self.intent,
            namespace='assets-page-lease',schema_prefix='iosAssetsPageLeaseSource',monotonic=monotonic)
        if self.previous is not None:self.state=self.decode(self.previous)
    def bound(self):
        self.lock.assert_held();self.episodes.guard();need(same(self.store.read(),self.previous));return True
    def live(self,scope):
        self.bound();need(not self.historical and type(scope) is AssetsEpisodeScope and scope.owner is self.episodes
            and self.episodes.selected.state==dict(phase='selected') and self.episodes.state['entries'][-1]['index']==scope.index)
        scope.guard();scope.locks['primary'].assert_held();return True
    def reserve(self):
        self.bound();need(not self.historical and self.state is None)
        self.state=dict(phase='reserved',token=secrets.token_hex(32),origin=None,records=[],attachments={},transfers={},closed=None,pending=None);self.save()
    def link(self):
        self.bound();need(self.state is not None)
        return dict(iosAssetsPageLeaseLinkVersion=1,path=str(self.store.path),token=self.state['token'])
    def identity(self):
        self.bound();need(self.state is not None and self.state['origin'] is not None)
        ref=self.originals.expand(self.state['origin']);row=self.originals.read(ref)
        return deepcopy(self.native_record(row,ref['index'])['page'])
    def context(self,scope,picker):
        need(type(scope) is AssetsEpisodeScope and scope.owner is self.episodes and isinstance(picker,OwnedAssetsPicker)
            and picker.lock is scope.locks['primary'] and same(picker.binding,self.binding)
            and picker.store.path==Path(scope.descriptor['directories']['primary']['stateRoot']['path'])/('ios-assets-'+self.run+'-primary-picker.json'))
        old=self.pickers.get(scope.index)
        if old is not None and old is not picker:
            # Fresh current-action transports may reassemble this same owned
            # episode. No stale metadata/context can inherit that authority.
            need(getattr(old,'episode',None) is scope and old.lock is picker.lock
                and old.files.store.path==picker.files.store.path
                and same(old.previous,picker.previous) and same(old.files.previous,picker.files.previous)
                and same(picker.store.read(),picker.previous) and same(picker.files.store.read(),picker.files.previous)
                and same(old.files.state,picker.files.state))
        self.pickers[scope.index]=picker
    def intent(self,kind,value):
        need(kind=='original' and self.state is not None and self.state['pending'] is not None)
        self.state['pending']['original']=deepcopy(value);self.save()
    def save(self):
        self.bound();need(not self.historical and same(self.store.read(),self.previous))
        value=dict(iosAssetsPageLeaseVersion=self.OWNER_VERSION,binding=self.binding,runId=self.run,role=self.role,payload=pack([self.state]))
        self.store.write(value,self.previous);self.previous=deepcopy(value)
    def native_record(self,row,index):
        exact(row,{'iosAssetsPageLeaseSourceVersion','index','episode','pickerPath','pickerSnapshot','captureIndex','page'})
        need(type(row['iosAssetsPageLeaseSourceVersion']) is int and row['iosAssetsPageLeaseSourceVersion']==VERSION and type(row['index']) is int and row['index']==index)
        picker=self.pickers.get(row['episode']['index']);need(picker is not None)
        scope=getattr(picker,'episode',None);need(type(scope) is AssetsEpisodeScope and scope.owner is self.episodes
            and same(row['episode'],scope.link()));self.context(scope,picker);need(str(picker.store.path)==row['pickerPath'] and same(picker.store.read(),picker.previous))
        current_rows=unpack(picker.previous['payload']);old_rows=unpack(row['pickerSnapshot']['payload']);need(len(current_rows)==len(old_rows)==1)
        current,old=current_rows[0],old_rows[0];need(type(current) is type(old) is dict and type(old.get('captures')) is list and type(current.get('captures')) is list
            and len(old['captures'])<=len(current['captures'])
            and same(old['captures'],current['captures'][:len(old['captures'])]) and same(row['pickerSnapshot']['binding'],self.binding))
        need(integer(row['captureIndex'],0,len(old['captures'])-1));packet=old['captures'][row['captureIndex']];observation(packet,int(self.binding['processIdentity']),packet['sampleEpochMs']);page=row['page']
        candidates=[item for item in project(packet)['inventory']['roots'] if item['rootId']==page['rootId'] and item['role']=='page'];need(len(candidates)==1 and same(page,candidates[0]))
        if page['alive']:need(page['visible'] and not page['busy'] and not page['bundleRequest'] and not page['pendingBundle'] and not page['destinationOpen'])
        return row
    def decode_picker_snapshot(self,picker,value):
        if self.snapshot_scope is None:return picker.decode(value)
        return self.snapshot_scope.decode(self,picker,value)
    def record(self,row,index):
        self.native_record(row,index);picker=self.pickers[row['episode']['index']]
        self.decode_picker_snapshot(picker,picker.previous);self.decode_picker_snapshot(picker,row['pickerSnapshot']);return row
    def read(self,ref):
        full=self.originals.expand(ref);row=self.originals.read(full);return self.record(row,full['index'])
    def decode(self,value):
        exact(value,{'iosAssetsPageLeaseVersion','binding','runId','role','payload'})
        need(type(value['iosAssetsPageLeaseVersion']) is int and value['iosAssetsPageLeaseVersion']==self.OWNER_VERSION
            and same(value['binding'],self.binding) and value['runId']==self.run and value['role']=='primary')
        states=unpack(value['payload']);need(len(states)==1);state=states[0];exact(state,{'phase','token','origin','records','attachments','transfers','closed','pending'})
        need(state['phase'] in ('reserved','open','closing','closed') and type(state['token']) is str and re.fullmatch('[a-f0-9]{64}',state['token'])
            and type(state['records']) is list and 0<=len(state['records'])<=24
            and type(state['attachments']) is dict and type(state['transfers']) is dict)
        self.state=state
        if not state['records']:
            need(state['phase']=='reserved' and state['origin'] is None and not state['attachments'] and not state['transfers'] and state['closed'] is None)
            self.pending(state,1)
            return state
        rows=[self.read(ref) for ref in state['records']];need(same(state['origin'],state['records'][0]) and rows[0]['page']['alive'])
        original=rows[0]['page']
        for row in rows:
            need(row['page']['rootId']==original['rootId'])
            need(all(row['page'][key]==original[key] for key in ('rootId','role','componentSource','ownerRootId','firstObservedEpochMs')))
            if row['page']['alive']:need(all(row['page'][key]==original[key] for key in STABLE))
        for name,mapping in (('attachments',state['attachments']),('transfers',state['transfers'])):
            for index,ref in mapping.items():
                need(type(index) is str and index.isdecimal() and same(ref,state['records'][self.originals.expand(ref)['index']-1]))
                row=rows[self.originals.expand(ref)['index']-1];need(row['episode']['index']==int(index) and row['page']['alive'])
                if name=='transfers':
                    picker=self.pickers[int(index)];snapshot=unpack(row['pickerSnapshot']['payload'])[0]
                    need(index in state['attachments'] and snapshot['phase']==picker.retirement_phase() and picker.files.state['phase']=='retired')
        keys=set(state['attachments']);need(keys=={str(i) for i in range(1,len(keys)+1)})
        need(set(state['transfers'])<=keys and len(keys)-len(state['transfers'])<=1)
        if state['closed'] is not None:
            self.all_transferred(state)
            need(state['phase']=='closed' and same(state['closed'],state['records'][-1]) and not rows[-1]['page']['alive'])
        else:need(state['phase']!='closed')
        self.pending(state,len(state['records'])+1)
        return state
    def pending(self,state,index):
        pending=state['pending']
        if pending is None:return
        exact(pending,{'row','original'});self.record(pending['row'],index)
        reference=pending['original']
        if reference is not None:
            from ios.adapters.assets_model_sources import AssetsModelSources
            self.originals.original(reference);need(reference['index']==index)
            AssetsModelSources.prefix(self,reference)
            if reference['phase']=='saved':need(same(self.originals.read(reference),pending['row']))
    def all_transferred(self,state):
        entries=self.episodes.state['entries'];wanted={str(i) for i in range(1,len(PLAN)+1)}
        need(len(entries)==len(PLAN) and all(row['phase']=='ready' for row in entries)
            and set(state['attachments'])==set(state['transfers'])==wanted)
    def recover_capture(self):
        # Only a genuinely saved complete original may finish its bookkeeping.
        # Planned/opened prefixes remain owned; no new UI query/write/retry.
        self.bound();need(not self.historical and self.state is not None and self.state['pending'] is not None)
        pending=self.state['pending'];reference=pending['original'];need(reference is not None and reference['phase']=='saved')
        self.pending(self.state,len(self.state['records'])+1)
        compact=self.originals.compact(reference);self.state['records'].append(compact)
        if self.state['origin'] is None:self.state['origin']=compact;self.state['phase']='open'
        self.state['pending']=None;self.save();return compact
    def capture(self,scope,picker):
        self.live(scope);self.context(scope,picker);need(self.state is not None and self.state['phase'] in ('reserved','open','closing') and self.state['pending'] is None)
        current=picker.capture();pages=[row for row in current['inventory']['roots'] if row['role']=='page']
        if self.state['origin'] is None:need(scope.index==1);page=root(current,'page')
        else:
            identity=self.identity();pages=[row for row in pages if row['rootId']==identity['rootId']];need(len(pages)==1);page=pages[0]
        row=dict(iosAssetsPageLeaseSourceVersion=VERSION,index=len(self.state['records'])+1,episode=scope.link(),pickerPath=str(picker.store.path),
            pickerSnapshot=deepcopy(picker.previous),captureIndex=len(picker.state['captures'])-1,page=deepcopy(page))
        self.state['pending']=dict(row=row,original=None);self.save();self.record(row,row['index'])
        ref=self.originals.write(row['index'],row);self.state['records'].append(ref)
        if self.state['origin'] is None:self.state['origin']=ref;self.state['phase']='open'
        self.state['pending']=None;self.save();return ref
    def attach(self,scope,picker):
        self.live(scope);self.context(scope,picker)
        if self.state is not None and str(scope.index) in self.state['attachments']:return self.read(self.state['attachments'][str(scope.index)])
        need(self.state is not None and set(self.state['attachments'])==set(self.state['transfers'])=={str(i) for i in range(1,scope.index)})
        ref=self.capture(scope,picker);need(self.read(ref)['page']['alive']);self.state['attachments'][str(scope.index)]=ref;self.save();return self.read(ref)
    def transferred(self,scope,picker):
        self.live(scope);need(self.state is not None and str(scope.index) in self.state['attachments'])
        if str(scope.index) in self.state['transfers']:return self.read(self.state['transfers'][str(scope.index)])
        need(picker.files.state['phase']=='retired' and picker.state['phase']==picker.retirement_phase())
        ref=self.capture(scope,picker);row=self.read(ref);snapshot=unpack(row['pickerSnapshot']['payload'])[0]
        need(row['page']['alive'] and snapshot['phase']==picker.retirement_phase())
        self.state['transfers'][str(scope.index)]=ref;self.save();return row
    def close(self,scope,picker):
        self.live(scope);need(scope.index==len(PLAN) and self.state is not None);self.all_transferred(self.state)
        if self.state['phase']=='closed':return self.read(self.state['closed'])
        self.state['phase']='closing';self.save();picker.close_shared_page()
        ref=self.capture(scope,picker);need(not self.read(ref)['page']['alive'])
        self.state.update(phase='closed',closed=ref);self.save();return self.read(ref)
