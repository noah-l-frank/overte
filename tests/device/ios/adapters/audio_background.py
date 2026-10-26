"""One-send background cancellation of an actual owned recording cycle.

This child retains the parent untouched. Its returned originals are historical
interruption proofs, not a parent lifecycle bypass or a complete Audio result.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_feature_observation import exact,need
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.original_frame_store import OriginalFrameStore
from adapters.recorded_preview_history import measured_state
from adapters.script_feature.history import pack,unpack,same
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.contract import identifier
from ios.adapters.audio_api_clock import operation
from ios.adapters.audio_recorded_owner import IOSAudioRecordedOwner
from ios.adapters.audio_background_sources import validate as observation
from ios.adapters.graphics_history import follow_native
from ios.adapters.lifecycle_background import LifecycleOSContext,os_original
from ios.adapters.tablet_web_admission import installed_forward


class AudioBackground:
    def __init__(self,store,parent_store,os_context,run,lock,source_factory,*,epoch_ms,monotonic,sleep):
        need(isinstance(store,PrivateFeatureState) and isinstance(parent_store,PrivateFeatureState)
            and isinstance(os_context,LifecycleOSContext) and isinstance(lock,ScriptSourceLock))
        need(store.path.name=='ios-audio-background.json' and parent_store.path==store.path.with_name('ios-audio-recorded-owner.json')
            and lock.path==store.path.parent/'script-feature-sources.lock' and all(callable(f) for f in (source_factory,epoch_ms,monotonic,sleep)))
        self.store,self.parent_store,self.os,self.lock=store,parent_store,os_context,lock
        self.binding,self.run=deepcopy(context(os_context.binding)),identifier(run)
        self.source_factory,self.epoch_ms,self.monotonic,self.sleep=source_factory,epoch_ms,monotonic,sleep
        lock.assert_held();self.parent_original=parent_store.read();need(self.parent_original is not None)
        from pathlib import Path
        self.root=Path(self.parent_original['artifactRoot'])
        need(self.root.is_absolute() and self.root.resolve()==self.root)
        self.parent=IOSAudioRecordedOwner.archive(parent_store,self.root,self.binding,self.run,lock,self.parent_original['fixtureUrl'])
        need(self.parent.state['pending'] is None and self.parent.state['observation'] is None)
        self.previous=store.read();self.state=None
        self.historical=False
        self.frames=OriginalFrameStore(self.root,self.binding,run,'primary',self.file_guard,self.storage_intent,
            namespace='ios-audio-background',schema_prefix='iosAudioBackground',monotonic=monotonic)
        if self.previous is not None:self.state=self.decode(self.previous)

    @classmethod
    def archive(cls,store,prefix,bundle):
        """Pure child decoder against a checked prefix of the full parent."""
        from ios.adapters.audio_background_bridge import RecordedPrefix
        from types import SimpleNamespace
        need(isinstance(prefix,RecordedPrefix));owner=object.__new__(cls)
        owner.store,owner.parent,owner.parent_store=store,prefix,prefix.store
        owner.root,owner.binding,owner.run,owner.lock=prefix.root,deepcopy(prefix.binding),prefix.run,prefix.lock
        owner.parent_original=deepcopy(prefix.previous);owner.previous=store.read();need(owner.previous is not None)
        owner.monotonic=prefix.monotonic;owner.historical=True;owner.os=SimpleNamespace(gate=SimpleNamespace(bundle=deepcopy(bundle)))
        owner.frames=OriginalFrameStore(owner.root,owner.binding,owner.run,'primary',owner.file_guard,owner.storage_intent,
            namespace='ios-audio-background',schema_prefix='iosAudioBackground',monotonic=owner.monotonic)
        owner.state=owner.decode(owner.previous);return owner

    def envelope(self,state):
        return dict(iosAudioBackgroundVersion=1,binding=self.binding,runId=self.run,artifactRoot=str(self.root),payload=pack([state]))

    def file_guard(self):
        self.lock.assert_held();need(same(self.store.read(),self.previous))
        if self.historical:return self.parent.bound()
        need(same(self.parent_store.read(),self.parent_original))
        self.os.runtime.adapter._candidate_guard()
        need(same(self.os.runtime.adapter.read_session(self.os.selector),self.os.session_state));return True

    def save(self):
        need(not self.historical);self.file_guard();value=self.envelope(self.state);self.store.write(value,self.previous)
        need(same(self.store.read(),value));self.previous=deepcopy(value)

    def decode(self,value):
        exact(value,{'iosAudioBackgroundVersion','binding','runId','artifactRoot','payload'})
        need(type(value['iosAudioBackgroundVersion']) is int and value['iosAudioBackgroundVersion']==1)
        rows=unpack(value['payload']);need(len(rows)==1 and same(value,self.envelope(rows[0])));state=rows[0]
        exact(state,{'parent','ticket','startedBy','phase','records','queries','observation','osBefore','background','foreground'})
        need(same(state['parent'],self.parent_original) and state['phase'] in ('prepared','background-issued','background-observed','foreground-issued','observed')
            and identifier(state['ticket']) and type(state['records']) is list and len(state['records'])<=3)
        need(type(state['queries']) is list and len(state['queries'])<=192)
        for query in state['queries']:IOSAudioRecordedOwner.query(query)
        starts=[row for row in self.parent.state['operations'] if row['verb']=='record-start' and same(row['after'],state['startedBy'])]
        need(len(starts)==1 and same(state['startedBy'],self.parent.state['records'][-1]))
        previous=self.parent.original(state['startedBy']);self.starting(previous)
        for index,reference in enumerate(state['records'],1):
            need(reference['index']==index);current=self.read(reference,state['ticket']);self.follows(previous,current)
            if index==1:self.owned_before(state,current)
            else:self.completed(state,current)
            previous=current
        if state['observation'] is not None:
            pending=state['observation'];exact(pending,{'queries','wire'})
            need(type(pending['queries']) is list and len(pending['queries'])<=64)
            for query in pending['queries']:IOSAudioRecordedOwner.query(query)
            if pending['queries']:need(same(pending['queries'],state['queries'][-len(pending['queries']):]))
            if pending['wire'] is not None:
                self.frames.original(pending['wire']);need(pending['wire']['index']==len(state['records'])+1)
        if state['phase']!='prepared':need(len(state['records'])>=1 and state['osBefore'] is not None)
        old=state['osBefore']
        if old is not None:
            os_original(old,self.binding,self.os.gate.bundle);need(old['process']['foreground'] and state['records'])
            before=self.read(state['records'][0],state['ticket'])['clockJoin']
            need(old['hostBefore']['epochMs']>=before['hostAfterEpochMs'] and old['hostBefore']['monotonic']>=before['hostAfterMonotonic'])
            need(old['hostBefore']['epochMs']-before['hostAfterEpochMs']<1500
                and old['hostBefore']['monotonic']-before['hostAfterMonotonic']<1.5)
        for key,foreground in (('background',False),('foreground',True)):
            current=state[key]
            if current is None:continue
            need(old is not None);os_original(current,self.binding,self.os.gate.bundle)
            need(current['process']['foreground']==foreground and same(old['source'],current['source']))
            installed_forward(old['installed'],current['installed'])
            need(current['hostBefore']['epochMs']>=old['hostAfter']['epochMs'] and current['hostBefore']['monotonic']>=old['hostAfter']['monotonic'])
            old=current
        if state['phase'] in ('background-observed','foreground-issued','observed'):need(state['background'] is not None)
        if state['phase']=='observed':
            need(len(state['records'])==3 and state['observation'] is None and state['foreground'] is not None)
            first,last=[self.read(reference,state['ticket'])['clockJoin'] for reference in state['records'][1:]]
            need(last['hostBeforeMonotonic']-first['hostAfterMonotonic']>=.3
                and last['nativeBefore']['capturedEpochMs']-first['nativeAfter']['capturedEpochMs']>=300)
        expected={self.frames.path(self.frames.expand(reference)) for reference in state['records']}
        if state['observation'] is not None and state['observation']['wire'] is not None:expected.add(self.frames.path(state['observation']['wire']))
        expected.add(self.store.path)
        for index,path in enumerate(self.root.iterdir()):
            need(index<4096)
            if path.name.startswith('ios-audio-background'):need(path in expected)
        return deepcopy(state)

    def read(self,reference,ticket=None):
        value=self.frames.read(self.frames.expand(reference))
        return observation(value,self.binding,self.run,self.state['ticket'] if ticket is None else ticket)

    @staticmethod
    def follows(previous,current):
        a,b=previous['clockJoin'],current['clockJoin'];follow_native(a['nativeAfter'],b['nativeBefore'])
        x,y=previous['originals']['ui'],current['originals']['ui']
        need(x['instance']==y['instance'] and y['lastSequence']==x['lastSequence'] and y['elapsedMs']>=x['elapsedMs']
            and b['hostBeforeEpochMs']>=a['hostAfterEpochMs'] and b['hostBeforeMonotonic']>=a['hostAfterMonotonic'])

    @staticmethod
    def starting(value):
        native=value['originals']['native'];voice=native['audio']['recordedVoice'];actual=measured_state(native)
        need(voice['active'] and voice['cycle']>0 and not native['audio']['muted'] and not native['audio']['recording']
            and actual['phase']=='capturing' and actual['history']==['capturing'] and actual['error']=='none' and actual['bufferedFrames']>0)

    def owned_before(self,state,value):
        self.starting(value)
        old=self.parent.original(state['startedBy'])['originals']['native']['audio']['recordedVoice']
        current=value['originals']['native']['audio']['recordedVoice']
        need(old['cycle']==current['cycle'] and same(old['events'],current['events'][:len(old['events'])]))

    def completed(self,state,value):
        need(state['foreground'] is not None and state['records'])
        before=self.read(state['records'][0],state['ticket']);old,new=before['originals']['native'],value['originals']['native']
        self.follows(before,value);a,b=old['audio'],new['audio'];x,y=a['recordedVoice'],b['recordedVoice'];actual=measured_state(new)
        need(a['muted']==b['muted'] and not b['recording'] and x['cycle']==y['cycle'] and not y['active']
            and same(x['events'],y['events'][:len(x['events'])]) and len(y['events'])==len(x['events'])+1
            and actual['phase']=='cancelled' and actual['history']==['capturing','cancelled']
            and actual['error'] in ('backgrounded','lifecycle-stopped','input-or-lifecycle-changed')
            and y['capturedBytes']==y['playedBytes']==actual['bufferedFrames']==0
            and y['events'][-1]['publishedEpochMs']>=before['clockJoin']['nativeAfter']['capturedEpochMs'])
        first,last=before['clockJoin']['nativeAfter']['lifecycle'],value['clockJoin']['nativeBefore']['lifecycle']
        need(last['backgrounds']>=first['backgrounds']+1 and last['activations']>=first['activations']+1 and last['launches']==first['launches'])
        foreground=state['foreground']['hostAfter'];joined=value['clockJoin']
        need(joined['hostBeforeEpochMs']>=foreground['epochMs'] and joined['hostBeforeMonotonic']>=foreground['monotonic'])
        return actual

    def storage_intent(self,event,wire):
        self.file_guard();need(event=='original' and self.state['observation'] is not None)
        self.state['observation']['wire']=deepcopy(wire);self.save();return True

    def query_intent(self,command):
        self.file_guard();IOSAudioRecordedOwner.query(command);pending=self.state['observation']
        need(pending is not None and len(pending['queries'])<64 and len(self.state['queries'])<192)
        pending['queries'].append(deepcopy(command));self.state['queries'].append(deepcopy(command));self.save()

    def capture(self):
        self.file_guard();self.os.probe(True)
        if self.state['observation'] is None:
            self.state['observation']=dict(queries=[],wire=None);self.save()
            previous=self.parent.original(self.state['startedBy']) if not self.state['records'] else self.read(self.state['records'][-1])
            source=self.source_factory(self.query_intent,previous['clockJoin']['nativeAfter'])
            need(source.binding==self.binding and source.run==self.run)
            value=source.sample(self.state['ticket'])
            reference=self.frames.write(len(self.state['records'])+1,value)
        else:
            wire=self.state['observation']['wire'];need(wire is not None and wire['phase'] in ('opened','saved'))
            self.frames.read(wire);reference=self.frames.compact(dict(wire,phase='saved'))
        value=self.read(reference)
        previous=self.parent.original(self.state['startedBy']) if not self.state['records'] else self.read(self.state['records'][-1])
        self.follows(previous,value)
        if not self.state['records']:
            self.owned_before(self.state,value);need(same(previous['clockJoin']['nativeAfter']['lifecycle'],value['clockJoin']['nativeBefore']['lifecycle']))
        else:self.completed(self.state,value)
        self.state['records'].append(reference);self.state['observation']=None;self.save();return value

    def status(self):
        self.file_guard();value=self.os.status(self.epoch_ms,self.monotonic);self.file_guard();return value

    def wait(self,foreground):
        start=self.monotonic()
        for index in range(51):
            current=self.status()
            if current['process']['foreground']==foreground:return current
            if self.monotonic()-start>=5 or index==50:break
            self.sleep(.1)
        need(False)

    @operation
    def act(self,ticket):
        need(not self.historical);self.file_guard();identifier(ticket)
        if self.state is None:
            need(self.parent.state['operations']);started=self.parent.state['operations'][-1]
            need(started['verb']=='record-start' and started['after']==self.parent.state['records'][-1]);self.starting(self.parent.original(started['after']))
            self.state=dict(parent=deepcopy(self.parent_original),ticket=ticket,startedBy=deepcopy(started['after']),phase='prepared',
                records=[],queries=[],observation=None,osBefore=None,background=None,foreground=None);self.save()
        need(self.state['ticket']==ticket)
        if self.state['phase']=='prepared':
            if not self.state['records']:self.capture()
            self.state.update(osBefore=self.status(),phase='background-issued');self.decode(self.envelope(self.state));self.save()
            self.os.background();self.file_guard()
        if self.state['phase']=='background-issued':
            self.state.update(background=self.wait(False),phase='background-observed');self.decode(self.envelope(self.state));self.save()
        if self.state['phase']=='background-observed':
            need(not self.status()['process']['foreground']);self.state['phase']='foreground-issued';self.save()
            self.os.activate();self.file_guard()
        if self.state['phase']=='foreground-issued':
            foreground=self.wait(True)
            if self.state['foreground'] is None:self.state['foreground']=foreground;self.save()
            if len(self.state['records'])<2:self.capture()
            if len(self.state['records'])<3:self.sleep(.35);self.capture()
            self.state['phase']='observed';self.decode(self.envelope(self.state));self.save()
        self.decode(self.envelope(self.state));self.file_guard()
        return dict(originalBefore=deepcopy(self.state['records'][0]),originalAfter=deepcopy(self.state['records'][-1]),
            historical=True,parentBridgeRequired=True,silenceRequired=True,independentActorRequired=True,wholeFeatureRequired=True)
