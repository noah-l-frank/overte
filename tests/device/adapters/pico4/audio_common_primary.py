"""Primary Common observations from new original bundles in the existing bank.

This participant does not export audio artifacts, drive cleanup or advertise a
complete feature. Independent Actor publication acquires its own later bundle.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
from adapters.chat_journey.source_chunks import json_digest
from adapters.native_feature_observation import fresh,integer,need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.pico4.audio_observation_bundle import validate
from adapters.pico4.audio_pc_start import PicoAudioPCStartCoordinator
from adapters.pico4.audio_settings_source import CLOCKS
from adapters.pico4.lifecycle_process_file import LifecycleProcessFile
from adapters.script_journey.history import canonical
from feature_journeys.contract import arguments,result

VERSION=1


class AudioCommonPrimary1:
    def __init__(self,coordinator):
        need(type(coordinator) is PicoAudioPCStartCoordinator and coordinator.actor.observation_bundle is not None)
        self.coordinator,self.actor,self.source=coordinator,coordinator.actor,coordinator.recipe.source
        self.client=self.source.client;self.credential=hashlib.sha256(self.client.token.encode()).hexdigest()
        need(self.client.token!=self.actor.source.client.token and self.source.run==self.actor.recipe.run
            and self.source.fixture_url==self.actor.source.fixture_url)
        self.failed=False;self.failure=None;self.state=None;self.physical=None
        self.scope=dict(audioCommonPrimaryVersion=VERSION,runId=self.source.run,binding=deepcopy(self.actor.recipe.binding),
            primaryCredentialSha256=self.credential,originalActorHeader=deepcopy(self.actor.header_ref))
        self.scope_sha=json_digest(self.scope)
        self.store=PrivateFeatureState(self.actor.store.path.with_name('audio-common-primary.json'))
        try:
            with self.actor.held():
                self.actor.bound();need(self.store.read() is None)
                self.physical=object.__new__(LifecycleProcessFile)
                LifecycleProcessFile.__init__(self.physical,self.store)
                self.save(dict(sequence=0,last=None,pending=None))
        except BaseException as error:self.poison(error);raise

    def poison(self,error):
        if self.failure is None:self.failure=(error,error.__traceback__)
        self.failed=True;self.actor.raws.stopped=True

    def guard(self):
        self.actor.lock.assert_held();self.actor.recipe.lock.assert_held()
        need(not self.failed and self.source is self.actor.recipe.source and self.source.client is self.client
            and self.coordinator.actor is self.actor and json_digest(self.scope)==self.scope_sha
            and hashlib.sha256(self.client.token.encode()).hexdigest()==self.credential
            and self.client.token!=self.actor.source.client.token)
        self.actor.bound();self.physical.guard();need(self.store.read()==self.state)

    def save(self,value):
        body=dict(scope=deepcopy(self.scope),value=deepcopy(value))
        need(len(canonical(body))+1<=16384)
        self.physical.write(body,self.state);self.state=deepcopy(body)

    def previous(self):
        last=self.state['value']['last']
        if last is None:return None
        raw=self.actor.raws.literal(last['rawReference'])
        # Historical decoding uses its ORIGINAL recorded epoch; it cannot
        # create a renewed live observation or change an original source time.
        return validate(raw,last['command'],self.actor.native.pid,self.actor.pages.bridge,last['epoch'])

    def observe(self,after_sequence):
        need(integer(after_sequence,0,4095))
        try:
            with self.actor.held():
                self.guard();need(self.state['value']['pending'] is None)
                before=self.source.status();need(before['active'] and before['activations'])
                ticket=before['activations'][-1]['ticket']
                self.save(dict(self.state['value'],pending=dict(ticket=ticket,before=before)))
                previous=self.previous()
                self.actor._begin('primary-observation',ticket)
                started=self.actor.state['pending']['started']
                current=self.actor.observation_bundle.capture(previous)
                after=self.source.status(before)
                need(after['active'] and after['activations']==before['activations'])
                native,settings,pages=(current[key] for key in ('native','settings','pages'))
                captured=min(native['requestedEpochMs'],native['capturedEpochMs'],settings['capturedEpochMs'],
                    pages['picoAudioPages']['capturedEpochMs'],*(settings['source'][key] for key in CLOCKS))
                actual=deepcopy(current['actual']);resources=[]
                if actual['open']:resources.append('panel:audio')
                if actual['recording'] or actual['preview']:resources.append('input:recorded-preview')
                sequence=max(after_sequence,self.state['value']['sequence'])+1;need(sequence<=4096)
                frame=result('feature.audio.observe',dict(schemaVersion=1,contractVersion=16,runId=self.source.run,
                    sequence=sequence,capturedEpochMs=captured,state=actual,artifacts=[],resources=resources,
                    lifecycle=deepcopy(native['lifecycle'])))
                transport=self.actor.observation_bundle
                last=dict(ticket=ticket,epoch=current['envelope']['capturedEpochMs'],
                    command=deepcopy(transport.last_command),rawReference=deepcopy(transport.last_reference),
                    resultSha256=json_digest(frame),after=after)
                # All original source bytes are already in the same raw bank.
                # This small sidecar stores references rather than extra Actor
                # history frames for the primary role's parsed snapshots.
                self.save(dict(sequence=sequence,last=last,pending=None))
                value=deepcopy(self.actor.state);value['pending']=None;self.actor._save(value)
                self.guard();self.actor.native.guard();self.actor.settings.guard();self.actor.pages.guard()
                fresh(captured,self.actor.native.clock_ms());need(0<=self.actor.monotonic()-started<=1.5)
                return frame
        except BaseException as error:self.poison(error);raise

    def invoke(self,operation,fields):
        call=arguments(operation,fields)
        need(call['runId']==self.source.run)
        if operation=='feature.audio.observe':return self.observe(call['afterSequence'])
        need(operation=='feature.audio.act' and call['fixtureUrl']==self.source.fixture_url)
        self.coordinator.act(call)
        return result(operation,dict(performed=True))

    def close_host(self):
        return self.physical is None or self.physical.close_host()
