"""Cold, readonly bundle transport using the original PC Actor raw bank."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import uuid
from adapters.native_feature_observation import exact,fresh,integer,need,number
from adapters.pico4.audio_observation_bundle import ACTION,LIMIT,NATIVE_DECLARATION,validate,accept
from feature_journeys.contract import json_document

VERSION=1
# Additional carrier, command ledger and current parse/copy overlap declaration.
# Retained frame/literal bytes remain in the Actor's ordinary aggregate bill.
HOST_DECLARATION=2*1024*1024
DECLARATION=NATIVE_DECLARATION+HOST_DECLARATION


class AudioBundleTransport1:
    """No IO at construction; the actor charges DECLARATION before first IO."""
    def __init__(self,send,read):
        need(callable(send) and callable(read))
        self.send,self.read=send,read;self._send,self._read=send,read
        self.actor=None;self.issued={};self.failed=False;self.failure=None
        self.last_raw=None;self.last_command=None;self.last_reference=None

    def bind(self,actor):
        from adapters.pico4.audio_pc_actor import PicoAudioPCActor
        need(type(actor) is PicoAudioPCActor and self.actor is None and not self.failed and not self.issued
            and actor.observation_bundle is self and actor.bundle_declaration==DECLARATION)
        self.actor=actor

    def guard(self,*,acquiring=False):
        actor=self.actor
        need(not self.failed and actor is not None and actor.observation_bundle is self
            and actor.bundle_declaration==DECLARATION and self.send is self._send and self.read is self._read
            and type(self.issued) is dict and len(self.issued)<=512)
        actor.recipe.lock.assert_held()
        if acquiring:actor.lock.assert_held()

    def capture(self,previous):
        actor=self.actor
        try:
            self.guard(acquiring=True);need(actor.state['pending'] is not None and len(self.issued)<512)
            started=actor.state['pending']['started'];requested=actor.native.clock_ms()
            need(integer(requested,1) and number(started,0,1e15))
            command=dict(schemaVersion=1,action=ACTION,commandId=uuid.uuid4().hex,runId=actor.recipe.run,
                nativeNonce=uuid.uuid4().hex,settingsNonce=uuid.uuid4().hex)
            need(len({command[k] for k in ('commandId','nativeNonce','settingsNonce')})==3)
            # The ordinary aggregate reserve includes our permanent declaration.
            # It precedes both the first command and every original file getter.
            token=actor.reserve_raw('audio-bundle',command,LIMIT)
            self.issued[command['commandId']]=deepcopy(command);self.last_command=deepcopy(command)
            self.send(command)  # Readonly once-issued request; no normal input.
            for attempt in range(51):
                self.guard(acquiring=True);raw=self.read()
                reference=actor.raws.retain(token,raw)
                self.last_raw,self.last_reference=raw,deepcopy(reference)
                actor._raw('audio-bundle',reference)  # Durable before parsing.
                need(type(raw) is str and len(raw.encode('utf-8'))<=LIMIT)
                value=json_document(raw) if raw else None
                epoch=actor.native.clock_ms();now=actor.monotonic()
                need(number(now,started,1e15) and now-started<1.5)
                if type(value) is dict and value.get('commandId')==command['commandId']:
                    if value.get('status')=='ready':
                        result=validate(raw,command,actor.native.pid,actor.pages.bridge,epoch)
                        accept(previous,result)
                        fresh(result['envelope']['requestedEpochMs'],actor.native.clock_ms())
                        need(0<=actor.monotonic()-started<1.5)
                        return result
                    exact(value,{'picoAudioObservationBundleVersion','commandId','status'})
                    need(type(value['picoAudioObservationBundleVersion']) is int
                        and value['picoAudioObservationBundleVersion']==VERSION and value['status']=='pending')
                need(attempt<50);actor.sleep(.025)
                token=actor.reserve_raw('audio-bundle',dict(commandId=command['commandId'],operation='original-getter'),LIMIT)
            need(False)
        except BaseException as error:
            if self.failure is None:self.failure=(error,error.__traceback__)
            self.failed=True
            if actor is not None:actor.raws.stopped=True
            raise
