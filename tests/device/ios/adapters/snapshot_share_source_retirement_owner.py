"""Conditional source files, one-send slots and three independent quiet clocks."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import time
import uuid
from adapters.native_clock_join import digest
from adapters.native_feature_observation import decode,exact,integer,need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import pack,unpack,same
from ios.adapters.snapshot_capture_clock import operation
from ios.adapters.snapshot_share_owner import IOSSnapshotShareOwner,SnapshotSharePending
from ios.adapters.snapshot_share_inventory_owner import SnapshotShareSourceInventoryOwner
from ios.adapters.snapshot_share_query_owner import host_clock
from ios.adapters.snapshot_share_seal_owner import ShareAdmissionSealAction
from ios.adapters import snapshot_share_source_retirement as source


class ShareSourceRetireAction(ShareAdmissionSealAction):
    _fields={'snapshot.share.archive.source-retire':{'snapshot.share.archive.query'}}
    _store_prefix='share-source-retire-slot'
    _namespace='share-source-retirement-output'
    _schema='shareSourceRetirementOutput'
    _owner_key='snapshotShareSourceRetireUIActionVersion'
    _frame_key='snapshotShareSourceRetireUIOutputVersion'
    _output_control='snapshot.share.archive.source-retire'
    _output_locator='snapshot.share.archive.source-retirement-original'


class ShareSourceInspectAction(ShareAdmissionSealAction):
    _fields={'snapshot.share.archive.source-retire-inspect':{'snapshot.share.archive.query'}}
    _store_prefix='share-source-retire-inspection-slot'
    _namespace='share-source-absence-output'
    _schema='shareSourceAbsenceOutput'
    _owner_key='snapshotShareSourceRetireInspectionUIActionVersion'
    _frame_key='snapshotShareSourceRetireInspectionUIOutputVersion'
    _output_control='snapshot.share.archive.source-retire-inspect'
    _output_locator='snapshot.share.archive.source-retirement-observation-original'


class SnapshotShareSourceRetirementOwner:
    def __init__(self,share):
        need(isinstance(share,IOSSnapshotShareOwner) and not share.historical)
        self.bind_scope(share,share.archive.artifact_path,share.archive.admission.store)
        self.historical=False;self.ctx=share.archive;self.epoch_ms,self.monotonic=share.queries.epoch_ms,share.queries.monotonic;self.setup()
    def bind_scope(self,share,artifact_path,admission_store):
        self.share,self.lock,self.binding,self.run,self.fixture_url=share,share.archive_lock,deepcopy(share.archive_binding),share.run,share.fixture_url
        self.queries=share.queries
        self.inventory=SnapshotShareSourceInventoryOwner.history(PrivateFeatureState(share.archive_root/'share-source-inventory-owner.json'),share,
            artifact_path,admission_store) if share.historical else SnapshotShareSourceInventoryOwner(share)
        need(self.inventory.state['result'] is not None);self.inventory.proof();self.inventory_hash=digest(self.inventory.previous)
    @classmethod
    def history(cls,store,share,artifact_path,admission_store):
        need(isinstance(store,PrivateFeatureState) and isinstance(share,IOSSnapshotShareOwner) and share.historical)
        result=object.__new__(cls);result.bind_scope(share,artifact_path,admission_store);result.historical=True;result.ctx=None
        result.epoch_ms=lambda:time.time()*1000;result.monotonic=time.monotonic;result.setup(store);need(result.previous is not None);return result
    def setup(self,store=None):
        self.root=self.share.archive_root;self.store=store or PrivateFeatureState(self.root/'share-source-retirement-owner.json')
        need(self.store.path==self.root/'share-source-retirement-owner.json');self.lock.assert_held()
        self.previous=self.store.read();self.state=dict(nonce=None,before=[[]],retireSha256=None,after=[],result=None)
        if self.previous is not None:self.state=self.load(self.previous)
        else:self.inventory_paths(set())
    def guard(self):
        self.lock.assert_held();self.inventory.bound();need(same(self.store.read(),self.previous) and digest(self.inventory.previous)==self.inventory_hash);return True
    def check(self):
        self.guard()
        if not self.historical:self.ctx.probe(True)
        return True
    def envelope(self):return dict(snapshotShareSourceRetirementOwnerVersion=1,binding=self.binding,runId=self.run,fixtureUrl=self.fixture_url,
        inventoryOwnerSha256=self.inventory_hash,payload=pack([self.state]))
    def save(self):
        need(not self.historical);self.check();value=self.envelope();self.store.write(value,self.previous);need(same(value,self.store.read()));self.previous=deepcopy(value)
    def action(self,row=None,history=False):
        need(self.state['nonce'] is not None and (history or not self.historical));cls=ShareSourceRetireAction if row is None else ShareSourceInspectAction
        index=1 if row is None else row['index'];nonce=self.state['nonce'] if row is None else row['nonce']
        plan=dict(label='source-retire' if row is None else 'source-retirement-inspect-'+str(index),control=cls._output_control,selector=None,
            fields=[['snapshot.share.archive.query',nonce]])
        def guard():
            self.check()
            if not self.slot_issued(cls,index,plan):
                self.share.cleanup_fresh(self.state['before'][-1][-1] if row is None else row['queryIndex'])
            return True
        return cls(self.root,self.lock,self.binding,self.run,index,plan,self.guard if history else guard,
            client=None if history else self.ctx.client,session=None if history else self.ctx.session,
            epoch_ms=self.epoch_ms,monotonic=self.monotonic,historical=history)
    def slot_issued(self,cls,index,plan):
        # A frame's opened prefix is deliberately not a complete original yet.
        # Read only the exact independently durable dispatch envelope here.
        value=PrivateFeatureState(self.root/(cls._store_prefix+'-'+format(index,'04d')+'.json')).read()
        if value is None:return False
        exact(value,{cls._owner_key,'binding','runId','index','plan','payload'})
        need(type(value[cls._owner_key]) is int and value[cls._owner_key]==1 and same(value['binding'],self.binding)
            and value['runId']==self.run and type(value['index']) is int and value['index']==index and same(value['plan'],plan))
        rows=unpack(value['payload']);need(len(rows)==1 and type(rows[0]) is dict and type(rows[0].get('issued')) is bool
            and same(value['payload'],pack(rows)))
        return rows[0]['issued']
    def inventory_paths(self,allowed):
        for path in self.root.iterdir():
            if path.name.startswith(('share-source-retire-','share-source-retirement-','share-source-absence-')):need(path==self.store.path or path in allowed)
    def paths(self,action):
        result={action.store.path}
        if action.state['wire'] is not None:result.add(action.files.path(action.state['wire']))
        if action.state['proof'] is not None:result.add(action.files.path(action.files.expand(action.state['proof'])))
        return result
    def dispatch_original(self,action,index):
        if not action.state['issued']:return
        need(integer(index,1,len(self.queries.state['queries'])));self.share.cleanup_absent(index)
        frame,_packet=self.queries.frame(self.queries.state['queries'][index-1]);host_clock(action.state['before'],frame['hostAfter'])
        need(action.state['before']['epochMs']-frame['hostAfter']['epochMs']<3000
            and action.state['before']['monotonicMs']-frame['hostAfter']['monotonicMs']<3000)
    def load(self,value):
        exact(value,{'snapshotShareSourceRetirementOwnerVersion','binding','runId','fixtureUrl','inventoryOwnerSha256','payload'})
        rows=unpack(value['payload']);need(len(rows)==1 and type(value['snapshotShareSourceRetirementOwnerVersion']) is int and value['snapshotShareSourceRetirementOwnerVersion']==1)
        state=rows[0];exact(state,set(self.state));prior=self.state;self.state=state
        try:
            need(same(value,self.envelope()) and type(state['before']) is list and 1<=len(state['before'])<=16 and type(state['after']) is list and len(state['after'])<=32)
            allowed=set();last=0
            for group in state['before']:
                need(type(group) is list and len(group)<=3)
                for index in group:need(integer(index,last+1,len(self.queries.state['queries'])));last=index;self.share.cleanup_absent(index)
                if len(group)==3:self.queries.quiet_originals(group)
            if state['nonce'] is not None:
                need(type(state['nonce']) is str and len(state['nonce'])==36 and state['nonce'].startswith('ios-')
                    and all(char in '0123456789abcdef' for char in state['nonce'][4:]));action=self.action(history=True);allowed|=self.paths(action)
                if action.state['issued']:need(len(state['before'][-1])==3);self.dispatch_original(action,state['before'][-1][-1])
                if state['retireSha256'] is not None:need(digest(action.previous)==state['retireSha256']);self.retired()
            else:need(state['retireSha256'] is None and not state['after'] and state['result'] is None)
            need(not state['after'] or state['retireSha256'] is not None)
            if state['after']:source.qualified(self.retired()[0])
            for at,row in enumerate(state['after'],1):
                exact(row,{'index','nonce','queryIndex','sha256','qualified'});need(type(row['index']) is int and row['index']==at and row['qualified'] in (None,False,True)
                    and (row['qualified'] is None or type(row['qualified']) is bool))
                need(type(row['nonce']) is str and len(row['nonce'])==36 and row['nonce'].startswith('ios-') and all(char in '0123456789abcdef' for char in row['nonce'][4:]))
                if row['queryIndex'] is not None:need(integer(row['queryIndex'],last+1,len(self.queries.state['queries'])));last=row['queryIndex'];self.share.cleanup_absent(last)
                action=self.action(row,True);allowed|=self.paths(action)
                if action.state['issued']:need(row['queryIndex'] is not None);self.dispatch_original(action,row['queryIndex'])
                if row['sha256'] is not None:need(digest(action.previous)==row['sha256']);self.observed(row)
                if row['qualified'] is True:self.qualified(row)
            if state['result'] is not None:need(same(state['result'],self.proof()))
            self.inventory_paths(allowed)
        finally:self.state=prior
        return deepcopy(state)
    def retired(self):
        need(self.state['retireSha256'] is not None);action=self.action(history=True);need(digest(action.previous)==self.state['retireSha256'])
        raw=action.original();value=source.original(decode(raw.decode('utf-8')),self.state['nonce'],self.inventory)
        frame=action.files.read(action.files.expand(action.state['proof']))
        need(value['clockAfter']['monotonicMs']-value['clockBefore']['monotonicMs']<=frame['hostAfter']['monotonicMs']-frame['hostBefore']['monotonicMs']+250)
        return value,raw
    def observed(self,row):
        need(row['sha256'] is not None);retired,retired_raw=self.retired();previous=None;selected=None
        for item in self.state['after']:
            if item['index']>row['index']:break
            if item['sha256'] is None:continue
            action=self.action(item,True);need(digest(action.previous)==item['sha256']);raw=action.original()
            value=source.observation(decode(raw.decode('utf-8')),item['nonce'],retired,retired_raw,previous)
            frame=action.files.read(action.files.expand(action.state['proof']))
            need(value['clockAfter']['monotonicMs']-value['clockBefore']['monotonicMs']<=frame['hostAfter']['monotonicMs']-frame['hostBefore']['monotonicMs']+250)
            previous=value;selected=(value,frame)
        need(selected is not None);return selected
    def qualified(self,row):
        self.share.cleanup_absent(row['queryIndex']);self.action(row,True).qualified();value,_frame=self.observed(row);return source.absent(value)
    def proof(self):
        retired,_raw=self.retired();source.qualified(retired);selected=[row for row in self.state['after'] if row['qualified'] is True][-3:];need(len(selected)==3)
        values=[];hosts=[]
        for row in selected:
            self.qualified(row);value,frame=self.observed(row);values.append(value);hosts.append(dict(before=frame['hostBefore'],after=frame['hostAfter']))
        files=source.quiet(values,hosts,self.run);before=self.queries.quiet_originals(self.state['before'][-1]);after=self.queries.quiet_originals([row['queryIndex'] for row in selected])
        return dict(snapshotShareSourceFilesRetiredVersion=1,runId=self.run,inventoryOwnerSha256=self.inventory_hash,retirementSha256=digest(retired),
            extensionBefore=before,extensionAfter=after,fileQuiet=files,sourceFilesRetired=True,hostOriginalsRetained=True,
            archiveProcessRetirementRequired=True,sourceSDKRetirementRequired=True,captureCleanupRequired=True,wholeFeatureRequired=True)
    @operation
    def cleanup(self):
        need(not self.historical);self.check()
        if self.state['result'] is not None:return self.proof()
        if self.state['nonce'] is None:self.state['nonce']='ios-'+uuid.uuid4().hex;self.save()
        if not self.action(history=True).state['issued']:
            group=self.state['before'][-1]
            if len(group)==3:
                try:self.share.cleanup_fresh(group[-1])
                except NativeUIError:need(len(self.state['before'])<16);group=[];self.state['before'].append(group);self.save()
            while len(group)<3:
                if group:self.queries.sleep(1.6)
                rows=self.queries.state['queries'];last=rows[-1] if rows else None
                label=last['label'] if last is not None and last['phase']!='retained' and last['label'].startswith('source-before-') else 'source-before-'+str(len(rows)+1)
                self.queries.query(label,retired=True);index=self.queries.state['queries'][-1]['index'];self.share.cleanup_absent(index);group.append(index);self.save()
            self.queries.quiet_originals(group)
        action=self.action();action.execute()
        if self.state['retireSha256'] is None:self.state['retireSha256']=digest(action.previous);self.save()
        retired,_raw=self.retired();source.qualified(retired)
        while sum(row['qualified'] is True for row in self.state['after'])<3:
            rows=self.state['after']
            if rows and rows[-1]['qualified'] is None:row=rows[-1]
            else:
                if rows:self.queries.sleep(1.6)
                need(len(rows)<32);row=dict(index=len(rows)+1,nonce='ios-'+uuid.uuid4().hex,queryIndex=None,sha256=None,qualified=None);rows.append(row);self.save()
            if row['queryIndex'] is None:
                self.queries.query('source-after-'+str(row['index']),retired=True);row['queryIndex']=self.queries.state['queries'][-1]['index'];self.share.cleanup_absent(row['queryIndex']);self.save()
            if not self.action(row,True).state['issued']:
                try:self.share.cleanup_fresh(row['queryIndex'])
                except NativeUIError:row['qualified']=False;self.save();raise SnapshotSharePending('Actual source inspection admission is stale or unknown') from None
            action=self.action(row);action.execute()
            if row['sha256'] is None:row['sha256']=digest(action.previous);self.save()
            try:self.qualified(row)
            except NativeUIError:row['qualified']=False;self.save();raise SnapshotSharePending('Actual source-file absence remains historical or unqualified') from None
            row['qualified']=True;self.save()
        result=self.proof();self.state['result']=deepcopy(result);self.save();return result
