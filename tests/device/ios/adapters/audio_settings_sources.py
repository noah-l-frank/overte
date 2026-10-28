"""Retained typed-settings cuts beside the original recording owner.

This collector issues readonly queries only. It does not grant permission,
deliver input or establish complete Settings/Audio restoration.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from types import SimpleNamespace
from adapters.native_clock_join import NativeClockAcquisition,validate_join
from adapters.native_clock_source_history import restore
from adapters.native_feature_observation import decode,exact,integer,need,validate as native_packet
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.original_frame_store import OriginalFrameStore
from adapters.script_feature.history import pack,unpack,same
from ios.adapters.audio_api_clock import operation
from ios.adapters.audio_recorded_owner import IOSAudioRecordedOwner
from ios.adapters.audio_settings_raw_sources import SettingsRawSources
from ios.adapters.assets_file_sources import FileSources
from ios.adapters.graphics_history import follow_native
from ios.adapters import audio_settings_source as settings_source


class AudioSettingsSources:
    def __init__(self,store,parent,source,*,epoch_ms,monotonic):
        need(isinstance(store,PrivateFeatureState) and isinstance(parent,IOSAudioRecordedOwner) and not parent.historical
            and store.path==parent.store.path.with_name('ios-audio-settings-source-owner.json') and source['binding']==parent.binding)
        parent.bound();self.store,self.parent=store,parent
        self.binding,self.run,self.root,self.lock=deepcopy(parent.binding),parent.run,parent.root,parent.lock
        self.source,self.native=source,source['clock_source'];self.epoch_ms,self.monotonic=epoch_ms,monotonic
        self.settings=source['observer'].audio_settings(clock_source=self.native)
        self.historical=False;self.active=False;self.previous=store.read();self.state=None
        self.raws=SettingsRawSources(self,'primary',self.bound,self.save)
        self.frames=OriginalFrameStore(self.root,self.binding,self.run,'primary',self.bound,self.intent,
            namespace='ios-audio-settings-source',schema_prefix='iosAudioSettingsSource',monotonic=monotonic)
        if self.previous is None:
            self.state=dict(frames=[],pending=None,interrupted=[],nextIndex=1,rawSources=self.raws.manifest());self.inventory(self.state)
        else:self.state=self.decode(self.previous)
        last=self.frame(self.state['frames'][-1]) if self.state['frames'] else None
        if last is not None:
            restore(self.native,last['clockJoin']['nativeAfter']);self.settings.last=deepcopy(last['originals']['settings'])
        elif parent.state['records']:restore(self.native,parent.original(parent.state['records'][-1])['clockJoin']['nativeAfter'])

    @classmethod
    def archive(cls,store,parent):
        need(isinstance(parent,IOSAudioRecordedOwner) and parent.historical);parent.bound();owner=object.__new__(cls)
        owner.store,owner.parent=store,parent
        owner.binding,owner.run,owner.root,owner.lock=deepcopy(parent.binding),parent.run,parent.root,parent.lock
        owner.monotonic=parent.monotonic;owner.native=SimpleNamespace(monotonic=parent.monotonic)
        owner.historical=True;owner.active=False;owner.previous=store.read();need(owner.previous is not None)
        owner.state=None;owner.raws=SettingsRawSources(owner,'primary',owner.bound,owner.save)
        owner.frames=OriginalFrameStore(owner.root,owner.binding,owner.run,'primary',owner.bound,owner.intent,
            namespace='ios-audio-settings-source',schema_prefix='iosAudioSettingsSource',monotonic=owner.monotonic)
        owner.state=owner.decode(owner.previous);return owner

    def bound(self):
        self.parent.bound();need(same(self.store.read(),self.previous))
        if not self.historical:need(self.source['check']() is not False)
        if self.active:need(same(self.parent.previous,self._active_parent) and same(self.parent.state,self._active_parent_state))
        return True

    def envelope(self):
        self.state['rawSources']=self.raws.manifest()
        return dict(iosAudioSettingsSourcesVersion=1,binding=self.binding,runId=self.run,artifactRoot=str(self.root),payload=pack([self.state]))

    def save(self):
        need(not self.historical);self.bound();value=self.envelope();self.decode(value)
        self.store.write(value,self.previous);need(same(self.store.read(),value));self.previous=deepcopy(value)

    @staticmethod
    def query(row):
        exact(row,{'kind','command'})
        if row['kind']=='clock':IOSAudioRecordedOwner.query(row['command']);need(row['command']['action']=='feature-native-observe')
        else:need(row['kind']=='settings');settings_source.command(row['command'])

    def pending(self,value,index,*,records=None):
        exact(value,{'stage','parent','queries','rawRefs','original','snapshot'})
        need(value['stage'] in ('baseline','before-input','after-input','verify')
            and (value['parent'] is None or value['parent'] in self.parent.state['records']))
        need(type(value['queries']) is list and len(value['queries'])<=24 and type(value['rawRefs']) is list and len(value['rawRefs'])<=24)
        if records is not None:need(type(records) is list and len(records)==len(value['rawRefs']))
        seen=set()
        for row in value['queries']:
            self.query(row);identifier=row['command']['commandId'];need(identifier not in seen);seen.add(identifier)
            if row['kind']=='settings':need(row['command']['runId']==self.run)
        indices=[]
        for offset,reference in enumerate(value['rawRefs']):
            need(reference in self.raws.refs);record=self.raws.read_record(reference) if records is None else records[offset]
            need(record['kind']=='native' and any(same(record['query'],row['command']) for row in value['queries']));indices.append(reference['index'])
        need(indices==sorted(set(indices)))
        if value['original'] is not None:
            self.frames.original(value['original']);need(value['original']['index']==index)
            current=FileSources.inspect(SimpleNamespace(store=self.frames),value['original'])
            if value['snapshot'] is not None:need(same(current,value['snapshot']))
        else:need(value['snapshot'] is None)

    def decode(self,value):
        exact(value,{'iosAudioSettingsSourcesVersion','binding','runId','artifactRoot','payload'})
        need(type(value['iosAudioSettingsSourcesVersion']) is int and value['iosAudioSettingsSourcesVersion']==1
            and same(value['binding'],self.binding) and value['runId']==self.run and value['artifactRoot']==str(self.root))
        rows=unpack(value['payload']);need(len(rows)==1);state=rows[0]
        exact(state,{'frames','pending','interrupted','nextIndex','rawSources'});self.raws.load(state['rawSources'])
        need(type(state['frames']) is list and len(state['frames'])<=32 and type(state['interrupted']) is list and len(state['interrupted'])<=8
            and integer(state['nextIndex'],1,41))
        seen=set();raws=[];previous=None
        for reference in state['frames']:
            need(reference['index'] not in seen and reference['index']<state['nextIndex']);seen.add(reference['index'])
            current=self.frame(reference,previous);previous=current;raws.extend(current['rawRefs'])
        for row in state['interrupted']:
            exact(row,{'index','pending'});need(integer(row['index'],1,state['nextIndex']-1) and row['index'] not in seen)
            seen.add(row['index']);self.pending(row['pending'],row['index']);raws.extend(row['pending']['rawRefs'])
        need(seen==set(range(1,state['nextIndex'])))
        if state['pending'] is not None:self.pending(state['pending'],state['nextIndex']);raws.extend(state['pending']['rawRefs'])
        need(sorted(raws,key=lambda ref:ref['index'])==self.raws.refs)
        if self.raws.pending is not None:
            need(state['pending'] is not None and any(row['command']['commandId']==self.raws.pending['queryId'] for row in state['pending']['queries']))
        self.inventory(state);return state

    def inventory(self,state):
        expected={self.store.path}|self.raws.owned_paths()|{self.frames.path(self.frames.expand(reference)) for reference in state['frames']}
        pending=[row['pending'] for row in state['interrupted']]+([] if state['pending'] is None else [state['pending']])
        for row in pending:
            if row['original'] is not None:expected.add(self.frames.path(row['original']))
        for directory in {self.root,self.store.path.parent}:
            for index,path in enumerate(directory.iterdir()):
                need(index<4096)
                if path.name.startswith('ios-audio-settings-source-'):need(path in expected)

    def frame(self,reference,previous=None):
        value=self.frames.read(self.frames.expand(reference))
        exact(value,{'iosAudioSettingsObservationVersion','stage','parent','queries','rawRefs','originals','clockJoin'})
        need(type(value['iosAudioSettingsObservationVersion']) is int and value['iosAudioSettingsObservationVersion']==1)
        need(type(value['rawRefs']) is list and len(value['rawRefs'])<=24)
        # Read and pin every original once in this validation call. Reopening
        # the entire list separately for each query added quadratic filesystem
        # work after a real native sample. No success survives this call, and
        # every query, raw body, inode/hash and parent guard is still checked.
        records=[self.raws.read_record(ref) for ref in value['rawRefs']]
        self.pending(dict(stage=value['stage'],parent=value['parent'],queries=value['queries'],rawRefs=value['rawRefs'],original=None,snapshot=None),1,records=records)
        raw=value['originals'];exact(raw,{'settings','settingsClock'});exact(raw['settingsClock'],{'capturedEpochMs'})
        need(raw['settingsClock']['capturedEpochMs']==raw['settings']['clockAfter']['epochMs'])
        join=validate_join(value['clockJoin'],raw);first,last=join['nativeBefore'],join['nativeAfter'];pid=int(self.binding['processIdentity'])
        need(first['processId']==pid and first['instance']==raw['settings']['instance'] and first['lifecycle']==last['lifecycle']==raw['settings']['lifecycle'])
        packets=[];external=[]
        for row in value['queries']:
            matches=[]
            for record in records:
                if not same(record['query'],row['command']):continue
                try:packet=decode(record['raw'],limit=262144)
                except (ValueError,NativeUIError):continue
                if type(packet) is dict and packet.get('requestId')==row['command']['commandId']:matches.append(packet)
            need(matches and all(same(packet,matches[0]) for packet in matches));packet=matches[0]
            if row['kind']=='clock':native_packet(packet,row['command']['commandId'],pid,packet['capturedEpochMs'],require_recorded_history=True);packets.append(packet)
            else:settings_source.validate(packet,row['command'],pid);external.append(packet)
        need(len(packets)>=2 and len(external)==1 and same(external[0],raw['settings']) and same(packets[0],first) and same(packets[-1],last))
        for a,b in zip(packets,packets[1:]):follow_native(a,b)
        need(first['capturedEpochMs']<=raw['settings']['clockBefore']['epochMs']<=raw['settings']['clockAfter']['epochMs']<=last['capturedEpochMs'])
        if value['parent'] is not None:
            parent=self.parent.original(value['parent']);follow_native(parent['clockJoin']['nativeAfter'],first)
            need(parent['clockJoin']['nativeAfter']['lifecycle']==first['lifecycle'])
        if previous is not None:
            follow_native(previous['clockJoin']['nativeAfter'],first)
            need(join['hostBeforeMonotonic']>=previous['clockJoin']['hostAfterMonotonic'] and join['hostBeforeEpochMs']>=previous['clockJoin']['hostAfterEpochMs'])
            settings_source.validate(raw['settings'],dict(schemaVersion=1,commandId=raw['settings']['requestId'],action=settings_source.ACTION,runId=self.run),pid,previous=previous['originals']['settings'])
        return value

    def intent(self,event,wire):
        need(event=='original' and self.state['pending'] is not None and wire['index']==self.state['nextIndex'])
        self.state['pending']['original']=deepcopy(wire);self.save();return True

    @operation
    def recover_capture(self):
        need(not self.historical and not self.active and self.state['pending'] is not None and self.raws.pending is None)
        self.bound();wire=self.state['pending']['original'];need(wire is not None and wire['phase'] in ('opened','saved'))
        self.frames.read(wire);reference=self.frames.compact(dict(wire,phase='saved'))
        self.frame(reference,self.frame(self.state['frames'][-1]) if self.state['frames'] else None)
        self.state['frames'].append(reference);self.state['pending']=None;self.state['nextIndex']+=1;self.save();return reference

    @operation
    def interrupt_capture(self):
        """Retain a failed readonly attempt; never reconstruct a successful cut."""
        need(not self.historical and not self.active and self.state['pending'] is not None and self.raws.pending is None
            and len(self.state['interrupted'])<8)
        self.bound();pending=self.state['pending']
        if pending['original'] is not None:
            pending['snapshot']=FileSources.inspect(SimpleNamespace(store=self.frames),pending['original'])
        self.state['interrupted'].append(dict(index=self.state['nextIndex'],pending=deepcopy(pending)))
        self.state['nextIndex']+=1;self.state['pending']=None;self.save()

    @operation
    def capture(self,stage):
        need(not self.historical and not self.active and self.state['pending'] is None and self.raws.pending is None and len(self.state['frames'])<32)
        self.bound();parent=self.parent.state['records'][-1] if self.parent.state['records'] else None
        self.state['pending']=dict(stage=stage,parent=deepcopy(parent),queries=[],rawRefs=[],original=None,snapshot=None);self.save()
        wrappers=[];self._active_parent=deepcopy(self.parent.previous);self._active_parent_state=deepcopy(self.parent.state);self.active=True
        for kind,reader in (('clock',self.native),('settings',self.settings)):
            send,original=reader.send,reader.original;wrappers.append((reader,send,original))
            def issued(command,kind=kind,send=send):
                need(len(self.state['pending']['queries'])<24);self.query(dict(kind=kind,command=command))
                self.state['pending']['queries'].append(dict(kind=kind,command=deepcopy(command)));self.save();return send(command)
            def body(kind=kind,original=original):
                raw=original()
                if raw:
                    need(len(self.state['pending']['rawRefs'])<24)
                    query=next(row['command'] for row in reversed(self.state['pending']['queries']) if row['kind']==kind)
                    self.raws.capture(query,raw);self.raws.accept_capture();self.state['pending']['rawRefs'].append(deepcopy(self.raws.refs[-1]));self.save()
                return raw
            reader.send,reader.original=issued,body
        try:
            clock=NativeClockAcquisition(self.native,epoch_ms=self.epoch_ms,monotonic=self.monotonic);clock.begin(self.epoch_ms())
            packet=self.settings.read(self.run);raw=dict(settings=packet,settingsClock=dict(capturedEpochMs=packet['clockAfter']['epochMs']))
            join=clock.finish(raw,[('settingsClock','capturedEpochMs')]);pending=self.state['pending']
            value=dict(iosAudioSettingsObservationVersion=1,stage=stage,parent=deepcopy(parent),queries=deepcopy(pending['queries']),
                rawRefs=deepcopy(pending['rawRefs']),originals=raw,clockJoin=join)
            reference=self.frames.write(self.state['nextIndex'],value);self.frame(reference,self.frame(self.state['frames'][-1]) if self.state['frames'] else None)
            self.state['frames'].append(reference);self.state['pending']=None;self.state['nextIndex']+=1;self.save();return reference
        except BaseException as primary:
            if self.state['pending'] is not None and self.state['pending']['original'] is not None:
                try:self.state['pending']['snapshot']=FileSources.inspect(SimpleNamespace(store=self.frames),self.state['pending']['original']);self.save()
                except BaseException as secondary:primary.add_note('Retaining settings prefix failed: '+type(secondary).__name__)
            raise
        finally:
            self.active=False
            for reader,send,original in wrappers:reader.send,reader.original=send,original
