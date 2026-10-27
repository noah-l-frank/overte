"""One-attempt readonly Assets world/parser originals on each actual target.

No phase/public actor verdict or GPU acquisition is provided by this collector.
Unknown native reads and incomplete actual file prefixes stay owned. It uses
the existing strict original/raw codecs without changing their literal defaults.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_clock_join import NativeClockAcquisition
from adapters.native_feature_observation import NativeFeatureObservation,decode,exact,integer,need,validate as native_packet
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.original_frame_store import OriginalFrameStore
from adapters.script_feature.history import pack,unpack,same
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.contract import identifier
from ios.adapters import create_state,emote_world,assets_model_origin,assets_scene_facts as facts
from ios.adapters.assets_budget import operation
from ios.adapters.assets_model_raw_sources import ModelRawSources
from ios.adapters.assets_model_sources import AssetsModelSources
from ios.adapters.graphics_history import follow_native,restore_native

VERSION=1
NAMES={'primary':'primary','actor':'actor','actor-primary':'read-primary'}


class SceneRawSources(ModelRawSources):
    SCHEMA_PREFIX='iosAssetsSceneRawSource'
    RECORD_KEY='iosAssetsSceneRawSourceRecordVersion'
    MIGRATION_KEY='iosAssetsSceneRawSourceMigrationVersion'
    def __init__(self,owner,guard,save):
        self.NAMESPACE='assets-scene-'+NAMES[owner.role]+'-native'
        self.MIGRATION_PREFIX=self.NAMESPACE+'-migration-'
        super().__init__(owner,owner.storage_role,guard,save)


class AssetsSceneSources(AssetsModelSources):
    """Reuse only bounded prefix/recovery mechanics, with separate schemas."""
    def __init__(self,store,binding,run,role,lock,guard,*,native,state,domain,origin,epoch_ms,monotonic):
        need(isinstance(store,PrivateFeatureState) and isinstance(lock,ScriptSourceLock) and callable(guard)
            and isinstance(native,NativeFeatureObservation) and native.ios and native.native_clock_bound and isinstance(state,create_state.IOSCreateState)
            and isinstance(domain,emote_world.IOSEmoteWorld) and isinstance(origin,assets_model_origin.IOSAssetsModelOrigin)
            and role in NAMES and callable(epoch_ms) and callable(monotonic))
        self.store,self.binding,self.run,self.role,self.lock=store,deepcopy(context(binding)),identifier(run),role,lock
        self.native,self.readers,self.check=native,dict(state=state,domain=domain,origin=origin),guard
        self.monotonic,self.epoch_ms=monotonic,epoch_ms;self.pid=int(binding['processIdentity']);self.storage_role='actor' if role=='actor' else 'primary'
        need(str(self.pid)==binding['processIdentity'] and all(reader.pid==self.pid for reader in (native,state,domain,origin))
            and store.path.name=='ios-assets-scene-'+run+'-'+role+'.json' and lock.path==store.path.with_name('script-feature-sources.lock'))
        lock.assert_held();self.previous=store.read();self.state=None;self.active=False;self._cached=[]
        self.raws=SceneRawSources(self,self.local_guard,self.save)
        self.originals=OriginalFrameStore(store.path.parent,binding,run,self.storage_role,self.local_guard,self.intent,
            namespace='assets-scene-'+NAMES[role]+'-source',schema_prefix='iosAssetsSceneSource',monotonic=monotonic)
        if self.previous is not None:
            self.state=self.decode(self.previous)
            if self._cached:
                last=self._cached[-1]['scene'];restore_native(self.native,last['clockJoin']['nativeAfter'])
                for kind,key in (('state','createAfter'),('domain','domain'),('origin','origin')):self.readers[kind].last=deepcopy(last['originals'][key])

    def local_guard(self):self.lock.assert_held();PrivateFeatureState(self.store.path)._parent();return True
    def guard(self):
        self.local_guard();need(self.check() is not False and self.native.guard() is not False and same(self.store.read(),self.previous));return True
    def reader_module(self,kind):return {'state':create_state,'domain':emote_world,'origin':assets_model_origin}[kind]
    def envelope(self):
        self.state['rawSources']=self.raws.manifest()
        return dict(iosAssetsSceneSourcesVersion=VERSION,binding=self.binding,runId=self.run,role=self.role,payload=pack([self.state]))

    def decode(self,value):
        exact(value,{'iosAssetsSceneSourcesVersion','binding','runId','role','payload'})
        need(type(value['iosAssetsSceneSourcesVersion']) is int and value['iosAssetsSceneSourcesVersion']==VERSION
            and same(value['binding'],self.binding) and value['runId']==self.run and value['role']==self.role)
        rows=unpack(value['payload']);need(len(rows)==1);state=rows[0];exact(state,{'frames','pending','interrupted','nextIndex','rawSources'})
        self.raws.load(state['rawSources']);need(type(state['frames']) is list and len(state['frames'])<=32
            and type(state['interrupted']) is list and len(state['interrupted'])<=8 and integer(state['nextIndex'],1,41))
        frames=[];seen=set();previous=None;raw_seen=[]
        for reference in state['frames']:
            original=self.originals.expand(reference);need(original['index'] not in seen and original['index']<state['nextIndex']);seen.add(original['index'])
            frame=self.originals.read(original);self.frame(frame,previous);need(frame['index']==original['index']);frames.append(frame);previous=frame;raw_seen+=frame['rawRefs']
        for row in state['interrupted']:
            exact(row,{'index','pending'});need(integer(row['index'],1,state['nextIndex']-1) and row['index'] not in seen);seen.add(row['index'])
            self.pending(row['pending'],row['index']);raw_seen+=row['pending']['rawRefs']
        need(seen==set(range(1,state['nextIndex'])))
        if state['pending'] is not None:self.pending(state['pending'],state['nextIndex']);raw_seen+=state['pending']['rawRefs']
        need(len(raw_seen)==len(self.raws.refs) and sorted(raw_seen,key=lambda ref:ref['index'])==self.raws.refs)
        if self.raws.pending is not None:need(state['pending'] is not None and any(row['command']['commandId']==self.raws.pending['queryId'] for row in state['pending']['queries']))
        self._cached=frames;return state

    def frame(self,value,previous=None):
        exact(value,{'assetSceneOriginalVersion','index','queries','rawRefs','scene'})
        need(type(value['assetSceneOriginalVersion']) is int and value['assetSceneOriginalVersion']==VERSION and integer(value['index'],1,40))
        self.pending(dict(queries=value['queries'],rawRefs=value['rawRefs'],original=None,snapshot=None),value['index'])
        sample=facts.scene(value['scene']);need(sample['runId']==self.run and sample['role']==self.role and same(sample['binding'],self.binding))
        records=[self.raws.read_record(reference) for reference in value['rawRefs']];clocks=[];external=[]
        for row in value['queries']:
            query=row['command'];self.query(row)
            matches=[record['raw'] for record in records if same(record['query'],query) and decode(record['raw'],limit=262144).get('requestId')==query['commandId']]
            need(matches and all(raw==matches[0] for raw in matches));packet=decode(matches[0],limit=262144)
            if row['kind']=='clock':native_packet(packet,query['commandId'],self.pid,packet['capturedEpochMs']);clocks.append(packet)
            else:self.reader_module(row['kind']).validate(packet,query,self.pid);external.append(packet)
        original=sample['originals'];need(len(clocks)>=2 and same(clocks[0],sample['clockJoin']['nativeBefore']) and same(clocks[-1],sample['clockJoin']['nativeAfter'])
            and same(external,[original[key] for key in ('createBefore','domain','origin','createAfter')]))
        for before,after in zip(clocks,clocks[1:]):follow_native(before,after)
        if previous is not None:
            old=previous['scene'];need(value['index']>previous['index'] and sample['clockJoin']['hostBeforeMonotonic']>=old['clockJoin']['hostAfterMonotonic'])
            follow_native(old['clockJoin']['nativeAfter'],sample['clockJoin']['nativeBefore'])
            for kind,key in (('state','createAfter'),('domain','domain'),('origin','origin')):
                packet=original['createBefore'] if kind=='state' else original[key]
                self.reader_module(kind).validate(packet,dict(schemaVersion=1,action=self.reader_module(kind).ACTION,commandId=packet['requestId'],runId=self.run),self.pid,
                    previous=old['originals'][key])
        return value

    @operation
    def reserve(self):
        self.guard();need(self.state is None);self.state=dict(frames=[],pending=None,interrupted=[],nextIndex=1,rawSources=self.raws.manifest());self.save()

    @operation
    def recover_capture(self):
        self.guard();super().recover_capture();return deepcopy(self._cached[-1]['scene'])

    @operation
    def capture(self,host_barrier):
        need(self.state is not None and self.state['pending'] is None and self.raws.pending is None and len(self.state['frames'])<32 and not self.active);self.guard()
        self.state['pending']=dict(queries=[],rawRefs=[],original=None,snapshot=None);self.save();wrappers=[];self.active=True
        for kind,reader in [('clock',self.native),*self.readers.items()]:
            old_send,old_original=reader.send,reader.original;wrappers.append((reader,old_send,old_original))
            def send(query,kind=kind,old_send=old_send):
                need(len(self.state['pending']['queries'])<24);self.state['pending']['queries'].append(dict(kind=kind,command=deepcopy(query)));self.save();return old_send(query)
            def read(kind=kind,old_original=old_original):
                raw=old_original()
                if raw:
                    matches=[row for row in self.state['pending']['queries'] if row['kind']==kind];need(matches and len(self.state['pending']['rawRefs'])<24)
                    self.raws.capture(matches[-1]['command'],raw);self.raws.accept_capture();self.state['pending']['rawRefs'].append(deepcopy(self.raws.refs[-1]));self.save()
                return raw
            reader.send,reader.original=send,read
        try:
            clock=NativeClockAcquisition(self.native,epoch_ms=self.epoch_ms,monotonic=self.monotonic);clock.begin(host_barrier)
            originals=dict(nativeBarrier=deepcopy(clock.started['nativeBefore']),createBefore=self.readers['state'].read(self.run),
                domain=self.readers['domain'].read(self.run),origin=self.readers['origin'].read(self.run),createAfter=self.readers['state'].read(self.run))
            sample=dict(assetSceneSourceFrameVersion=VERSION,binding=self.binding,runId=self.run,role=self.role,
                clockJoin=clock.finish(originals,[('nativeBarrier','capturedEpochMs')]),originals=originals)
            frame=dict(assetSceneOriginalVersion=VERSION,index=self.state['nextIndex'],queries=deepcopy(self.state['pending']['queries']),rawRefs=deepcopy(self.state['pending']['rawRefs']),scene=sample)
            self.frame(frame,self._cached[-1] if self._cached else None);reference=self.originals.write(self.state['nextIndex'],frame)
            self.state['frames'].append(reference);self.state['pending']=None;self.state['nextIndex']+=1;self.save();return deepcopy(sample)
        except BaseException as primary:
            if self.state['pending'] is not None and self.state['pending']['original'] is not None:
                try:self.state['pending']['snapshot']=self.prefix(self.state['pending']['original']);self.save()
                except BaseException as secondary:primary.add_note('Retaining Assets scene prefix also failed: '+type(secondary).__name__)
            raise
        finally:
            self.active=False
            for reader,send,original in wrappers:reader.send,reader.original=send,original
