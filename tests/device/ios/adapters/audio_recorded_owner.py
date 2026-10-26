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

VERSION=4
READS=(1,2,3,4)

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
        self.version=VERSION if self.previous is None else self.previous.get('iosAudioRecordedOwnerVersion')
        if self.version>=4:self.state['background']=None
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
        owner.version=owner.previous.get('iosAudioRecordedOwnerVersion')
        owner.frames=owner.frame_store();owner.state=owner.decode(owner.previous);return owner

    def frame_store(self):
        return OriginalFrameStore(self.root,self.binding,self.run,'primary',self.bound,self.storage_intent,
            namespace='ios-audio-recorded',schema_prefix='iosAudioRecorded',monotonic=self.monotonic)

    def envelope(self,state):
        return dict(iosAudioRecordedOwnerVersion=self.version,runId=self.run,binding=self.binding,artifactRoot=str(self.root),fixtureUrl=self.fixture_url,payload=pack([state]))

    def bound(self):
        self.lock.assert_held();need(same(self.store.read(),self.previous) and self.guard() is not False);return True

    def save(self):
        need(not self.historical);self.bound();value=self.envelope(self.state);self.store.write(value,self.previous)
        need(same(self.store.read(),value));self.previous=deepcopy(value)

    def phase_original(self,value,ticket,verb,previous=None):
        phase_packet(value,run=self.run,area='audio',request=value['requestId'],epoch=value['capturedEpochMs'],previous=previous)
        need(value['active'] and value['activations'] and value['activations'][-1]['ticket']==ticket
            and value['activations'][-1]['stimulus']['verb']==verb)
        inputs=value['activations'][-1]['stimulus']['inputs']
        if verb=='mute':
            need(self.version>=2);exact(inputs,{'enabled'});need(type(inputs['enabled']) is bool)
        else:need(inputs=={})
        return inputs

    def frame(self,value,previous=None,state=None):
        exact(value,{'iosAudioRecordedObservationVersion','ticket','verb','phaseBefore','phaseAfter','originals','clockJoin'}
            |({'background'} if value.get('iosAudioRecordedObservationVersion',0)>=4 else set()))
        need(type(value['iosAudioRecordedObservationVersion']) is int and value['iosAudioRecordedObservationVersion'] in READS
            and value['iosAudioRecordedObservationVersion']<=self.version)
        identifier(value['ticket']);need(value['verb'] in ('record-start','record-cancel')
            or value['iosAudioRecordedObservationVersion']>=2 and value['verb'] in ('mute','await-completion')
            or value['iosAudioRecordedObservationVersion']>=3 and value['verb'] in ('open','close')
            or value['iosAudioRecordedObservationVersion']>=4 and value['verb']=='background-resume')
        bridge=value.get('background')
        if bridge is not None:
            from ios.adapters.audio_background_bridge import proof
            current=self.state if state is None else state
            need(value['verb']=='background-resume' and current['background'] is not None
                and same(current['background']['proof'],bridge))
            final=proof(self,bridge,current)
            need(final['ticket']==value['ticket']);follow_native(final['clockJoin']['nativeAfter'],value['clockJoin']['nativeBefore'])
            need(same(final['clockJoin']['nativeAfter']['lifecycle'],value['clockJoin']['nativeBefore']['lifecycle'])
                and same(final['originals']['native']['audio'],value['originals']['native']['audio'])
                and final['originals']['ui']['lastSequence']==value['originals']['ui']['lastSequence']
                and value['clockJoin']['hostBeforeEpochMs']>=final['clockJoin']['hostAfterEpochMs']
                and value['clockJoin']['hostBeforeMonotonic']>=final['clockJoin']['hostAfterMonotonic'])
        elif value['verb']=='background-resume':need(False)
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
        page=TokenAudioUI.row(controls,'audio.page')
        need(page is not None or value['iosAudioRecordedObservationVersion']>=3 and value['verb'] in ('open','close'))
        voice=current['audio']['recordedVoice']
        if page is not None:need(page['cycle']==voice['cycle'])
        row=TokenAudioUI.row(controls,'audio.record')
        if row is not None:need(row['cycle']==voice['cycle'] and row['phase']==(voice['event']['phase'] if voice['events'] else 'idle')
            and row['nativeActive']==row['uiActive']==voice['active'])
        mute=TokenAudioUI.row(controls,'audio.mute')
        if mute is not None and value['iosAudioRecordedObservationVersion']>=2:
            need(mute['nativeMuted']==current['audio']['muted'])
        if previous is not None:
            follow_native(previous['clockJoin']['nativeAfter'],first)
            if bridge is None:need(first['lifecycle']==previous['clockJoin']['nativeAfter']['lifecycle'])
            else:need(same(previous,self.original(bridge['before'],state=state)))
            need(ui['instance']==previous['originals']['ui']['instance']
                and ui['lastSequence']>=previous['originals']['ui']['lastSequence']
                and ui['elapsedMs']>=previous['originals']['ui']['elapsedMs']
                and join['hostBeforeEpochMs']>=previous['clockJoin']['hostAfterEpochMs']
                and join['hostBeforeMonotonic']>=previous['clockJoin']['hostAfterMonotonic'])
            self.phase_original(value['phaseBefore'],value['ticket'],value['verb'],previous['phaseAfter'])
        return value

    def original(self,reference,*,state=None):return self.frame(self.frames.read(self.frames.expand(reference)),state=state)

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
        need(type(value['iosAudioRecordedOwnerVersion']) is int and value['iosAudioRecordedOwnerVersion'] in READS
            and value['iosAudioRecordedOwnerVersion']==self.version and len(rows)==1
            and same(value,self.envelope(rows[0])));state=rows[0]
        exact(state,{'records','operations','pending','observation'}|({'background'} if self.version>=4 else set()))
        need(type(state['records']) is list and len(state['records'])<=128 and type(state['operations']) is list and len(state['operations'])<=32)
        previous=None
        for index,reference in enumerate(state['records'],1):
            need(reference['index']==index);current=self.original(reference,state=state);self.frame(current,previous,state);previous=current
        self.operations(state)
        if self.version>=4 and state['background'] is not None:
            from ios.adapters.audio_background_bridge import proof
            background=state['background'];exact(background,{'proof','after'});proof(self,background['proof'],state)
            if background['after'] is not None:
                need(background['after'] in state['records'] and background['after']['index']==background['proof']['before']['index']+1)
                result=self.original(background['after'],state=state)
                need(result['verb']=='background-resume' and same(result['background'],background['proof']))
            else:need(len(state['records'])<=background['proof']['before']['index']+1)
        self.inventory(state)
        return deepcopy(state)

    def operations(self,state):
        """Pure operation grammar shared with an exact validated record prefix."""
        tickets=set();completed=[]
        for operation in state['operations']+([] if state['pending'] is None else [state['pending']]):
            keys={'ticket','verb','cycle','before','inputs','queries','after','quiet'}
            if operation.get('verb')=='await-completion':
                need(self.version>=2);keys.add('startedBy')
                need(any(row['verb']=='record-start' and same(row['after'],operation.get('startedBy')) for row in completed))
            if operation.get('verb') in ('open','close'):
                need(self.version>=3);keys.add('launcher')
                if operation['verb']=='close':
                    keys|={'openedBy','openedBefore'}
                    need(any(row['verb']=='open' and same(row['after'],operation.get('openedBy'))
                        and same(row['before'],operation.get('openedBefore')) and same(row['launcher'],operation.get('launcher')) for row in completed))
            exact(operation,keys)
            identifier(operation['ticket']);need(operation['ticket'] not in tickets);tickets.add(operation['ticket'])
            need((operation['verb'] in ('record-start','record-cancel') or self.version>=2 and operation['verb'] in ('mute','await-completion')
                    or self.version>=3 and operation['verb'] in ('open','close')) and integer(operation['cycle'])
                and operation['before'] in state['records'] and type(operation['inputs']) is list and len(operation['inputs'])<=(72 if operation['verb'] in ('open','close') else 16)
                and type(operation['queries']) is list and len(operation['queries'])<=(1024 if operation['verb'] in ('open','close') else 256)
                and type(operation['quiet']) is list and len(operation['quiet'])<=2)
            before=self.original(operation['before']);need(before['ticket']==operation['ticket'] and before['verb']==operation['verb']
                and before['originals']['native']['audio']['recordedVoice']['cycle']==operation['cycle'])
            page_labels=set()
            for item in operation['inputs']:
                fields={'verb','identifier','ui','phase'}
                if item.get('verb')=='page':
                    from ios.adapters.audio_page_inputs import action as page_action
                    need(self.version>=3 and operation['verb'] in ('open','close'));fields|={'label','element','returned'}
                    page_action(item['label'],item['identifier'],item['element'])
                    need(type(item['returned']) is bool and item['label'] not in page_labels);page_labels.add(item['label'])
                exact(item,fields);need(item['verb'] in ('record-start','record-cancel','select-current-mode','scroll-up','scroll-down')
                    or self.version>=2 and item['verb']=='mute' or self.version>=3 and item['verb']=='page')
                ui_packet(item['ui'],int(self.binding['processIdentity']),item['ui']['sampleEpochMs'])
                self.phase_original(item['phase'],operation['ticket'],operation['verb'])
            for query in operation['queries']:self.query(query)
            if operation['after'] is not None:
                need(operation in state['operations'] and operation['after'] in state['records']);self.effect(operation,self.original(operation['after']))
                self.quiet(operation,state['records'])
                completed.append(operation)
            else:need(operation is state['pending'])
        observation=state['observation']
        if observation is not None:
            exact(observation,{'ticket','verb','queries','wire'});identifier(observation['ticket'])
            need((observation['verb'] in ('record-start','record-cancel') or self.version>=2 and observation['verb'] in ('mute','await-completion')
                    or self.version>=3 and observation['verb'] in ('open','close')
                    or self.version>=4 and observation['verb']=='background-resume')
                and type(observation['queries']) is list and len(observation['queries'])<=64)
            for query in observation['queries']:self.query(query)
            if observation['wire'] is not None:self.frames.original(observation['wire'])

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
        need(len(holder['queries'])<(64 if self.state['observation'] is not None else 1024 if holder['verb'] in ('open','close') else 256))
        holder['queries'].append(deepcopy(command));self.save()

    def input_intent(self,verb,value,identifier):
        self.bound();operation=self.state['pending'];need(operation is not None and len(operation['inputs'])<(72 if operation['verb'] in ('open','close') else 16))
        need(verb in ('select-current-mode','scroll-up','scroll-down',operation['verb'])
            or self.version>=3 and operation['verb'] in ('open','close') and verb=='mute')
        if verb in ('record-start','record-cancel','mute'):need(not any(item['verb'] in ('record-start','record-cancel','mute') for item in operation['inputs']))
        status=self.phase.read();need(status['ticket']==operation['ticket'] and status['verb']==operation['verb'])
        need(same(status['inputs'],self.phase_original(self.original(operation['before'])['phaseBefore'],operation['ticket'],operation['verb'])))
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
        status=self.phase.read();self.phase_original(status['status'],ticket,verb)
        self.state['observation']=dict(ticket=ticket,verb=verb,queries=[],wire=None);self.save()
        acquisition=NativeClockAcquisition(self.native,epoch_ms=self.epoch_ms,monotonic=self.monotonic)
        acquisition.begin(self.epoch_ms());native=self.native.read(self.native.sequence,require_recorded_history=True);ui=self.ui.capture()
        originals=dict(native=native,ui=ui)
        join=acquisition.finish(originals,[('native','capturedEpochMs'),('ui','sampleEpochMs')])
        after=self.phase.status(status['status'])
        value=dict(iosAudioRecordedObservationVersion=self.version,ticket=ticket,verb=verb,phaseBefore=status['status'],phaseAfter=after,originals=originals,clockJoin=join)
        if self.version>=4:value['background']=deepcopy(self.state['background']['proof']) if verb=='background-resume' else None
        self.frame(value,None if not self.state['records'] else self.original(self.state['records'][-1]))
        reference=self.frames.write(len(self.state['records'])+1,value);self.state['records'].append(reference);self.state['observation']=None;self.save()
        return reference

    def effect(self,operation,observation):
        need(observation['ticket']==operation['ticket'] and observation['verb']==operation['verb'])
        voice=observation['originals']['native']['audio']['recordedVoice'];actual=measured_state(observation['originals']['native'])
        inputs=[item for item in operation['inputs'] if item['verb']==operation['verb']]
        if operation['verb'] in ('open','close'):return self.page_effect(operation,observation)
        if operation['verb']=='mute':return self.mute_effect(operation,observation,inputs)
        if operation['verb']=='await-completion':return self.completion_effect(operation,observation)
        need(len(inputs)==1 and inputs[0]['identifier']=='audio.record')
        rows=[row for row in inputs[0]['ui']['controls'] if row['id']=='audio.record']
        need(len(rows)==1 and rows[0]['cycle']==operation['cycle'] and rows[0]['inputReady'] and rows[0]['enabled'])
        need(observation['originals']['native']['capturedEpochMs']>=inputs[0]['ui']['sampleEpochMs'])
        if operation['verb']=='record-start':
            need(voice['cycle']==operation['cycle']+1 and voice['events']
                and voice['events'][0]['publishedEpochMs']>=inputs[0]['ui']['sampleEpochMs'])
            before=self.original(operation['before'])['originals']['native']['audio']
            if before['muted']:
                need(self.version>=2 and observation['originals']['native']['audio']['muted'] and not voice['active']
                    and actual['phase']=='error' and actual['history']==['error'] and actual['error']=='microphone-muted'
                    and len(voice['events'])==1 and voice['capturedBytes']==voice['playedBytes']==0
                    and actual['recordedFrames']==actual['playedFrames']==actual['bufferedFrames']==0)
            else:need(voice['events'][0]['phase']=='capturing' and actual['recordedFrames']>0)
        else:
            need(voice['cycle']==operation['cycle'] and actual['phase']=='cancelled' and not voice['active']
                and voice['capturedBytes']==voice['playedBytes']==actual['bufferedFrames']==0
                and voice['events'][-1]['publishedEpochMs']>=inputs[0]['ui']['sampleEpochMs'])
        return actual

    def completion_effect(self,operation,observation):
        need(self.version>=2 and operation['inputs']==[] and operation['quiet']==[])
        started=self.original(operation['startedBy']);need(started['verb']=='record-start')
        first=started['originals']['native']['audio']['recordedVoice'];native=observation['originals']['native'];voice=native['audio']['recordedVoice']
        actual=measured_state(native)
        need(first['active'] and first['event']['phase']=='capturing' and first['cycle']==operation['cycle']==voice['cycle']
            and same(first['events'],voice['events'][:len(first['events'])]) and not native['audio']['muted']
            and not voice['active'] and actual['phase']=='completed' and actual['error']=='none'
            and actual['history']==['capturing','playing','draining','completed']
            and 24000<=actual['recordedFrames']<=144000 and actual['playedFrames']==actual['recordedFrames']
            and actual['bufferedFrames']==0 and voice['capturedBytes']==voice['playedBytes']==0)
        return actual

    def mute_effect(self,operation,observation,inputs):
        before=self.original(operation['before']);old=before['originals']['native']['audio'];new=observation['originals']['native']['audio']
        wanted=self.phase_original(before['phaseBefore'],operation['ticket'],'mute')['enabled']
        need(self.version>=2 and same(self.phase_original(observation['phaseBefore'],operation['ticket'],'mute'),dict(enabled=wanted)))
        need(len(inputs)==int(old['muted']!=wanted) and new['muted'] is wanted and new['recordedVoice']['cycle']==operation['cycle'])
        controls=observation['originals']['ui']['controls'];rows=[row for row in controls if row['id']=='audio.mute']
        need(len(rows)==1 and rows[0]['inputReady'] and rows[0]['enabled'] and rows[0]['checked'] is wanted and rows[0]['nativeMuted'] is wanted)
        if inputs:
            item=inputs[0];need(item['identifier']=='audio.mute')
            native_rows=[row for row in item['ui']['controls'] if row['id']=='audio.mute'];need(len(native_rows)==1)
            row=native_rows[0];need(row['inputReady'] and row['enabled'] and row['nativeMuted'] is old['muted']
                and row['checked'] is old['muted'] and observation['originals']['native']['capturedEpochMs']>=item['ui']['sampleEpochMs'])
        voice=new['recordedVoice'];prior=old['recordedVoice'];actual=measured_state(observation['originals']['native'])
        if wanted and prior['active']:
            need(len(inputs)==1 and not voice['active'] and actual['phase']=='cancelled' and actual['error']=='microphone-muted'
                and voice['capturedBytes']==voice['playedBytes']==actual['bufferedFrames']==0
                and same(voice['events'][:len(prior['events'])],prior['events']) and len(voice['events'])==len(prior['events'])+1
                and voice['events'][-1]['publishedEpochMs']>=inputs[0]['ui']['sampleEpochMs'])
        else:
            # Unmute must not start or replay a recording. Preserve the actual
            # existing cycle/history, including an earlier error or completion.
            need(same(voice,prior))
        return actual

    def quiet_required(self,operation):
        if operation['verb']=='await-completion':return False
        if operation['verb']=='open':return False
        return operation['verb'] in ('record-cancel','mute','close') or self.version>=2 and self.original(operation['before'])['originals']['native']['audio']['muted']

    def page_intent(self,label,control,value,element):
        self.bound();operation=self.state['pending'];need(self.version>=3 and operation is not None and operation['verb'] in ('open','close'))
        need(not any(row.get('label')==label for row in operation['inputs']) and len(operation['inputs'])<72)
        ui_packet(value,int(self.binding['processIdentity']),value['sampleEpochMs']);status=self.phase.read()
        need(status['ticket']==operation['ticket'] and status['verb']==operation['verb'] and status['inputs']=={})
        operation['inputs'].append(dict(verb='page',identifier=control,ui=deepcopy(value),phase=status['status'],label=label,element=element,returned=False))
        self.save();return True

    @operation
    def adopt_background(self,child=None):
        """Retain one exact child, then acquire a fresh parent foreground cut."""
        from ios.adapters.audio_background import AudioBackground
        from ios.adapters.audio_background_bridge import proof
        self.bound();need(not self.historical and self.version>=4 and self.state['pending'] is None)
        if self.state['background'] is None:
            need(isinstance(child,AudioBackground) and not child.historical and type(child.state) is dict and child.state['phase']=='observed'
                and same(child.parent_original,self.previous) and child.binding==self.binding and child.run==self.run
                and child.lock.path==self.lock.path and child.root==self.root)
            child.file_guard();child.decode(child.previous)
            value=dict(iosAudioBackgroundBridgeVersion=1,before=deepcopy(self.state['records'][-1]),
                child=deepcopy(child.previous),bundle=deepcopy(child.os.gate.bundle))
            proof(self,value,self.state);self.state['background']=dict(proof=value,after=None);self.save()
        background=self.state['background'];last=proof(self,background['proof'],self.state)
        if background['after'] is None:
            self.recover_observation()
            candidates=[reference for reference in self.state['records'] if reference['index']>background['proof']['before']['index']]
            if candidates:
                need(len(candidates)==1);reference=candidates[0]
            else:reference=self.capture(last['ticket'],'background-resume')
            value=self.original(reference);need(value['verb']=='background-resume' and same(value['background'],background['proof']))
            background['after']=deepcopy(reference);self.decode(self.envelope(self.state));self.save()
        reference=background['after'];value=self.original(reference)
        return dict(performed=True,original=deepcopy(reference),state=measured_state(value['originals']['native']),historical=True)

    def page_returned(self,label):
        self.bound();operation=self.state['pending'];need(operation is not None)
        rows=[row for row in operation['inputs'] if row.get('label')==label];need(len(rows)==1 and not rows[0]['returned'])
        rows[0]['returned']=True;self.save()

    def page_inputs(self):
        from ios.adapters.audio_page_inputs import AudioPageInputs
        return AudioPageInputs(self.ui.io,self.ui.io.original.ui,self.page_intent,returned=self.page_returned,
            monotonic=self.monotonic,sleep=self.sleep)

    def page_flow(self,operation):
        from ios.adapters.audio_page_inputs import AudioPageInputs
        from ios.adapters import tablet_launcher_controls as launcher
        recipe=self.page_inputs()
        if operation['verb']=='open':
            current=recipe.capture()
            if AudioPageInputs.route(current)!='audio':recipe.open()
            candidates=[row['ui'] for row in operation['inputs'] if row['verb']=='page' and AudioPageInputs.route(row['ui'])=='launcher']
            need(candidates);operation['launcher']=launcher.selection(candidates[0]);self.save()
            self.ui.mute(False)
        else:
            initial=self.original(operation['openedBefore'])['originals']['native']['audio']['muted']
            current=recipe.capture()
            if AudioPageInputs.route(current)!='closed':
                if AudioPageInputs.route(current)=='audio':self.ui.mute(initial)
                recipe.close(operation['launcher'])

    def page_effect(self,operation,observation):
        from ios.adapters.audio_page_inputs import AudioPageInputs
        from ios.adapters import tablet_launcher_controls as launcher
        before=self.original(operation['before']);old,new=before['originals'],observation['originals']
        need(self.version>=3 and not old['native']['audio']['recordedVoice']['active']
            and not new['native']['audio']['recordedVoice']['active']
            and same(old['native']['audio']['recordedVoice'],new['native']['audio']['recordedVoice']))
        pages=[row for row in operation['inputs'] if row['verb']=='page'];need(pages)
        for row in operation['inputs']:
            need(before['clockJoin']['nativeAfter']['capturedEpochMs']<=row['ui']['sampleEpochMs']
                <=observation['clockJoin']['nativeBefore']['capturedEpochMs'])
        if operation['verb']=='open':
            need(AudioPageInputs.route(old['ui']) in ('closed','launcher') and AudioPageInputs.route(new['ui'])=='audio'
                 and not new['native']['audio']['muted'] and any(row['identifier'] in ('audio.entry','audio.settings-entry') for row in pages))
            original=next((row['ui'] for row in pages if AudioPageInputs.route(row['ui'])=='launcher'),None);need(original is not None)
            need(same(operation['launcher'],launcher.selection(original)))
            if AudioPageInputs.route(old['ui'])=='launcher':need(same(operation['launcher'],launcher.selection(old['ui'])))
            wanted=False
        else:
            need(AudioPageInputs.route(new['ui'])=='closed')
            close=[row for row in pages if row['identifier']=='tablet.close'];need(len(close)==1)
            selected=launcher.selection(close[0]['ui']);original=operation['launcher']
            need(selected['launcherCurrentIndex']==original['launcherCurrentIndex'] and selected['launcherPageCount']==original['launcherPageCount'])
            wanted=self.original(operation['openedBefore'])['originals']['native']['audio']['muted']
            need(new['native']['audio']['muted'] is wanted)
        mute=[row for row in operation['inputs'] if row['verb']=='mute']
        need(len(mute)==int(old['native']['audio']['muted']!=wanted))
        return dict(open=AudioPageInputs.route(new['ui'])=='audio',muted=new['native']['audio']['muted'])

    def quiet(self,operation,records):
        if not self.quiet_required(operation):need(operation['quiet']==[]);return
        need(len(operation['quiet'])==2 and all(reference in records for reference in operation['quiet'])
            and operation['quiet'][-1]==operation['after'] and operation['quiet'][0]['index']<operation['quiet'][1]['index'])
        first,last=[self.original(reference) for reference in operation['quiet']]
        self.effect(operation,first);self.effect(operation,last)
        need(last['clockJoin']['hostBeforeMonotonic']-first['clockJoin']['hostAfterMonotonic']>=.3
            and last['clockJoin']['nativeBefore']['capturedEpochMs']-first['clockJoin']['nativeAfter']['capturedEpochMs']>=300)

    @operation
    def resolve(self):
        self.bound();need(not self.historical);self.recover_observation();operation=self.state['pending'];need(operation is not None)
        if operation['verb'] in ('open','close'):self.page_flow(operation)
        reference=self.capture(operation['ticket'],operation['verb']);first=self.original(reference)
        if operation['verb']=='await-completion':
            while first['originals']['native']['audio']['recordedVoice']['event'].get('phase') in ('capturing','playing','draining'):
                need(first['originals']['native']['audio']['recordedVoice']['cycle']==operation['cycle'])
                self.sleep(.25);reference=self.capture(operation['ticket'],operation['verb']);first=self.original(reference)
        self.effect(operation,first)
        quiet=[]
        if self.quiet_required(operation):
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
    def act(self,ticket,verb,*,enabled=None):
        self.bound();need(not self.historical);identifier(ticket)
        if self.version>=4 and self.state['background'] is not None:need(self.state['background']['after'] is not None)
        need(verb in ('record-start','record-cancel') and enabled is None
             or self.version>=2 and verb=='await-completion' and enabled is None
             or self.version>=2 and verb=='mute' and type(enabled) is bool
             or self.version>=3 and verb in ('open','close') and enabled is None)
        self.recover_observation()
        if self.state['pending'] is not None:
            need(self.state['pending']['ticket']==ticket and self.state['pending']['verb']==verb)
            if verb=='mute':need(self.phase_original(self.original(self.state['pending']['before'])['phaseBefore'],ticket,verb)['enabled']==enabled)
            return self.resolve()
        retained=next((item for item in self.state['operations'] if item['ticket']==ticket),None)
        if retained is not None:
            need(retained['verb']==verb)
            if verb=='mute':need(self.phase_original(self.original(retained['before'])['phaseBefore'],ticket,verb)['enabled']==enabled)
            reference=self.capture(ticket,verb);actual=self.effect(retained,self.original(reference))
            return dict(performed=True,original=reference,state=actual)
        need(len(self.state['operations'])<32);reference=self.capture(ticket,verb);before=self.original(reference)
        voice=before['originals']['native']['audio']['recordedVoice']
        started=None
        opening=None
        if verb in ('open','close'):
            from ios.adapters.audio_page_inputs import AudioPageInputs
            need(not voice['active'] and not before['originals']['native']['audio']['recording'])
            if verb=='open':
                need(AudioPageInputs.route(before['originals']['ui']) in ('closed','launcher') and not any(row['verb']=='open' for row in self.state['operations']))
            else:
                opens=[row for row in self.state['operations'] if row['verb']=='open'];need(len(opens)==1);opening=opens[0]
                need(AudioPageInputs.route(before['originals']['ui']) in ('audio','launcher'))
                wanted=self.original(opening['before'])['originals']['native']['audio']['muted']
                if before['originals']['native']['audio']['muted']!=wanted:need(AudioPageInputs.route(before['originals']['ui'])=='audio')
                path=self.root/'ios-audio-pcm-lease.json'
                if path.exists():
                    from ios.adapters.audio_pcm_lease import IOSAudioPCMLease
                    archived=self.archive(self.store,self.root,self.binding,self.run,self.lock,self.fixture_url)
                    need(IOSAudioPCMLease.archive(PrivateFeatureState(path),archived).retired()['retired'])
        elif verb=='mute':need(self.phase_original(before['phaseBefore'],ticket,verb)['enabled']==enabled)
        elif verb=='await-completion':
            starts=[row for row in self.state['operations'] if row['verb']=='record-start' and row['after'] is not None
                and self.original(row['after'])['originals']['native']['audio']['recordedVoice']['cycle']==voice['cycle']]
            need(len(starts)==1 and not before['originals']['native']['audio']['muted']);started=deepcopy(starts[0]['after'])
            initial=self.original(started)['originals']['native']['audio']['recordedVoice']
            need(initial['active'] and initial['event']['phase']=='capturing')
        else:
            need(not before['originals']['native']['audio']['muted'] or self.version>=2 and verb=='record-start')
            if verb=='record-start':need(not voice['active'])
            else:need(voice['active'] and voice['cycle']>0)
        self.state['pending']=dict(ticket=ticket,verb=verb,cycle=voice['cycle'],before=reference,inputs=[],queries=[],after=None,quiet=[])
        if started is not None:self.state['pending']['startedBy']=started
        if verb in ('open','close'):self.state['pending']['launcher']=None if opening is None else deepcopy(opening['launcher'])
        if opening is not None:self.state['pending'].update(openedBy=deepcopy(opening['after']),openedBefore=deepcopy(opening['before']))
        self.save()
        if verb in ('open','close'):pass # Normal page flow executes once/resumes from actual current UI in resolve.
        elif verb=='record-start':self.ui.start()
        elif verb=='mute':self.ui.mute(enabled)
        elif verb=='await-completion':pass # The product timer owns capture/play/drain; no preview/stop input.
        else:self.ui.cancel(voice['cycle'])
        return self.resolve()
