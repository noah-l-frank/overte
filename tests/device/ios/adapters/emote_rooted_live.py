"""Durable original cleanup cuts for the existing Emote terminal window.

Only small inode-bound references enter metadata. Each immutable record stores
the actual component-envelope snapshot, never a copied measured public answer.
Reads rederive that answer from original native/input/file/PNG evidence.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from contextlib import contextmanager
import os
from pathlib import Path
import re

from adapters.native_clock_join import digest
from adapters.native_feature_observation import exact,integer,need
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.original_frame_store import OriginalFrameStore
from adapters.script_feature.history import pack,unpack,same
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.contract import identifier,result
from ios.adapters.emote_rooted_archive import capture,read,grouped
from ios.adapters.emote_rooted_retirement import IOSEmoteRootedKeyedRetirement
from ios.adapters.avatar_record_cache import AvatarRecordCache
from ios.adapters.emote_archive_round import validation_batch

VERSION=1
LIMIT=96


def sha(value):need(type(value) is str and re.fullmatch('[0-9a-f]{64}',value))


class IOSEmoteRootedLive:
    Owner=IOSEmoteRootedKeyedRetirement
    FORMAT_VERSION=VERSION

    def capture_snapshot(self,reference):return capture(self.owner,reference)

    def read_snapshot(self,snapshot):return read(snapshot,lock=self.lock,primary_lock=self.primary_lock)

    def group_snapshots(self,snapshots):return grouped(snapshots,lock=self.lock,primary_lock=self.primary_lock)

    def __init__(self,owner):
        need(type(owner) is self.Owner and not owner.historical)
        self.owner,self.historical=owner,False
        self.configure(root=owner.root,binding=owner.binding,primary_binding=owner.primary_binding,run=owner.run,role=owner.role,
            fixture_url=owner.fixture_url,phase_instance=owner.phase_instance,policy=owner.policy,
            store=PrivateFeatureState(owner.store.path.with_name('ios-emote-'+owner.role+'-'+owner.run+'-terminal-live.json')),
            lock=owner.lock,primary_lock=owner.primary_lock)
        self.previous=self.store.read();self.state=dict(records=[],pending=None)
        self.originals=self.original_store()
        if self.previous is not None:self.state=self.decode(self.previous)
        else:need(not any(self.root.glob('emote-rooted-live-frame-inputs-'+self.run+'-'+self.role+'-*.json')))

    @classmethod
    def archive(cls,value,*,store,lock,primary_lock):
        obj=cls._archive_header(value,store=store,lock=lock,primary_lock=primary_lock)
        obj.state=obj.decode(value);return obj

    @classmethod
    @contextmanager
    def archive_scope(cls,value,*,store,lock,primary_lock):
        obj=cls._archive_header(value,store=store,lock=lock,primary_lock=primary_lock)
        with obj.decoding(value) as state:
            obj.state=state;yield obj

    @classmethod
    def _archive_header(cls,value,*,store,lock,primary_lock):
        need(type(value) is dict);obj=object.__new__(cls);obj.owner,obj.historical=None,True
        obj.configure(root=value.get('artifactRoot'),binding=value.get('binding'),primary_binding=value.get('primaryBinding'),
            run=value.get('runId'),role=value.get('role'),fixture_url=value.get('fixtureUrl'),phase_instance=value.get('phaseInstance'),
            policy=value.get('imagePolicy'),store=store,lock=lock,primary_lock=primary_lock)
        obj.previous=store.read();need(same(obj.previous,value));obj.originals=obj.original_store()
        return obj

    def configure(self,*,root,binding,primary_binding,run,role,fixture_url,phase_instance,policy,store,lock,primary_lock):
        need(type(root) is str or isinstance(root,Path))
        self.root,self.binding,self.primary_binding,self.run,self.role=Path(root),deepcopy(context(binding)),deepcopy(context(primary_binding)),identifier(run),role
        self.store,self.lock,self.primary_lock,self.failed=store,lock,primary_lock,False
        need(type(fixture_url) is str and type(policy) is dict and policy.get('source')=='world-render-target')
        self.fixture_url,self.phase_instance,self.policy=fixture_url,identifier(phase_instance),deepcopy(policy)
        self.cache=AvatarRecordCache();self.prepared=None
        need(isinstance(store,PrivateFeatureState) and isinstance(lock,ScriptSourceLock) and isinstance(primary_lock,ScriptSourceLock)
            and self.root.is_absolute() and self.root.resolve()==self.root and self.root.is_dir() and role in ('primary','actor')
            and store.path==lock.path.parent/('ios-emote-'+role+'-'+self.run+'-terminal-live.json'))
        lock.assert_held();primary_lock.assert_held()

    def original_store(self):
        return OriginalFrameStore(self.root,self.binding,self.run,self.role,self.file_guard,self.intent,
            namespace='emote-rooted-live',schema_prefix='iosEmoteRootedLive',kind='inputs')

    def envelope(self,state):
        return dict(iosEmoteRootedLiveVersion=self.FORMAT_VERSION,binding=deepcopy(self.binding),primaryBinding=deepcopy(self.primary_binding),
            runId=self.run,role=self.role,fixtureUrl=self.fixture_url,phaseInstance=self.phase_instance,imagePolicy=deepcopy(self.policy),
            artifactRoot=str(self.root),sourceLock=str(self.lock.path),primaryLock=str(self.primary_lock.path),payload=pack([state]))

    def bound(self):
        self.file_guard();need(not self.failed and same(self.store.read(),self.previous));return True

    def file_guard(self):
        self.lock.assert_held();self.primary_lock.assert_held();return True

    def save(self):
        need(not self.historical);self.bound();value=self.envelope(self.state)
        try:
            self.store.write(value,self.previous);need(same(self.store.read(),value));self.previous=deepcopy(value)
        except Exception:self.failed=True;raise

    def intent(self,kind,original):
        need(not self.historical and kind=='original' and self.state['pending'] is not None)
        self.originals.original(original);need(original['index']==self.state['pending']['index'])
        self.state['pending']['original']=deepcopy(original);self.save()

    def snapshot_context(self,snapshot):
        need(type(snapshot) is dict and same(snapshot.get('binding'),self.binding) and same(snapshot.get('primaryBinding'),self.primary_binding)
            and snapshot.get('runId')==self.run and snapshot.get('role')==self.role and snapshot.get('artifactRoot')==str(self.root)
            and snapshot.get('fixtureUrl')==self.fixture_url and snapshot.get('phaseInstance')==self.phase_instance
            and same(snapshot.get('imagePolicy'),self.policy)
            and snapshot.get('stateRoot')==str(self.lock.path.parent) and snapshot.get('sourceLock')==str(self.lock.path)
            and snapshot.get('primaryLock')==str(self.primary_lock.path))

    def measurement(self,snapshot):
        self.snapshot_context(snapshot)
        if self.prepared is not None:return self.prepared.read(snapshot)
        return self.read_snapshot(snapshot)

    def record(self,reference):
        self.bound()
        with self.read_batch():
            return self.cache.read(dict(namespace='emote-rooted-live-record',reference=reference),lambda:self.read_record(reference))

    def read_batch(self):
        return validation_batch(dict(artifactRoot=str(self.root),stateRoot=str(self.store.path.parent)),
            lock=self.lock,primary_lock=self.primary_lock)

    def read_frame(self,reference):
        frame=self.originals.read(self.originals.expand(reference))
        exact(frame,{'iosEmoteRootedLiveRecordVersion','snapshot','measurementSha256'})
        need(type(frame['iosEmoteRootedLiveRecordVersion']) is int and frame['iosEmoteRootedLiveRecordVersion']==self.FORMAT_VERSION)
        self.snapshot_context(frame['snapshot']);sha(frame['measurementSha256']);return frame

    def read_record(self,reference):
        frame=self.read_frame(reference)
        measured=self.measurement(frame['snapshot']);need(digest(measured)==frame['measurementSha256'])
        return dict(reference=deepcopy(reference),measurement=measured)

    def pending(self,value,index):
        exact(value,{'index','keyedReference','snapshotSha256','measurementSha256','original'})
        need(type(value['index']) is int and value['index']==index and index<=LIMIT)
        exact(value['keyedReference'],{'index','sha256'});need(integer(value['keyedReference']['index'],1,128))
        for field in ('snapshotSha256','measurementSha256'):sha(value[field])
        sha(value['keyedReference']['sha256'])
        if value['original'] is not None:
            original=self.originals.original(value['original']);need(original['index']==index)
        return value

    def decode(self,value):
        with self.decoding(value) as state:return state

    @contextmanager
    def decoding(self,value):
        with self.read_batch():
            state=self.structure(value)
            snapshots=[self.read_frame(reference)['snapshot'] for reference in state['records']]
            if not snapshots:
                yield self.decode_state(value);return
            need(self.prepared is None)
            with self.group_snapshots(snapshots) as prepared:
                self.prepared=prepared
                try:yield self.decode_state(value)
                finally:self.prepared=None

    def structure(self,value):
        exact(value,set(self.envelope(dict(records=[],pending=None))));rows=unpack(value['payload'])
        need(type(value['iosEmoteRootedLiveVersion']) is int and value['iosEmoteRootedLiveVersion']==self.FORMAT_VERSION
            and len(rows)==1 and same(value,self.envelope(rows[0])))
        state=rows[0];exact(state,{'records','pending'});need(type(state['records']) is list and len(state['records'])<=LIMIT)
        return state

    def decode_state(self,value):
        state=self.structure(value)
        previous=None
        for index,reference in enumerate(state['records'],1):
            need(reference['index']==index);measured=self.record(reference)['measurement']
            if previous is not None:self.follows(previous,measured)
            previous=measured
        if state['pending'] is not None:self.pending(state['pending'],len(state['records'])+1)
        if not self.historical:
            expected={self.originals.path(self.originals.expand(reference)) for reference in state['records']}
            if state['pending'] is not None and state['pending']['original'] is not None:
                path=self.originals.path(state['pending']['original'])
                if os.path.lexists(path):expected.add(path)
            need(set(self.root.glob('emote-rooted-live-frame-inputs-'+self.run+'-'+self.role+'-*.json'))==expected)
        return deepcopy(state)

    @staticmethod
    def follows(previous,current):
        a,b=previous['public'],current['public']
        need(a['sequence']<b['sequence'] and a['capturedEpochMs']<=b['capturedEpochMs']
            and previous['ticket']==current['ticket']
            and previous['acquisition']['hostAfterMonotonic']<=current['acquisition']['hostBeforeMonotonic']
            and previous['acquisition']['hostAfterEpochMs']<=current['acquisition']['hostBeforeEpochMs'])

    def complete(self,reference):
        pending=self.state['pending'];need(pending is not None and reference['index']==pending['index'])
        row=self.record(reference);frame=self.originals.read(self.originals.expand(reference));snapshot=frame['snapshot']
        need(same(snapshot['reference'],pending['keyedReference']) and digest(snapshot)==pending['snapshotSha256']
            and frame['measurementSha256']==pending['measurementSha256'])
        if self.state['records']:self.follows(self.record(self.state['records'][-1])['measurement'],row['measurement'])
        self.state['records'].append(deepcopy(reference));self.state['pending']=None;self.save();return row

    def recover(self):
        """Adopt only the same fully written file with an observed file birth."""
        need(not self.historical);self.bound();pending=self.state['pending']
        if pending is None:return None
        original=pending['original'];need(original is not None and original['phase'] in ('opened','saved'))
        self.originals.read(original)
        return self.complete(self.originals.compact(dict(original,phase='saved')))

    def append(self,reference):
        need(not self.historical);self.bound();self.owner.current()
        if self.state['pending'] is not None:
            pending=deepcopy(self.state['pending'])
            if pending['original'] is not None:self.recover()
            else:
                # No file write was attempted. Only an identical actual owner
                # snapshot can resume this private save; no input/query occurs.
                snapshot=self.capture_snapshot(reference);measured=self.measurement(snapshot)
                need(same(reference,pending['keyedReference']) and digest(snapshot)==pending['snapshotSha256']
                    and digest(measured)==pending['measurementSha256'])
        snapshot=self.capture_snapshot(reference);measured=self.measurement(snapshot)
        if self.state['records']:
            last=self.record(self.state['records'][-1]);frame=self.originals.read(self.originals.expand(last['reference']))
            if same(snapshot,frame['snapshot']):need(same(measured,last['measurement']));return last
            self.follows(last['measurement'],measured)
        index=len(self.state['records'])+1;need(index<=LIMIT)
        pending=dict(index=index,keyedReference=deepcopy(reference),snapshotSha256=digest(snapshot),measurementSha256=digest(measured),original=None)
        if self.state['pending'] is not None:need(same(self.state['pending'],pending))
        else:self.state['pending']=pending;self.save()
        frame=dict(iosEmoteRootedLiveRecordVersion=self.FORMAT_VERSION,snapshot=snapshot,measurementSha256=digest(measured))
        return self.complete(self.originals.write(index,frame))

    def selected_many(self,values):
        """Revalidate each selected original, preserving its native clocks."""
        self.bound();need(self.state['pending'] is None and type(values) is list and 1<=len(values)<=LIMIT)
        requested={}
        for value in values:
            result('feature.emotes.observe',value);need(value['runId']==self.run and value['sequence'] not in requested)
            requested[value['sequence']]=value
        matched={}
        for reference in self.state['records']:
            row=self.record(reference);public=row['measurement']['public'];sequence=public['sequence']
            if sequence in requested:
                need(sequence not in matched and same(public,requested[sequence]));matched[sequence]=row
        need(set(matched)==set(requested));self.bound()
        return [deepcopy(matched[value['sequence']]) for value in values]
