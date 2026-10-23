"""Independent original GetAll readers; no bake/model/render verdicts."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import ExitStack
from copy import deepcopy
import math
from adapters.chat_journey.source_chunks import json_digest
from adapters.native_feature_observation import fresh,integer,need,number
from adapters.pico4.assets_source import PicoAssetsSource
from adapters.script_journey.history import canonical,same,MAX_RAW,MAX_FRAMES
from adapters.script_journey.lock import ScriptSourceLock
from feature_journeys.phase_fixture import PhaseFixtureReader

VERSION=1


class IndependentAssetsMappings:
    def __init__(self,primary,independent,primary_lock,independent_lock,phase):
        need(all(isinstance(source,PicoAssetsSource) and not source.is_download and not source.is_resolve
                and source.intent is None and not source.history and source.pending is None for source in (primary,independent))
            and primary is not independent and primary.pid!=independent.pid
            and all(isinstance(lock,ScriptSourceLock) for lock in (primary_lock,independent_lock))
            and primary_lock is not independent_lock and primary_lock.path!=independent_lock.path
            and isinstance(phase,PhaseFixtureReader) and phase.area=='assets')
        self.sources=(primary,independent);self.locks=tuple(sorted((primary_lock,independent_lock),key=lambda lock:str(lock.path)))
        self.phase=phase;self.history=[];self.seal=canonical([]);self.source_seals=(canonical([]),canonical([]))
        self._sealed_history,self._sealed_sources=self.seal,self.source_seals
    def capture(self):
        with ExitStack() as stack:
            for lock in self.locks:stack.enter_context(lock.held())
            json_digest(self.history)
            need(self.seal is self._sealed_history and self.source_seals is self._sealed_sources
                and canonical(self.history)==self.seal and len(self.history)<64)
            for source,sealed in zip(self.sources,self.source_seals):
                json_digest(source.history)
                need(canonical(source.history)==sealed and source.pending is None and source.intent is None and source.guard() is not False)
            phase_started=self.phase.monotonic();phase_epoch=self.phase.epoch_ms();before=self.phase.read()
            anchors=[];packets=[]
            for source in self.sources:
                started=source.monotonic();requested=source.clock_ms();need(number(started,0,1e15) and integer(requested,1))
                packet=source.read(self.phase.run);need(packet['requestedEpochMs']>=requested and packet['capturedEpochMs']>=before['afterEpochMs'])
                anchors.append((started,requested));packets.append(packet)
            left,right=(packet['source'] for packet in packets)
            need(all(left[key]==right[key] for key in ('domainId','assetServerId'))
                and all(left[key]!=right[key] for key in ('sessionId','clientInstance','nodeListInstance','assetServerInstance'))
                and packets[0]['instance']!=packets[1]['instance'] and packets[0]['processId']!=packets[1]['processId']
                and same(left['mappings'],right['mappings']))
            after=self.phase.read(before['status']);need(same(before['status']['activations'],after['status']['activations']) and before['ticket']==after['ticket'])
            row=dict(assetsIndependentMappingsVersion=VERSION,runId=self.phase.run,ticket=before['ticket'],
                phaseBefore=deepcopy(before['status']),phaseAfter=deepcopy(after['status']),
                primary=deepcopy(self.sources[0].history[-1]),independent=deepcopy(self.sources[1].history[-1]))
            result=deepcopy(row);history=deepcopy(self.history)+[row]
            # Current raw originals are counted once in each dedicated source,
            # and again wherever the returned paired transcript retains them.
            counts=4*len(history)+sum(len(source.history) for source in self.sources)
            size=len(canonical(history))+sum(len(canonical(source.history)) for source in self.sources)
            need(counts<=MAX_FRAMES and size<=MAX_RAW)
            seal=canonical(history);source_seals=tuple(canonical(source.history) for source in self.sources)
            for source,packet,(started,requested) in zip(self.sources,packets,anchors):
                need(source.guard() is not False);epoch=source.clock_ms();ended=source.monotonic()
                need(number(ended,started,started+1.5) and integer(epoch,requested))
                fresh(packet['capturedEpochMs'],max(epoch,requested+math.ceil((ended-started)*1000)))
            ended=self.phase.monotonic();epoch=self.phase.epoch_ms()
            need(number(ended,phase_started,phase_started+1.5) and number(epoch,phase_epoch,phase_epoch+1500))
            # No result copy, digest or append follows the final original clocks.
            self.history,self.seal,self.source_seals=history,seal,source_seals
            self._sealed_history,self._sealed_sources=seal,source_seals
            return result
