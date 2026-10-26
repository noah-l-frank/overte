"""Durable readonly native model/tree/lifetime acquisitions on existing routes.

Queries are owned before delivery. Native originals keep their actual raw bytes
and clocks; an interrupted read is retained and never rebracketed as complete.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import os
from adapters.native_clock_join import NativeClockAcquisition,validate_join
from adapters.native_feature_observation import NativeFeatureObservation,decode,exact,integer,need,validate as native_packet
from adapters.normal_feature_state import PrivateFeatureState
from adapters.original_frame_store import OriginalFrameStore
from adapters.original_file_reads import record as record_original_read
from adapters.script_feature.history import same,pack,unpack
from ios.adapters import create_state,create_work
from ios.adapters.assets_budget import operation
from ios.adapters.assets_usage_owner import OwnedAssetsUsage
from ios.adapters.assets_model_raw_sources import ModelRawSources
from ios.adapters.graphics_history import follow_native

VERSION=1


class AssetsModelSources:
    def __init__(self,usage,native,state_reader,work_reader,store,*,lock,epoch_ms,monotonic):
        need(isinstance(usage,OwnedAssetsUsage) and isinstance(native,NativeFeatureObservation) and native.ios
            and native is usage.source.clock and isinstance(state_reader,create_state.IOSCreateState) and isinstance(work_reader,create_work.IOSCreateWork)
            and isinstance(store,PrivateFeatureState) and callable(epoch_ms) and callable(monotonic)
            and native.pid==state_reader.pid==work_reader.pid==usage.source.files.native.pid);lock.assert_held()
        self.usage,self.native,self.readers,self.store,self.lock=usage,native,dict(state=state_reader,work=work_reader),store,lock
        self.epoch_ms,self.monotonic=epoch_ms,monotonic;self.previous=store.read();self.state=None;self._cached=[];self.active=False
        source=usage.source;self.binding,self.run,self.role=source.binding,source.files.run,source.role
        self.raws=ModelRawSources(self,source.role,self.local_guard,self.save)
        self.originals=OriginalFrameStore(store.path.parent,source.binding,source.files.run,source.role,self.guard,self.intent,
            namespace='assets-model-source',schema_prefix='iosAssetsModelSource',monotonic=monotonic)
        if self.previous is not None:
            self.state=self.decode(self.previous)
            if self._cached:
                self.readers['state'].last=deepcopy(self._cached[-1]['originals']['createAfter']);self.readers['work'].last=deepcopy(self._cached[-1]['originals']['work'])

    def guard(self):
        self.lock.assert_held();self.usage.guard();need(same(self.usage.store.read(),self.usage.previous));return True

    def local_guard(self):self.lock.assert_held();PrivateFeatureState(self.store.path)._parent();return True

    def envelope(self):
        self.state['rawSources']=self.raws.manifest()
        source=self.usage.source;return dict(iosAssetsModelSourcesVersion=VERSION,binding=source.binding,runId=source.files.run,role=source.role,fileOwnerToken=source.files.state['token'],page=source.state['page'],payload=pack([self.state]))

    def query(self,row):
        exact(row,{'kind','command'});query=row['command']
        if row['kind']=='clock':
            exact(query,{'schemaVersion','commandId','action'});need(type(query['schemaVersion']) is int and query['schemaVersion']==1 and query['action']=='feature-native-observe'
                and type(query['commandId']) is str and __import__('re').fullmatch('ios-[a-f0-9]{32}',query['commandId']) is not None)
        elif row['kind']=='state':create_state.command(query)
        else:need(row['kind']=='work');create_work.command(query)

    def prefix(self,reference):
        self.originals.original(reference);path=self.originals.path(reference)
        if reference['phase']=='planned':need(not os.path.lexists(path));return None
        fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC)
        try:
            self.originals.file(path,fd,reference);raw=b''
            while len(raw)<=reference['bytes']:
                part=os.read(fd,min(65536,reference['bytes']+1-len(raw)))
                if not part:break
                raw+=part
            self.originals.file(path,fd,reference);need(len(raw)<=reference['bytes'])
        finally:os.close(fd)
        value=dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),complete=len(raw)==reference['bytes'] and hashlib.sha256(raw).hexdigest()==reference['sha256'])
        need(reference['phase']!='saved' or value['complete']);record_original_read(path);return value

    def pending(self,value,index):
        exact(value,{'queries','rawRefs','original','snapshot'});need(type(value['queries']) is list and len(value['queries'])<=24 and type(value['rawRefs']) is list and len(value['rawRefs'])<=24)
        seen=set()
        for row in value['queries']:
            self.query(row);identifier=row['command']['commandId'];need(identifier not in seen);seen.add(identifier)
        indexes=[]
        for reference in value['rawRefs']:
            need(reference in self.raws.refs);record=self.raws.read_record(reference);need(record['kind']=='native' and any(same(record['query'],row['command']) for row in value['queries']));indexes.append(reference['index'])
        need(indexes==sorted(set(indexes)))
        if value['original'] is not None:
            self.originals.original(value['original']);need(value['original']['index']==index);current=self.prefix(value['original'])
            if value['snapshot'] is not None:need(same(current,value['snapshot']))
        else:need(value['snapshot'] is None)

    def decode(self,value):
        source=self.usage.source;exact(value,{'iosAssetsModelSourcesVersion','binding','runId','role','fileOwnerToken','page','payload'})
        need(type(value['iosAssetsModelSourcesVersion']) is int and value['iosAssetsModelSourcesVersion']==VERSION and same(value['binding'],source.binding)
            and value['runId']==source.files.run and value['role']==source.role and value['fileOwnerToken']==source.files.state['token'] and value['page']==source.state['page'])
        decoded=unpack(value['payload']);need(len(decoded)==1);state=decoded[0];exact(state,{'frames','pending','interrupted','nextIndex','rawSources'});self.raws.load(state['rawSources'])
        need(type(state['frames']) is list and len(state['frames'])<=32 and type(state['interrupted']) is list and len(state['interrupted'])<=8
            and integer(state['nextIndex'],1,41))
        frames=[];seen=set();previous=None;raw_seen=[]
        for reference in state['frames']:
            original=self.originals.expand(reference);need(original['index'] not in seen and original['index']<state['nextIndex']);seen.add(original['index'])
            frame=self.originals.read(original);self.frame(frame,previous);frames.append(frame);previous=frame;raw_seen.extend(frame['rawRefs'])
        for row in state['interrupted']:
            exact(row,{'index','pending'});need(integer(row['index'],1,state['nextIndex']-1) and row['index'] not in seen);seen.add(row['index']);self.pending(row['pending'],row['index']);raw_seen.extend(row['pending']['rawRefs'])
        need(seen==set(range(1,state['nextIndex'])))
        if state['pending'] is not None:self.pending(state['pending'],state['nextIndex']);raw_seen.extend(state['pending']['rawRefs'])
        need(len(raw_seen)==len(self.raws.refs) and sorted(raw_seen,key=lambda ref:ref['index'])==self.raws.refs)
        if self.raws.pending is not None:
            need(state['pending'] is not None and any(row['command']['commandId']==self.raws.pending['queryId'] for row in state['pending']['queries']))
        self._cached=frames;return state

    def save(self):
        self.guard();need(same(self.store.read(),self.previous));value=self.envelope();self.decode(value);self.store.write(value,self.previous);self.previous=deepcopy(value)

    def intent(self,kind,reference):
        need(kind=='original' and self.state['pending'] is not None and reference['index']==self.state['nextIndex']);self.state['pending']['original']=deepcopy(reference);self.save();return True

    @operation
    def reserve(self):
        need(self.state is None and self.usage.state is not None);self.state=dict(frames=[],pending=None,interrupted=[],nextIndex=1,rawSources=self.raws.manifest());self.save()

    def frame(self,frame,previous=None):
        exact(frame,{'assetModelSourceFrameVersion','queries','rawRefs','uiFrame','clockJoin','originals'})
        need(type(frame['assetModelSourceFrameVersion']) is int and frame['assetModelSourceFrameVersion']==VERSION and type(frame['queries']) is list and 1<=len(frame['queries'])<=24
            and type(frame['rawRefs']) is list and 1<=len(frame['rawRefs'])<=24 and integer(frame['uiFrame'],1,len(self.usage.source._cached)))
        self.pending(dict(queries=frame['queries'],rawRefs=frame['rawRefs'],original=None,snapshot=None),1)
        records=[self.raws.read_record(reference) for reference in frame['rawRefs']]
        originals=frame['originals'];exact(originals,{'ui','createBefore','work','createAfter'});need(same(originals['ui'],self.usage.source._cached[frame['uiFrame']-1]['ui']))
        validate_join(frame['clockJoin'],originals);source=self.usage.source;pid=source.clock.pid;packets={};clocks=[];external=[]
        for row in frame['queries']:
            self.query(row);query=row['command'];identifier=query['commandId'];need(identifier not in packets)
            matches=[record['raw'] for record in records if same(record['query'],query) and decode(record['raw'],limit=262144).get('requestId')==identifier]
            need(matches and all(raw==matches[0] for raw in matches));packet=decode(matches[0],limit=262144)
            if row['kind']=='clock':
                native_packet(packet,identifier,pid,packet['capturedEpochMs']);clocks.append(packet)
            else:
                module=create_state if row['kind']=='state' else create_work;module.validate(packet,query,pid);external.append(packet)
                need(query['runId']==source.files.run and clocks and clocks[-1]['capturedEpochMs']<=packet['clockBefore']['epochMs'])
            packets[identifier]=packet
        need(len(external)==3 and all(same(a,b) for a,b in zip(external,[originals['createBefore'],originals['work'],originals['createAfter']])))
        need(len(clocks)>=2 and same(clocks[0],frame['clockJoin']['nativeBefore']) and same(clocks[-1],frame['clockJoin']['nativeAfter'])
            and same(clocks[0]['lifecycle'],clocks[-1]['lifecycle']))
        for a,b in zip(clocks,clocks[1:]):follow_native(a,b)
        for packet in external:need(clocks[0]['capturedEpochMs']<=packet['clockBefore']['epochMs']<=packet['clockAfter']['epochMs']<=clocks[-1]['capturedEpochMs'])
        before,after=originals['createBefore'],originals['createAfter'];create_state.validate(after,dict(schemaVersion=1,action=create_state.ACTION,commandId=after['requestId'],runId=source.files.run),pid,previous=before)
        need(before['iosCreateStateVersion']>=3 and before['source']['complete'] and after['source']['complete'] and originals['work']['source']['complete']
            and originals['work']['source']['entityLifetimes']['complete'] and before['source']['domainId']==after['source']['domainId']
            and {row['id'] for row in before['source']['entities']}=={row['id'] for row in after['source']['entities']})
        if previous is not None:
            need(frame['clockJoin']['hostBeforeMonotonic']>=previous['clockJoin']['hostAfterMonotonic']);follow_native(previous['clockJoin']['nativeAfter'],clocks[0])
            create_state.validate(before,dict(schemaVersion=1,action=create_state.ACTION,commandId=before['requestId'],runId=source.files.run),pid,previous=previous['originals']['createAfter'])
            work=originals['work'];create_work.validate(work,dict(schemaVersion=1,action=create_work.ACTION,commandId=work['requestId'],runId=source.files.run),pid,previous=previous['originals']['work'])
        return frame

    @operation
    def capture(self,host_barrier):
        need(self.state is not None and self.state['pending'] is None and self.raws.pending is None and len(self.state['frames'])<32 and not self.active);self.guard()
        self.state['pending']=dict(queries=[],rawRefs=[],original=None,snapshot=None);self.save();wrappers=[];self.active=True
        for kind,reader in [('clock',self.native),*self.readers.items()]:
            old_send,old_original=reader.send,reader.original;wrappers.append((reader,old_send,old_original))
            def send(query,kind=kind,old_send=old_send):
                need(len(self.state['pending']['queries'])<24 and len(self.state['pending']['rawRefs'])<24)
                self.state['pending']['queries'].append(dict(kind=kind,command=deepcopy(query)));self.save();return old_send(query)
            def read(kind=kind,old_original=old_original):
                raw=old_original()
                if raw:
                    need(len(self.state['pending']['rawRefs'])<24);matches=[row for row in self.state['pending']['queries'] if row['kind']==kind];need(matches)
                    self.raws.capture(matches[-1]['command'],raw);self.raws.accept_capture();self.state['pending']['rawRefs'].append(deepcopy(self.raws.refs[-1]));self.save()
                return raw
            reader.send,reader.original=send,read
        try:
            clock=NativeClockAcquisition(self.native,epoch_ms=self.epoch_ms,monotonic=self.monotonic);clock.begin(host_barrier)
            before=self.readers['state'].read(self.usage.source.files.run);work=self.readers['work'].read(self.usage.source.files.run);after=self.readers['state'].read(self.usage.source.files.run)
            ui=self.usage.capture();originals=dict(ui=ui,createBefore=before,work=work,createAfter=after);join=clock.finish(originals,[('ui','sampleEpochMs')])
            frame=dict(assetModelSourceFrameVersion=VERSION,queries=deepcopy(self.state['pending']['queries']),rawRefs=deepcopy(self.state['pending']['rawRefs']),uiFrame=len(self.usage.source.state['frames']),clockJoin=join,originals=originals)
            self.frame(frame,self._cached[-1] if self._cached else None);reference=self.originals.write(self.state['nextIndex'],frame)
            self.state['frames'].append(reference);self.state['pending']=None;self.state['nextIndex']+=1;self.save();return deepcopy(frame)
        except BaseException as primary:
            if self.state['pending'] is not None and self.state['pending']['original'] is not None:
                try:self.state['pending']['snapshot']=self.prefix(self.state['pending']['original']);self.save()
                except BaseException as secondary:primary.add_note('Retaining the model-source prefix also failed: '+type(secondary).__name__)
            raise
        finally:
            self.active=False
            for reader,send,original in wrappers:reader.send,reader.original=send,original

    @operation
    def recover_capture(self):
        need(not self.active and self.state['pending'] is not None);pending=self.state['pending'];original=pending['original'];need(original is not None and original['phase']=='saved')
        frame=self.originals.read(original);need(same(frame['queries'],pending['queries']));self.frame(frame,self._cached[-1] if self._cached else None)
        self.state['frames'].append(self.originals.compact(original));self.state['pending']=None;self.state['nextIndex']+=1;self.save();return deepcopy(frame)

    @operation
    def freeze_interrupted(self):
        need(not self.active and self.state['pending'] is not None and len(self.state['interrupted'])<8);pending=self.state['pending']
        if self.raws.pending is not None:
            reference,record=self.raws.completed_capture();need(any(same(record['query'],row['command']) for row in pending['queries']))
            self.raws.accept_capture();pending['rawRefs'].append(reference);self.save()
        if pending['original'] is not None:
            need(pending['original']['phase']!='saved');current=self.prefix(pending['original'])
            if pending['snapshot'] is not None:need(same(current,pending['snapshot']))
            pending['snapshot']=current
        self.state['interrupted'].append(dict(index=self.state['nextIndex'],pending=deepcopy(pending)));self.state['nextIndex']+=1;self.state['pending']=None;self.save()
