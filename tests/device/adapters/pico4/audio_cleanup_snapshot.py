"""Cold canonical Audio reads with original conservative decoder SUM by default.

Fresh G1 readers require the actual new-bound cleanup owner. No historical
adoption, Actor credential, acoustic, quiet or whole-cleanup verdict is granted.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy

from adapters.chat_journey.source_chunks import json_digest
from adapters.native_feature_observation import need
from adapters.pico4.audio_cleanup_io import PicoAudioCleanupIO1
from adapters.pico4.audio_cleanup_profile import AudioCleanupBudget1
from adapters.pico4.audio_settings_source import CLOCKS
from adapters.pico4.lifecycle_namespace_bill import canonical_size
from adapters.recorded_preview_history import measured_state
from adapters import audio_preview_lifetime as preview_lifetime
from adapters.script_journey.history import canonical


class AudioCleanupSnapshot1:
    def __init__(self,budget,io,*,epoch='old',role='primary',binding=None):
        need(type(epoch) is str and type(role) is str
             and type(budget) is AudioCleanupBudget1 and type(io) is PicoAudioCleanupIO1
             and budget.restart_io is io and io.budget is budget
             and budget.sampler_metadata==65536 and not budget.failed
             and ((epoch=='old' and role=='primary' and binding is None and budget.sampler is self and not budget.old_frozen)
                  or epoch=='new' and role in ('primary','actor') and budget.old_frozen
                  and any(self is item for item in budget.new_samplers)
                  and binding==budget.cleanup_owner.state['newBinding']))
        self.budget,self.io=budget,io;self.original=(budget,io)
        self.epoch,self.role=epoch,role
        self._role_key=(epoch,role)
        self.binding=deepcopy(budget.value['binding'] if epoch=='old' else binding);self.binding_sha=json_digest(self.binding)
        self.failed=False;self.failure=None;self.reading=False;self.sequence=0
        self.native=self.presence=self.settings=self.pages=None
        self.partial_output=self.last_output=None
        self.seal=None
        self.guard()
        io.begin_query(self.epoch,self.role)
        self.native,self.presence,self.settings,self.pages=io.sources(
            self.binding['processIdentity'],self.binding['sessionId'])
        io.end_query()

    def guard(self):
        need(type(self.original) is tuple and len(self.original)==2
             and type(self.original[0]) is AudioCleanupBudget1 and type(self.original[1]) is PicoAudioCleanupIO1
             and type(self.failed) is bool and type(self.reading) is bool
             and type(self.sequence) is int and 0<=self.sequence<=512)
        budget,io=self.original
        need(self.budget is budget and self.io is io
             and budget.restart_io is io and io.budget is budget
             and not self.failed and not budget.failed
             and json_digest(self.binding)==self.binding_sha
             and type(self.epoch) is str and type(self.role) is str
             and (self.epoch,self.role)==self._role_key
             and ((self.epoch=='old' and self.role=='primary' and budget.sampler is self
                   and not budget.old_frozen and self.binding==budget.value['binding'])
                  or self.epoch=='new' and self.role in ('primary','actor') and budget.old_frozen
                  and any(self is item for item in budget.new_samplers)
                  and self.binding==budget.cleanup_owner.state['newBinding']))
        budget.guard()
        if self.epoch=='new':budget.cleanup_owner.guard()
        if self.seal is not None:
            need(self.seal is budget.decode_seal if self.epoch=='old' else
                any(self.seal is item for item in budget.new_seals));self.seal.require()

    def _sample_local(self,start):
        # All three decoded return graphs are confined to this exact method.
        # Existing readers retain their own documented history/previous/raw
        # fields. Work stays charged until an optional sealed outer handback.
        native=self.native.read(self.native.sequence,require_recorded_history=True)
        settings=self.settings.capture(self.budget.value['runId'])
        pages=self.pages.capture()
        need(settings['source']['native']['muted']==native['audio']['muted']
             and settings['source']['native']['previewCycle']==native['audio']['recordedVoice']['cycle'])
        state=measured_state(native);state['open']=bool(pages['picoAudioPages']['current'])
        key=dict(state=state,instance=native['instance'],lifecycle=native['lifecycle'],
            voice=native['audio']['recordedVoice'],settings=settings['source'],pages=pages['picoAudioPages']['originals'])
        digest=json_digest(key)
        clocks=[native['requestedEpochMs'],native['capturedEpochMs'],
            *(settings['source'][name] for name in CLOCKS),pages['picoAudioPages']['capturedEpochMs']]
        body=dict(picoAudioCleanupSnapshotVersion=1 if self.epoch=='old' else 2,epoch=self.epoch,role=self.role,sequence=self.sequence+1,
            processIdentity=self.binding['processIdentity'],nativeInstance=native['instance'],
            lifecycle=native['lifecycle'],state=state,originalStateSha256=digest,
            originalClocks=clocks,sourceQueryAnchor=list(self.io.query),
            rawReferences=self.io.references[start:])
        if self.epoch=='new':
            baseline=self.budget.cleanup_owner.state['baseline']
            source=settings['source'];original=baseline['settings']
            stable=dict(state=state,voice=native['audio']['recordedVoice'],instance=native['instance'],
                lifecycle=native['lifecycle'],properties=source['properties'],native=source['native'],
                gains=source['mixerGains'],peak=source['inputPeakValuesEnabled'],
                lifetime=source.get('previewLifetime'),pages=pages['picoAudioPages']['originals'])
            restored=(state==baseline['actual'] and source['properties']==original['properties']
                and source['native']==original['native'] and source['mixerGains']==original['mixerGains']
                and source['inputPeakValuesEnabled']==original['inputPeakValuesEnabled']
                and preview_lifetime.restored(source['previewLifetime'],original['previewLifetime'])
                and pages['picoAudioPages']['originals']==baseline['pages'])
            body.update(quietStateSha256=json_digest(stable),baselineRestored=restored)
        canonical_size(body,16384)
        encoded=canonical(body)
        # Only immutable canonical bytes cross the local method's return.
        # Any exception keeps this frame/graphs in the original failure holder.
        self.partial_output=encoded
        return encoded

    def sample(self):
        try:
            self.guard();need(not self.reading and self.io.query is None)
            self.reading=True;start=len(self.io.references)
            if self.seal is not None and self.seal.handback:self.seal.begin()
            self.io.begin_query(self.epoch,self.role)
            encoded=self._sample_local(start)
            # The local decoded graph frame is gone before final freshness.
            # Reader-held roots and all active SUM charges remain fully owned
            # through the original final guards and optional sealed handback.
            if self.seal is not None and self.seal.handback:self.seal.stage(encoded)
            self.guard()
            # A closed handback keeps ALL old/new decoder SUM and bounded
            # output work charged. Its final global bill follows the original
            # candidate/query guard below, before any handback or return.
            # Default conservative callers retain their original early bill.
            if self.seal is None or not self.seal.handback:self.budget.check_global(self.io)
            self.io.end_query()
            if self.seal is not None and self.seal.handback:
                self.budget.check_global(self.io)
                self.seal.commit(encoded)
            self.last_output=encoded;self.partial_output=None;self.sequence+=1
            self.reading=False
            return encoded
        except BaseException as error:
            self.failed=True;self.budget.failed=True
            if self.failure is None:self.failure=(error,error.__traceback__)
            raise

    def retained_projection_bytes(self):
        # Read-only measurement of actual documented retained roots. It is
        # neither permission to clear SUM nor a complete Python heap bound.
        need(type(self.original) is tuple and len(self.original)==2
             and self.original[0] is self.budget and self.original[1] is self.io
             and (self.budget.sampler is self or any(self is item for item in self.budget.new_samplers)))
        graph=dict(native=dict(lifecycle=self.native.lifecycle,voice=self.native.voice_history,
            animation=self.native.animation_history,account=self.native.account_history),
            settings=dict(previous=self.settings.previous,raw=self.settings.last_raw),
            pages=dict(previous=self.pages.previous,raw=self.pages.last_raw))
        return canonical_size(graph,16*1024*1024)+sum(len(v) for v in
            (self.partial_output,self.last_output) if type(v) is bytes)
