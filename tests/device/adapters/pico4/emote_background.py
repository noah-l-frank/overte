"""One-send Pico Emote lifecycle input with original OS and native observations."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import time
from adapters.native_feature_observation import exact,need,number
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.normal_ui import NativeUIError
from adapters.graphics_journey.lifecycle import GraphicsBackground
from adapters.pico4.emote_sources import PicoEmoteSources
from adapters.pico4.emote_inputs import PicoEmoteInputs
from adapters.script_journey.lock import ScriptSourceLock
from adapters.script_journey.history import pack,unpack,same
from feature_journeys.contract import arguments
from feature_journeys.phase_fixture import PhaseFixtureReader,validate as phase_packet

VERSION=1


class PicoEmoteBackground:
    def __init__(self,phase,lock,sources,inputs,live,lifecycle,target,session,*,artifact_root,
                 monotonic=time.monotonic,sleep=time.sleep):
        need(isinstance(phase,PhaseFixtureReader) and phase.area=='emotes' and isinstance(lock,ScriptSourceLock)
            and isinstance(sources,PrivateFeatureState) and isinstance(inputs,PrivateFeatureState)
            and all(callable(fn) for fn in (live,session,monotonic,sleep)))
        lock.assert_held();self.phase,self.lock,self.sources,self.inputs=phase,lock,sources,inputs
        self.live,self.lifecycle,self.selector,self.session=live,lifecycle,target,session
        self.artifact_root=Path(artifact_root);self.run,self.fixture_url=phase.run,phase.fixture_url
        self.monotonic,self.sleep,self.started,self.clock=monotonic,sleep,None,None
        self.store=PrivateFeatureState(sources.path.with_name(sources.path.stem+'-background.json'))
        self.previous=self.store.read();self.state=None;self.failed=False;self.before_phase=None;self.historical=False
        if self.previous is not None:self.state=self.decode(self.previous)

    def bound(self):
        self.lock.assert_held();now=self.monotonic()
        need(not self.failed and number(now,0,1e15) and (self.clock is None or now>=self.clock)
            and (self.started is None or now-self.started<30) and same(self.store.read(),self.previous))
        self.clock=now

    def status(self,binding):
        self.bound();value=self.lifecycle._graphics_lifecycle_status(self.selector,binding)
        GraphicsBackground.status_packet(value,binding);self.bound();return deepcopy(value)

    def archive(self,header,binding):
        self.status(binding)
        result=PicoEmoteSources.archive(header,phase=self.phase,artifact_root=self.artifact_root,
            binding=binding,guard=self.bound,monotonic=self.monotonic)
        self.status(binding);return result

    def decode(self,value):
        exact(value,{'picoEmoteBackgroundVersion','runId','fixtureUrl','artifactRoot','payload'})
        need(type(value['picoEmoteBackgroundVersion']) is int and value['picoEmoteBackgroundVersion']==VERSION
            and value['runId']==self.run and value['fixtureUrl']==self.fixture_url and value['artifactRoot']==str(self.artifact_root))
        rows=unpack(value['payload']);need(len(rows)==1);state=rows[0]
        exact(state,{'binding','call','phase','beforeHeader','inputHeader','background','foreground','afterHeader','cleanup'})
        binding=context(state['binding']);call=arguments('feature.emotes.act',state['call'])
        need(call['runId']==self.run and call['fixtureUrl']==self.fixture_url and call['verb']=='background-resume'
            and state['phase'] in ('background-issued','background-observed','foreground-issued','observing','observed'))
        original,frames=self.archive(state['beforeHeader'],binding)
        need(original['phase']=='ready' and frames and state['beforeHeader']['role']=='primary')
        self.idle(frames[-1]);self.active(call,frames[-1]['phaseBefore']);self.active(call,frames[-1]['phaseAfter'])
        self.input_admission(state['inputHeader'],state['beforeHeader'],binding)
        if state['background'] is not None:
            GraphicsBackground.status_packet(state['background'],binding);need(state['background']['foreground'] is False)
        if state['phase']!='background-issued':need(state['background'] is not None)
        if state['foreground'] is not None:
            GraphicsBackground.status_packet(state['foreground'],binding);need(state['foreground']['foreground'] is True)
        if state['phase'] in ('observing','observed'):need(state['foreground'] is not None)
        if state['afterHeader'] is not None:
            after_state,after=self.archive(state['afterHeader'],binding)
            need(after_state['phase']=='ready' and len(after)>len(frames) and same(after[:len(frames)],frames))
            self.completed(frames[-1],after[-1]);self.active(call,after[-1]['phaseBefore']);self.active(call,after[-1]['phaseAfter'])
        need((state['afterHeader'] is not None)==(state['phase']=='observed'))
        cleanup=state['cleanup']
        if cleanup is not None:
            exact(cleanup,{'phase','provider','foreground'});need(cleanup['phase'] in ('foreground-issued','observed'))
            self.cleanup_phase(cleanup['provider'],frames[-1]['phaseAfter'])
            if cleanup['foreground'] is not None:
                GraphicsBackground.status_packet(cleanup['foreground'],binding);need(cleanup['foreground']['foreground'] is True)
            need((cleanup['foreground'] is not None)==(cleanup['phase']=='observed'))
        self.before_phase=deepcopy(frames[-1]['phaseAfter']);return deepcopy(state)

    def input_admission(self,header,source_header,binding,*,current=False):
        need(header is not None and type(current) is bool)
        if current:need(same(self.inputs.read(),header))
        state,history=PicoEmoteInputs.archive(header,source_header,phase=self.phase,artifact_root=self.artifact_root,
            binding=binding,guard=self.bound,monotonic=self.monotonic)
        need(history['pendingArchive'] is None and (state['current'] is None or state['current']['phase']=='acknowledged'))

    def save(self):
        try:
            self.bound();self.status(self.state['binding'])
            value=dict(picoEmoteBackgroundVersion=VERSION,runId=self.run,fixtureUrl=self.fixture_url,
                artifactRoot=str(self.artifact_root),payload=pack([self.state]))
            self.store.write(value,self.previous);need(same(self.store.read(),value));self.previous=deepcopy(value);self.bound()
        except Exception:self.failed=True;raise

    def lifecycle_input(self,operation,binding):
        return self.lifecycle._graphics_lifecycle_input(self.selector,operation,binding)

    def wait_activation(self):
        started=self.monotonic();need(number(started,0,1e15))
        for attempt in range(51):
            self.current_phase(self.state['call']);status=self.status(self.state['binding'])
            if status['foreground'] is True:return status
            if attempt==50 or self.monotonic()-started>=5:break
            self.sleep(.1)
        raise NativeUIError('Original Pico activation remains unobserved')

    def act(self,call):
        call=deepcopy(arguments('feature.emotes.act',call));need(call['verb']=='background-resume'
            and call['runId']==self.run and call['fixtureUrl']==self.fixture_url)
        self.started=self.monotonic()
        try:
            self.bound();self.current_phase(call);need(self.state is None or self.state['cleanup'] is None)
            with self.session():
                if self.state is None:
                    source=self.live();need(self.status(source.binding)['foreground'] is True)
                    before=source.read();self.idle(before)
                    self.active(call,before['phaseBefore']);self.active(call,before['phaseAfter'])
                    input_header=self.inputs.read();self.input_admission(input_header,source.previous,source.binding,current=True)
                    self.before_phase=deepcopy(before['phaseAfter'])
                    self.state=dict(binding=deepcopy(source.binding),call=call,phase='background-issued',
                        beforeHeader=deepcopy(source.previous),inputHeader=deepcopy(input_header),background=None,
                        foreground=None,afterHeader=None,cleanup=None)
                    self.save();self.current_phase(call);self.lifecycle_input('lifecycle.background',source.binding);self.bound()
                else:need(same(self.state['call'],call));self.decode(self.previous)
                state=self.state;binding=state['binding']
                if state['phase'] in ('background-issued','background-observed','foreground-issued'):
                    need(same(self.sources.read(),state['beforeHeader']) and same(self.inputs.read(),state['inputHeader']))
                if state['phase']=='background-issued':
                    state.update(phase='background-observed',background=self.wait_background());self.save()
                if state['phase']=='background-observed':
                    need(self.status(binding)['foreground'] is False)
                    state['phase']='foreground-issued';self.save();self.current_phase(call)
                    self.lifecycle_input('app.launch',binding);self.bound()
                if state['phase']=='foreground-issued':
                    state.update(phase='observing',foreground=self.wait_activation());self.save()
                need(state['phase'] in ('observing','observed') and self.status(binding)['foreground'] is True)
                source=self.live();need(same(source.binding,binding) and source.state['phase']=='ready')
                _before,original=self.archive(state['beforeHeader'],binding)
                need(same(source.frames[:len(original)],original))
                after=source.read();self.completed(original[-1],after)
                self.active(call,after['phaseBefore']);self.active(call,after['phaseAfter'])
                state.update(phase='observed',afterHeader=deepcopy(source.previous));self.save();self.bound()
            return {'performed':True}
        finally:self.started=None

    @staticmethod
    def idle(frame):
        native=frame['group']['native'];animation=native['animation']
        need(animation['overrideActive'] is False and not any(row['id']=='emote.page' and row['activeName']
            for row in PicoEmoteSources.ui(frame)['controls']))
        return native


    @staticmethod
    def active(call,status):
        need(status['active'] and status['activations'])
        current=status['activations'][-1]
        need(current['ticket']==call['ticket'] and current['stimulus']['verb']=='background-resume'
            and same(current['stimulus']['inputs'],call['inputs']))


    def current_phase(self,call):
        self.bound()
        try:status=self.phase.status(self.before_phase)
        except ValueError:raise NativeUIError('Original Emote background fixture phase changed') from None
        self.active(call,status);self.bound()
        return status


    @classmethod
    def completed(cls,before,after):
        left,right=cls.idle(before),cls.idle(after)
        need(left['instance']==right['instance'] and left['processId']==right['processId']
            and right['sequence']>left['sequence'] and right['requestedEpochMs']>=left['capturedEpochMs']
            and right['lifecycle']['backgrounds']>=left['lifecycle']['backgrounds']+1
            and right['lifecycle']['activations']>=left['lifecycle']['activations']+1
            and right['lifecycle']['launches']==left['lifecycle']['launches']
            and left['animation']['rigId']==right['animation']['rigId']
            and right['animation']['evaluationSequence']>left['animation']['evaluationSequence']
            and same(left['animation']['history']['events'],right['animation']['history']['events'])
            and left['animation']['history']['callSequence']==right['animation']['history']['callSequence'])


    def wait_background(self):
        started=self.monotonic();need(number(started,0,1e15))
        for attempt in range(51):
            status=self.status(self.state['binding'])
            if status['foreground'] is False:return status
            if attempt==50 or self.monotonic()-started>=5:break
            self.sleep(.1)
        raise NativeUIError('Normal Emote background input did not change actual OS state')


    def cleanup_phase(self,value,previous=None):
        phase_packet(value,run=self.run,area='emotes',request=value.get('requestId'),epoch=value.get('capturedEpochMs'),previous=previous)
        need(value['active'] and value['activations'] and value['activations'][-1]['stimulus']==dict(verb='cleanup',inputs={}))
        return value['activations'][-1]['ticket']


    def cleanup_current(self):
        need(self.state is not None);cleanup=self.state['cleanup']
        previous=cleanup['provider'] if cleanup is not None else self.before_phase
        self.bound();value=self.phase.status(previous);ticket=self.cleanup_phase(value,previous)
        if cleanup is not None:need(ticket==self.cleanup_phase(cleanup['provider']))
        self.bound();return value


    def wait_foreground(self):
        started=self.monotonic();need(number(started,0,1e15))
        for attempt in range(51):
            self.cleanup_current();status=self.status(self.state['binding'])
            if status['foreground'] is True:return status
            if attempt==50 or self.monotonic()-started>=5:break
            self.sleep(.1)
        raise NativeUIError('Owned cleanup activation did not reach actual foreground')


    def recover_foreground(self,call):
        """One separately owned cleanup activation; never complete an old action."""
        call=arguments('feature.emotes.cleanup',call);need(self.historical is False and call['runId']==self.run)
        self.started=self.monotonic()
        try:
            self.bound();need(self.state is not None and same(self.decode(self.previous),self.state))
            with self.session():
                provider=self.cleanup_current();binding=self.state['binding']
                if self.state['cleanup'] is None:
                    status=self.status(binding)
                    self.state['cleanup']=dict(phase='observed' if status['foreground'] else 'foreground-issued',
                        provider=provider,foreground=status if status['foreground'] else None)
                    self.save()
                    if self.state['cleanup']['phase']=='foreground-issued':
                        self.cleanup_current();self.lifecycle_input('app.launch',binding);self.bound()
                if self.state['cleanup']['phase']=='foreground-issued':
                    status=self.wait_foreground();self.state['cleanup'].update(phase='observed',foreground=status);self.save()
                self.cleanup_current();need(self.status(binding)['foreground'] is True);self.decode(self.previous)
                result=dict(picoEmoteForegroundRecoveryVersion=1,header=deepcopy(self.previous));self.bound();return result
        finally:self.started=None



    @classmethod
    def completed_archive(cls,header,source):
        """Reopen completed original lifecycle evidence without OS/native reads.

        This grants historical context only. It cannot create an input owner,
        acquire a current source or retire any responsibility.
        """
        need(isinstance(source,PicoEmoteSources));source.lock.assert_held()
        started=previous=source.monotonic();need(number(started,0,1e15))
        def bound():
            nonlocal previous
            source.lock.assert_held();need(source.guard() is not False)
            now=source.monotonic();need(number(now,previous,1e15) and now-started<5);previous=now
        bound();exact(header,{'picoEmoteBackgroundVersion','runId','fixtureUrl','artifactRoot','payload'})
        need(type(header['picoEmoteBackgroundVersion']) is int and header['picoEmoteBackgroundVersion']==VERSION
            and header['runId']==source.run and header['fixtureUrl']==source.phase.fixture_url
            and header['artifactRoot']==str(source.artifact_root))
        rows=unpack(header['payload']);need(len(rows)==1);state=rows[0]
        exact(state,{'binding','call','phase','beforeHeader','inputHeader','background','foreground','afterHeader','cleanup'})
        need(same(context(state['binding']),source.binding) and state['phase']=='observed' and state['cleanup'] is None)
        call=arguments('feature.emotes.act',state['call']);need(call['runId']==source.run
            and call['fixtureUrl']==source.phase.fixture_url and call['verb']=='background-resume')
        frames=[]
        for value in (state['beforeHeader'],state['afterHeader']):
            need(type(value) is dict and value.get('role')=='primary')
            original,group=PicoEmoteSources.archive(value,phase=source.phase,artifact_root=source.artifact_root,
                binding=source.binding,guard=bound,monotonic=source.monotonic)
            need(original['phase']=='ready' and original['pending'] is None and group)
            for key in ('phaseBefore','phaseAfter'):cls.active(call,group[-1][key])
            frames.append(group)
        before,after=frames;need(len(after)>len(before) and same(after[:len(before)],before))
        cls.completed(before[-1],after[-1])
        for key,foreground in (('background',False),('foreground',True)):
            GraphicsBackground.status_packet(state[key],source.binding);need(state[key]['foreground'] is foreground)
        inputs,history=PicoEmoteInputs.archive(state['inputHeader'],state['beforeHeader'],phase=source.phase,
            artifact_root=source.artifact_root,binding=source.binding,guard=bound,monotonic=source.monotonic)
        need(history['pendingArchive'] is None and (inputs['current'] is None or inputs['current']['phase']=='acknowledged'))
        bound();return deepcopy(state),deepcopy(before),deepcopy(after)
