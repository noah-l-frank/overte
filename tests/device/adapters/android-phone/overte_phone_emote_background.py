"""Owned one-send Emote Home/activation with actual OS and native effects."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import time

from adapters.native_feature_observation import exact,need,number
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.normal_ui import NativeUIError
from feature_journeys.contract import arguments
from feature_journeys.phase_fixture import PhaseFixtureReader,validate as phase_packet
from overte_phone_emote_sources import PhoneEmoteSources,source_name
from overte_phone_emote_inputs import PhoneEmoteInputs
from overte_phone_graphics_lifecycle import PhoneGraphicsBackground
from overte_phone_script_history import pack,unpack,same
from overte_phone_script_lock import PhoneScriptSourceLock

VERSION=2


class PhoneEmoteBackground:
    def __init__(self,adapter,selector,phase,lock,*,artifact_root,monotonic=time.monotonic,sleep=time.sleep,segment=0):
        need(isinstance(phase,PhaseFixtureReader) and phase.area=='emotes' and isinstance(lock,PhoneScriptSourceLock)
            and callable(monotonic) and callable(sleep));lock.assert_held()
        self.adapter,self.selector,self.phase,self.lock=adapter,selector,phase,lock
        self.artifact_root=Path(artifact_root);self.monotonic,self.sleep=monotonic,sleep
        self.run,self.fixture_url=phase.run,phase.fixture_url
        self.segment=segment;name=source_name('primary',segment)
        path=adapter.state_path(selector);need(lock.path==path.with_name('phone-script-sources.lock'))
        self.store=PrivateFeatureState(path.with_name('phone-emote-background.json'))
        self.sources=PrivateFeatureState(path.with_name(name))
        self.previous=self.store.read();self.state=None;self.failed=False;self.started=self.clock=None;self.before_phase=None
        if self.previous is not None:
            try:self.state=self.decode(self.previous)
            except (KeyError,TypeError,ValueError,OSError):
                raise NativeUIError('Original Emote background ownership is invalid') from None

    def bound(self):
        self.lock.assert_held();now=self.monotonic()
        need(not self.failed and number(now,0,1e15) and (self.clock is None or now>=self.clock)
            and (self.started is None or now-self.started<30) and same(self.store.read(),self.previous))
        self.clock=now

    def status(self,binding):
        self.bound();value=self.adapter._emote_lifecycle_status(self.selector,binding)
        PhoneGraphicsBackground.status_packet(value,binding);self.bound();return deepcopy(value)

    def archive(self,header,binding):
        self.status(binding)
        result=PhoneEmoteSources.archive(header,phase=self.phase,artifact_root=self.artifact_root,
            binding=binding,guard=self.bound,monotonic=self.monotonic)
        self.status(binding);return result

    @staticmethod
    def idle(frame):
        native=frame['group']['native'];animation=native['animation']
        need(animation['overrideActive'] is False and not any(row['id']=='emote.page' and row['activeName']
            for row in frame['ui']['controls']))
        return native

    def active(self,call,status):
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

    def completed(self,before,after):
        left,right=self.idle(before),self.idle(after)
        need(left['instance']==right['instance'] and left['processId']==right['processId']
            and right['sequence']>left['sequence'] and right['requestedEpochMs']>=left['capturedEpochMs']
            and right['lifecycle']['backgrounds']>=left['lifecycle']['backgrounds']+1
            and right['lifecycle']['activations']>=left['lifecycle']['activations']+1
            and right['lifecycle']['launches']==left['lifecycle']['launches']
            and left['animation']['rigId']==right['animation']['rigId']
            and right['animation']['evaluationSequence']>left['animation']['evaluationSequence']
            and same(left['animation']['history']['events'],right['animation']['history']['events'])
            and left['animation']['history']['callSequence']==right['animation']['history']['callSequence'])

    def decode(self,value):
        need(type(value) is dict and type(value.get('emoteBackgroundVersion')) is int and value['emoteBackgroundVersion'] in (1,2))
        version=value['emoteBackgroundVersion']
        exact(value,{'emoteBackgroundVersion','runId','fixtureUrl','artifactRoot','payload'}|({'sourceSegment'} if version==2 else set()))
        need((version==1 and self.segment==0 or version==2 and type(value['sourceSegment']) is int and value['sourceSegment']==self.segment)
            and value['runId']==self.run and value['fixtureUrl']==self.fixture_url and value['artifactRoot']==str(self.artifact_root))
        rows=unpack(value['payload']);need(len(rows)==1);state=rows[0]
        exact(state,{'binding','call','phase','beforeHeader','background','foreground','afterHeader'}|({'cleanup'} if version==2 else set()))
        if version==1:state['cleanup']=None
        binding=context(state['binding']);call=arguments('feature.emotes.act',state['call'])
        need(call['runId']==self.run and call['fixtureUrl']==self.fixture_url and call['verb']=='background-resume'
            and state['phase'] in ('background-issued','background-observed','foreground-issued','observing','observed'))
        original,frames=self.archive(state['beforeHeader'],binding)
        need(original['phase']=='ready' and frames and state['beforeHeader']['role']=='primary')
        self.idle(frames[-1]);self.active(call,frames[-1]['phaseBefore']);self.active(call,frames[-1]['phaseAfter'])
        if state['background'] is not None:
            PhoneGraphicsBackground.status_packet(state['background'],binding);need(state['background']['foreground'] is False)
        if state['phase']!='background-issued':need(state['background'] is not None)
        if state['foreground'] is not None:
            PhoneGraphicsBackground.status_packet(state['foreground'],binding);need(state['foreground']['foreground'] is True)
        if state['phase'] in ('observing','observed'):need(state['foreground'] is not None)
        if state['afterHeader'] is not None:
            _after,after=self.archive(state['afterHeader'],binding);need(_after['phase']=='ready' and after
                and len(after)>len(frames) and same(after[:len(frames)],frames))
            self.completed(frames[-1],after[-1]);self.active(call,after[-1]['phaseBefore']);self.active(call,after[-1]['phaseAfter'])
        need((state['afterHeader'] is not None)==(state['phase']=='observed'))
        cleanup=state['cleanup']
        if cleanup is not None:
            exact(cleanup,{'phase','provider','foreground'})
            need(cleanup['phase'] in ('foreground-issued','observed'))
            self.cleanup_phase(cleanup['provider'],frames[-1]['phaseAfter'])
            if cleanup['foreground'] is not None:
                PhoneGraphicsBackground.status_packet(cleanup['foreground'],binding);need(cleanup['foreground']['foreground'] is True)
            need((cleanup['foreground'] is not None)==(cleanup['phase']=='observed'))
        self.before_phase=deepcopy(frames[-1]['phaseAfter'])
        return deepcopy(state)

    def save(self):
        try:
            self.bound();self.status(self.state['binding'])
            value=dict(emoteBackgroundVersion=VERSION,runId=self.run,fixtureUrl=self.fixture_url,
                artifactRoot=str(self.artifact_root),sourceSegment=self.segment,payload=pack([self.state]))
            self.store.write(value,self.previous);need(same(self.store.read(),value));self.previous=deepcopy(value);self.bound()
        except Exception:
            self.failed=True
            raise

    def wait_background(self):
        started=self.monotonic();need(number(started,0,1e15))
        for attempt in range(51):
            status=self.status(self.state['binding'])
            if status['foreground'] is False:return status
            if attempt==50 or self.monotonic()-started>=5:break
            self.sleep(.1)
        raise NativeUIError('Normal Emote background input did not change actual OS state')

    def live(self):
        return PhoneEmoteSources(self.adapter,self.selector,self.phase,'primary',self.lock,
            artifact_root=self.artifact_root,monotonic=self.monotonic,segment=self.segment)

    def act(self,call):
        call=deepcopy(arguments('feature.emotes.act',call));need(call['verb']=='background-resume'
            and call['runId']==self.run and call['fixtureUrl']==self.fixture_url)
        self.started=self.monotonic();self.bound();self.current_phase(call)
        need(self.state is None or self.state['cleanup'] is None)
        with self.adapter.existing_input_session(self.selector):
            if self.state is None:
                source=self.live();need(self.status(source.binding)['foreground'] is True)
                inputs=PhoneEmoteInputs(source)
                need(inputs.history_state['pendingArchive'] is None and (inputs.state['current'] is None
                    or inputs.state['current']['phase']=='acknowledged'))
                before=source.read();self.idle(before)
                self.active(call,before['phaseBefore']);self.active(call,before['phaseAfter'])
                self.before_phase=deepcopy(before['phaseAfter'])
                self.state=dict(binding=deepcopy(source.binding),call=call,phase='background-issued',
                    beforeHeader=deepcopy(source.previous),background=None,foreground=None,afterHeader=None,cleanup=None)
                self.save();self.current_phase(call)
                self.adapter.invoke(self.selector,'lifecycle.background',{});self.bound()
            else:
                need(same(self.state['call'],call));self.decode(self.previous)
            state=self.state;binding=state['binding']
            if state['phase'] in ('background-issued','background-observed','foreground-issued'):
                need(same(self.sources.read(),state['beforeHeader']))
            if state['phase']=='background-issued':
                state.update(phase='background-observed',background=self.wait_background());self.save()
            if state['phase']=='background-observed':
                need(self.status(binding)['foreground'] is False)
                state['phase']='foreground-issued';self.save();self.current_phase(call)
                self.adapter.invoke(self.selector,'app.launch',{});self.bound()
            if state['phase']=='foreground-issued':
                foreground=self.status(binding);need(foreground['foreground'] is True)
                state.update(phase='observing',foreground=foreground);self.save()
            need(state['phase'] in ('observing','observed') and self.status(binding)['foreground'] is True)
            source=self.live();need(same(source.binding,binding) and source.state['phase']=='ready')
            _before,original=self.archive(state['beforeHeader'],binding)
            need(same(source.frames[:len(original)],original))
            # A lost read result never replays Home/activation. Completed source
            # originals remain historical; obtain a new read before delivery.
            after=source.read();self.completed(original[-1],after)
            self.active(call,after['phaseBefore']);self.active(call,after['phaseAfter'])
            state.update(phase='observed',afterHeader=deepcopy(source.previous));self.save();self.bound()
        return {'performed':True} # OS/native lifecycle proof only; no whole-feature result.

    def retire(self,*,retain=None):
        need(retain is None or callable(retain));self.started=self.monotonic()
        try:
            self.bound();need(self.state is not None and self.state['phase']=='observed' and self.state['cleanup'] is None)
            need(same(self.decode(self.previous),self.state) and same(self.sources.read(),self.state['afterHeader']))
            binding=self.state['binding'];need(self.status(binding)['foreground'] is True)
            if retain is not None:
                need(retain(deepcopy(self.previous)) is not False);self.bound();self.decode(self.previous)
                need(same(self.sources.read(),self.state['afterHeader']) and self.status(binding)['foreground'] is True)
            self.store.discard(self.previous);need(self.store.read() is None)
            self.previous=self.state=None;self.bound();need(self.status(binding)['foreground'] is True)
        finally:self.started=None

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
        call=arguments('feature.emotes.cleanup',call);need(call['runId']==self.run)
        self.started=self.monotonic()
        try:
            self.bound();need(self.state is not None and same(self.decode(self.previous),self.state))
            with self.adapter.existing_input_session(self.selector):
                provider=self.cleanup_current();binding=self.state['binding']
                if self.state['cleanup'] is None:
                    status=self.status(binding)
                    self.state['cleanup']=dict(phase='observed' if status['foreground'] else 'foreground-issued',
                        provider=provider,foreground=status if status['foreground'] else None)
                    self.save()
                    if self.state['cleanup']['phase']=='foreground-issued':
                        self.cleanup_current();self.adapter.invoke(self.selector,'app.launch',{});self.bound()
                if self.state['cleanup']['phase']=='foreground-issued':
                    status=self.wait_foreground();self.state['cleanup'].update(phase='observed',foreground=status);self.save()
                self.cleanup_current();need(self.status(binding)['foreground'] is True);self.decode(self.previous)
                result=dict(emoteForegroundRecoveryVersion=1,header=deepcopy(self.previous));self.bound();return result
        finally:self.started=None

    def recovery_archive(self,value):
        """Historical original recovery context; no native getter or feature pass."""
        outer=self.started is None
        if outer:self.started=self.monotonic();need(number(self.started,0,1e15))
        try:return self._recovery_archive(value)
        finally:
            if outer:self.started=None

    def _recovery_archive(self,value):
        self.bound();exact(value,{'emoteForegroundRetirementVersion','header','sourceHeader'})
        need(type(value['emoteForegroundRetirementVersion']) is int and value['emoteForegroundRetirementVersion']==1)
        state=self.decode(value['header']);need(state['cleanup'] is not None and state['cleanup']['phase']=='observed')
        need(type(value['sourceHeader']) is dict and value['sourceHeader'].get('role')=='primary')
        _original,frames=self.archive(state['beforeHeader'],state['binding'])
        _current,after=self.archive(value['sourceHeader'],state['binding'])
        need(same(after[:len(frames)],frames))
        result=deepcopy(value);self.bound();return result

    def retire_recovery(self,retain):
        """Transfer old failure plus cleanup proof before removing this lease."""
        need(callable(retain));self.started=self.monotonic()
        try:
            self.bound();need(self.state is not None and self.state['cleanup'] is not None and self.state['cleanup']['phase']=='observed')
            need(same(self.decode(self.previous),self.state))
            self.cleanup_current();binding=self.state['binding'];need(self.status(binding)['foreground'] is True)
            value=dict(emoteForegroundRetirementVersion=1,header=deepcopy(self.previous),sourceHeader=self.sources.read())
            self.recovery_archive(value);need(retain(deepcopy(value)) is not False)
            self.bound();self.cleanup_current();self.recovery_archive(value)
            need(same(self.sources.read(),value['sourceHeader']) and self.status(binding)['foreground'] is True)
            self.store.discard(self.previous);need(self.store.read() is None);self.previous=self.state=None
            self.bound();need(self.status(binding)['foreground'] is True);return value
        finally:self.started=None
