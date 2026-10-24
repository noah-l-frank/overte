"""Retained normal recording start/cancel; no whole Audio capability.

Native recorded-voice history proves effects. UI tokens authorize inputs only.
An uncertain input stays owned and can only be resolved by new observations.
This owner never allocates a PCM snapshot or claims acoustic/tap-file cleanup.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
from adapters.native_clock_join import NativeClockAcquisition,digest,validate_join
from adapters.native_feature_observation import NativeFeatureObservation,exact,integer,need,validate
from adapters.native_clock_source_history import restore
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.original_frame_store import OriginalFrameStore
from adapters.recorded_preview_history import measured_state
from adapters.script_feature.history import pack,unpack,same
from adapters.script_feature.lock import ScriptSourceLock
from adapters.token_audio_ui import TokenAudioUI
from feature_journeys.contract import identifier
from feature_journeys.phase_fixture import PhaseFixtureReader,validate as phase_packet
from ios.adapters.graphics_history import follow_native
from ios.adapters.normal_input import observation as ui_packet
from ios.adapters.audio_api_clock import operation


class IOSAudioRecordedOwner:
    def __init__(self,store,root,binding,run,lock,guard,*,native,io,phase,epoch_ms,monotonic,sleep):
        need(isinstance(store,PrivateFeatureState) and isinstance(lock,ScriptSourceLock)
            and isinstance(native,NativeFeatureObservation) and native.ios and not native.native_clock_bound
            and isinstance(phase,PhaseFixtureReader) and phase.run==run and phase.area=='audio'
            and all(callable(fn) for fn in (guard,epoch_ms,monotonic,sleep)))
        self.store,self.root,self.binding,self.run,self.lock=store,Path(root),deepcopy(context(binding)),identifier(run),lock
        need(self.root.is_absolute() and self.root.resolve()==self.root and native.pid==int(self.binding['processIdentity']))
        self.guard,self.native,self.phase,self.epoch_ms,self.monotonic,self.sleep=guard,native,phase,epoch_ms,monotonic,sleep
        self.fixture_url=phase.fixture_url;self.historical=False;self.lock.assert_held()
        self.previous=store.read();self.state=dict(records=[],operations=[],pending=None,observation=None)
        self.frames=self.frame_store();self.ui=TokenAudioUI(io,self.input_intent,monotonic=monotonic,sleep=sleep)
        if self.previous is not None:self.state=self.decode(self.previous)
        else:self.inventory(self.state)
        if self.state['records']:restore(native,self.original(self.state['records'][-1])['clockJoin']['nativeAfter'])

    @classmethod
    def archive(cls,store,root,binding,run,lock,fixture_url):
        """Pure original decoder; never constructs an SDK or a native reader."""
        owner=object.__new__(cls)
        owner.store,owner.root,owner.binding,owner.run,owner.lock=store,Path(root),deepcopy(context(binding)),identifier(run),lock
        lock.assert_held()
        owner.fixture_url=fixture_url;owner.historical=True;owner.guard=lambda:True
        import time
        owner.monotonic=time.monotonic;owner.previous=store.read();need(owner.previous is not None)
        owner.frames=owner.frame_store();owner.state=owner.decode(owner.previous);return owner

    def frame_store(self):
        return OriginalFrameStore(self.root,self.binding,self.run,'primary',self.bound,self.storage_intent,
            namespace='ios-audio-recorded',schema_prefix='iosAudioRecorded',monotonic=self.monotonic)

    def envelope(self,state):
        return dict(iosAudioRecordedOwnerVersion=1,runId=self.run,binding=self.binding,artifactRoot=str(self.root),fixtureUrl=self.fixture_url,payload=pack([state]))

    def bound(self):
        self.lock.assert_held();need(same(self.store.read(),self.previous) and self.guard() is not False);return True

    def save(self):
        need(not self.historical);self.bound();value=self.envelope(self.state);self.store.write(value,self.previous)
        need(same(self.store.read(),value));self.previous=deepcopy(value)

    def phase_original(self,value,ticket,verb,previous=None):
        phase_packet(value,run=self.run,area='audio',request=value['requestId'],epoch=value['capturedEpochMs'],previous=previous)
        need(value['active'] and value['activations'] and value['activations'][-1]['ticket']==ticket
            and value['activations'][-1]['stimulus']==dict(verb=verb,inputs={}))

    def frame(self,value,previous=None):
        exact(value,{'iosAudioRecordedObservationVersion','ticket','verb','phaseBefore','phaseAfter','originals','clockJoin'})
        need(type(value['iosAudioRecordedObservationVersion']) is int and value['iosAudioRecordedObservationVersion']==1)
        identifier(value['ticket']);need(value['verb'] in ('record-start','record-cancel'))
        self.phase_original(value['phaseBefore'],value['ticket'],value['verb'])
        self.phase_original(value['phaseAfter'],value['ticket'],value['verb'],value['phaseBefore'])
        need(same(value['phaseBefore']['activations'],value['phaseAfter']['activations']))
        exact(value['originals'],{'native','ui'});join=validate_join(value['clockJoin'],value['originals'])
        first,current,last=join['nativeBefore'],value['originals']['native'],join['nativeAfter']
        validate(current,current['requestId'],int(self.binding['processIdentity']),last['capturedEpochMs'],require_recorded_history=True)
        follow_native(first,current);follow_native(current,last)
        need(first['processId']==last['processId']==int(self.binding['processIdentity']) and first['lifecycle']==last['lifecycle'])
        ui=ui_packet(value['originals']['ui'],int(self.binding['processIdentity']),last['capturedEpochMs'])
        class Frozen:
            def capture(self):return deepcopy(ui)
        controls=TokenAudioUI(Frozen(),lambda *_args:need(False)).capture()
        page=TokenAudioUI.row(controls,'audio.page');need(page is not None)
        voice=current['audio']['recordedVoice'];need(page['cycle']==voice['cycle'])
        row=TokenAudioUI.row(controls,'audio.record')
        if row is not None:need(row['cycle']==voice['cycle'] and row['phase']==(voice['event']['phase'] if voice['events'] else 'idle')
            and row['nativeActive']==row['uiActive']==voice['active'])
        if previous is not None:
            follow_native(previous['clockJoin']['nativeAfter'],first)
            need(first['lifecycle']==previous['clockJoin']['nativeAfter']['lifecycle']
                and ui['instance']==previous['originals']['ui']['instance']
                and ui['lastSequence']>=previous['originals']['ui']['lastSequence']
                and ui['elapsedMs']>=previous['originals']['ui']['elapsedMs']
                and join['hostBeforeEpochMs']>=previous['clockJoin']['hostAfterEpochMs']
                and join['hostBeforeMonotonic']>=previous['clockJoin']['hostAfterMonotonic'])
            self.phase_original(value['phaseBefore'],value['ticket'],value['verb'],previous['phaseAfter'])
        return value

    def original(self,reference):return self.frame(self.frames.read(self.frames.expand(reference)))

    def inventory(self,state):
        expected={self.frames.path(self.frames.expand(reference)) for reference in state['records']}
        expected.add(self.store.path)
        if state['observation'] is not None and state['observation']['wire'] is not None:
            expected.add(self.frames.path(state['observation']['wire']))
        for index,path in enumerate(self.root.iterdir()):
            need(index<4096)
            if path.name.startswith('ios-audio-recorded-'):need(path in expected)

    def decode(self,value):
        exact(value,{'iosAudioRecordedOwnerVersion','runId','binding','artifactRoot','fixtureUrl','payload'});rows=unpack(value['payload'])
        need(type(value['iosAudioRecordedOwnerVersion']) is int and value['iosAudioRecordedOwnerVersion']==1 and len(rows)==1
            and same(value,self.envelope(rows[0])));state=rows[0]
        exact(state,{'records','operations','pending','observation'})
        need(type(state['records']) is list and len(state['records'])<=128 and type(state['operations']) is list and len(state['operations'])<=32)
        previous=None
        for index,reference in enumerate(state['records'],1):
            need(reference['index']==index);current=self.original(reference);self.frame(current,previous);previous=current
        tickets=set()
        for operation in state['operations']+([] if state['pending'] is None else [state['pending']]):
            exact(operation,{'ticket','verb','cycle','before','inputs','queries','after','quiet'})
            identifier(operation['ticket']);need(operation['ticket'] not in tickets);tickets.add(operation['ticket'])
            need(operation['verb'] in ('record-start','record-cancel') and integer(operation['cycle'])
                and operation['before'] in state['records'] and type(operation['inputs']) is list and len(operation['inputs'])<=16
                and type(operation['queries']) is list and len(operation['queries'])<=256
                and type(operation['quiet']) is list and len(operation['quiet'])<=2)
            before=self.original(operation['before']);need(before['ticket']==operation['ticket'] and before['verb']==operation['verb']
                and before['originals']['native']['audio']['recordedVoice']['cycle']==operation['cycle'])
            for item in operation['inputs']:
                exact(item,{'verb','identifier','ui','phase'});need(item['verb'] in ('record-start','record-cancel','select-current-mode','scroll-up','scroll-down'))
                ui_packet(item['ui'],int(self.binding['processIdentity']),item['ui']['sampleEpochMs'])
                self.phase_original(item['phase'],operation['ticket'],operation['verb'])
            for query in operation['queries']:self.query(query)
            if operation['after'] is not None:
                need(operation in state['operations'] and operation['after'] in state['records']);self.effect(operation,self.original(operation['after']))
                self.quiet(operation,state['records'])
            else:need(operation is state['pending'])
        observation=state['observation']
        if observation is not None:
            exact(observation,{'ticket','verb','queries','wire'});identifier(observation['ticket'])
            need(observation['verb'] in ('record-start','record-cancel') and type(observation['queries']) is list and len(observation['queries'])<=64)
            for query in observation['queries']:self.query(query)
            if observation['wire'] is not None:self.frames.original(observation['wire'])
        self.inventory(state)
        return deepcopy(state)

    @staticmethod
    def query(command):
        need(type(command) is dict and command.get('action') in ('feature-native-observe','normal-ui-input'))
        exact(command,{'schemaVersion','commandId','action'}|({'operation'} if command['action']=='normal-ui-input' else set()))
        need(type(command['schemaVersion']) is int and command['schemaVersion']==1 and type(command['commandId']) is str
            and command['commandId'].startswith('ios-'));identifier(command['commandId'][4:])
        if command['action']=='normal-ui-input':need(command['operation']=='observe')

    def query_intent(self,command):
        """Persist actual query IDs before native/UI observation delivery."""
        self.bound();need(not self.historical);self.query(command)
        holder=self.state['observation'] or self.state['pending'];need(holder is not None)
        need(len(holder['queries'])<(64 if self.state['observation'] is not None else 256))
        holder['queries'].append(deepcopy(command));self.save()

    def input_intent(self,verb,value,identifier):
        self.bound();operation=self.state['pending'];need(operation is not None and len(operation['inputs'])<16)
        need(verb in ('select-current-mode','scroll-up','scroll-down',operation['verb']))
        if verb in ('record-start','record-cancel'):need(not any(item['verb'] in ('record-start','record-cancel') for item in operation['inputs']))
        status=self.phase.read();need(status['ticket']==operation['ticket'] and status['verb']==operation['verb'] and status['inputs']=={})
        operation['inputs'].append(dict(verb=verb,identifier=identifier,ui=deepcopy(value),phase=status['status']));self.save()

    def storage_intent(self,event,wire):
        self.bound();need(event=='original' and self.state['observation'] is not None)
        self.state['observation']['wire']=deepcopy(wire);self.save();return True

    def recover_observation(self):
        pending=self.state['observation']
        if pending is None:return
        wire=pending['wire'];need(wire is not None and wire['phase'] in ('opened','saved'))
        value=self.frame(self.frames.read(wire),None if not self.state['records'] else self.original(self.state['records'][-1]))
        need(value['ticket']==pending['ticket'] and value['verb']==pending['verb'] and wire['index']==len(self.state['records'])+1)
        reference=self.frames.compact(dict(wire,phase='saved'));self.state['records'].append(reference);self.state['observation']=None;self.save()

    @operation
    def capture(self,ticket,verb):
        self.bound();need(not self.historical and len(self.state['records'])<128 and self.state['observation'] is None)
        status=self.phase.read();need(status['ticket']==ticket and status['verb']==verb and status['inputs']=={})
        self.state['observation']=dict(ticket=ticket,verb=verb,queries=[],wire=None);self.save()
        acquisition=NativeClockAcquisition(self.native,epoch_ms=self.epoch_ms,monotonic=self.monotonic)
        acquisition.begin(self.epoch_ms());native=self.native.read(self.native.sequence,require_recorded_history=True);ui=self.ui.capture()
        originals=dict(native=native,ui=ui)
        join=acquisition.finish(originals,[('native','capturedEpochMs'),('ui','sampleEpochMs')])
        after=self.phase.status(status['status'])
        value=dict(iosAudioRecordedObservationVersion=1,ticket=ticket,verb=verb,phaseBefore=status['status'],phaseAfter=after,originals=originals,clockJoin=join)
        self.frame(value,None if not self.state['records'] else self.original(self.state['records'][-1]))
        reference=self.frames.write(len(self.state['records'])+1,value);self.state['records'].append(reference);self.state['observation']=None;self.save()
        return reference

    def effect(self,operation,observation):
        need(observation['ticket']==operation['ticket'] and observation['verb']==operation['verb'])
        voice=observation['originals']['native']['audio']['recordedVoice'];actual=measured_state(observation['originals']['native'])
        inputs=[item for item in operation['inputs'] if item['verb']==operation['verb']]
        need(len(inputs)==1 and inputs[0]['identifier']=='audio.record')
        rows=[row for row in inputs[0]['ui']['controls'] if row['id']=='audio.record']
        need(len(rows)==1 and rows[0]['cycle']==operation['cycle'] and rows[0]['inputReady'] and rows[0]['enabled'])
        need(observation['originals']['native']['capturedEpochMs']>=inputs[0]['ui']['sampleEpochMs'])
        if operation['verb']=='record-start':
            need(voice['cycle']==operation['cycle']+1 and voice['events'] and voice['events'][0]['phase']=='capturing'
                and voice['events'][0]['publishedEpochMs']>=inputs[0]['ui']['sampleEpochMs'] and actual['recordedFrames']>0)
        else:
            need(voice['cycle']==operation['cycle'] and actual['phase']=='cancelled' and not voice['active']
                and voice['capturedBytes']==voice['playedBytes']==actual['bufferedFrames']==0
                and voice['events'][-1]['publishedEpochMs']>=inputs[0]['ui']['sampleEpochMs'])
        return actual

    def quiet(self,operation,records):
        if operation['verb']=='record-start':need(operation['quiet']==[]);return
        need(len(operation['quiet'])==2 and all(reference in records for reference in operation['quiet'])
            and operation['quiet'][-1]==operation['after'] and operation['quiet'][0]['index']<operation['quiet'][1]['index'])
        first,last=[self.original(reference) for reference in operation['quiet']]
        self.effect(operation,first);self.effect(operation,last)
        need(last['clockJoin']['hostBeforeMonotonic']-first['clockJoin']['hostAfterMonotonic']>=.3
            and last['clockJoin']['nativeBefore']['capturedEpochMs']-first['clockJoin']['nativeAfter']['capturedEpochMs']>=300)

    @operation
    def resolve(self):
        self.bound();need(not self.historical);self.recover_observation();operation=self.state['pending'];need(operation is not None)
        reference=self.capture(operation['ticket'],operation['verb']);first=self.original(reference);self.effect(operation,first)
        quiet=[]
        if operation['verb']=='record-cancel':
            quiet=[deepcopy(reference)]
            # Ask for a real margin; qualification still checks original >=300ms
            # intervals on both clocks, without rounding or retiming samples.
            self.sleep(.35);reference=self.capture(operation['ticket'],operation['verb']);last=self.original(reference);self.effect(operation,last)
            quiet.append(deepcopy(reference))
        actual=self.effect(operation,self.original(reference));completed=dict(deepcopy(operation),after=deepcopy(reference),quiet=quiet)
        self.quiet(completed,self.state['records'])
        self.state['operations'].append(completed);self.state['pending']=None;self.save()
        return dict(performed=True,original=deepcopy(reference),state=actual)

    @operation
    def act(self,ticket,verb):
        self.bound();need(not self.historical);identifier(ticket);need(verb in ('record-start','record-cancel'))
        self.recover_observation()
        if self.state['pending'] is not None:
            need(self.state['pending']['ticket']==ticket and self.state['pending']['verb']==verb);return self.resolve()
        retained=next((item for item in self.state['operations'] if item['ticket']==ticket),None)
        if retained is not None:
            need(retained['verb']==verb);reference=self.capture(ticket,verb);actual=self.effect(retained,self.original(reference))
            return dict(performed=True,original=reference,state=actual)
        need(len(self.state['operations'])<32);reference=self.capture(ticket,verb);before=self.original(reference)
        voice=before['originals']['native']['audio']['recordedVoice']
        need(not before['originals']['native']['audio']['muted'])
        if verb=='record-start':need(not voice['active'])
        else:need(voice['active'] and voice['cycle']>0)
        self.state['pending']=dict(ticket=ticket,verb=verb,cycle=voice['cycle'],before=reference,inputs=[],queries=[],after=None,quiet=[]);self.save()
        if verb=='record-start':self.ui.start()
        else:self.ui.cancel(voice['cycle'])
        return self.resolve()
