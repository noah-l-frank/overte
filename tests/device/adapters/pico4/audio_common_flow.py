"""Common Audio actions/observations with original PCM and PC file acquisitions.

Cleanup and public routing remain separate integration obligations. Neither a
capture request nor its acknowledgment contributes a measured Audio state.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_feature_observation import need
from adapters.pico4.audio_common_primary import AudioCommonPrimary1
from adapters.pico4.audio_common_files import PicoAudioCommonFiles1
from adapters.pico4.audio_recipe_evidence import completed,wav
from adapters.pico4.audio_capture_owner import read_original_file
from feature_journeys.contract import arguments,result

VERSION=1


class AudioCommonFlow1:
    def __init__(self,primary,files):
        need(type(primary) is AudioCommonPrimary1 and type(files) is PicoAudioCommonFiles1
            and primary.actor is files.actor)
        self.primary,self.files=primary,files
        self.coordinator,self.actor,self.source=primary.coordinator,primary.actor,primary.source
        self.silence=set();self.failed=False;self.failure=None

    def poison(self,error):
        if self.failure is None:self.failure=(error,error.__traceback__)
        self.failed=True

    def invoke(self,operation,fields):
        call=arguments(operation,fields);need(call['runId']==self.source.run and not self.failed)
        try:
            if operation=='feature.audio.observe':return self.observe(call['afterSequence'])
            need(operation=='feature.audio.act' and call['fixtureUrl']==self.source.fixture_url)
            self.coordinator.act(call)
            ticket,verb=call['ticket'],call['verb']
            quiet=(verb=='mute' and call['inputs']['enabled'] is True
                or verb in ('record-cancel','background-resume'))
            if quiet and ticket not in self.silence:
                # The normal action has already finished. Capture its actual
                # subsequent output, avoiding unmuted pre-action samples.
                self.actor.arm(ticket,3.25,wait_ready=False);self.actor.wait_saved(ticket);self.silence.add(ticket)
            elif verb=='record-start' and ticket not in self.silence and self.actor.job(ticket)['seconds']==3.25:
                # Reuse the capture already armed from actual muted state by
                # the ordinary coordinator; never resend its receive/input.
                self.actor.wait_saved(ticket);self.silence.add(ticket)
            return result(operation,dict(performed=True))
        except BaseException as error:self.poison(error);raise

    def observe(self,after_sequence):
        need(not self.failed)
        try:
            phase=self.source.status();need(phase['active'] and phase['activations'])
            ticket=phase['activations'][-1]['ticket'];artifacts=[]
            if ticket in self.silence:
                peer=self.actor.peer();packet,raw=peer.original(self.source.run,ticket)
                need(raw is not None and packet['exists'] is True and packet['retired'] is False)
                file=self.files.write(ticket,'peer',ticket,raw,packet)
                # Acquisition is a NEW original PC query/file read. Capture
                # production/closure times remain untouched in provenance.
                artifacts.append(dict(kind='audio',name=file['name'],ticket=ticket,capturedEpochMs=packet['capturedEpochMs']))
            elif self.actor.recipe.state['cursor']>=8 and phase['activations'][-1]['stimulus']['verb']=='await-completion':
                recipe=self.actor.recipe;source_ticket,root,child=completed(recipe,recipe.state)
                source=child['original']['source'];rate,channels=source['sampleRate'],source['channels']
                pcm=read_original_file(recipe.store.path,child['artifacts']['input'])
                raw=wav(pcm,rate,channels)
                file=self.files.write(source_ticket,'input',source_ticket,raw,child['original'])
                acquired=self.actor.native.clock_ms()
                artifacts.append(dict(kind='file',name=file['name'],ticket=ticket,capturedEpochMs=acquired))
                peer=self.actor.peer();packet,raw=peer.original(self.source.run,source_ticket)
                need(raw is not None and packet['exists'] is True and packet['retired'] is False)
                file=self.files.write(source_ticket,'peer',source_ticket,raw,packet)
                artifacts.append(dict(kind='audio',name=file['name'],ticket=ticket,capturedEpochMs=packet['capturedEpochMs']))
            value=self.primary.observe(after_sequence)
            for row in artifacts:row['sequence']=value['sequence']
            value=deepcopy(value);value['artifacts']=artifacts
            return result('feature.audio.observe',value)
        except BaseException as error:self.poison(error);raise

    def read_artifact(self,name):return self.files.read(name)
