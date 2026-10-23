"""Original common Browser cleanup consumption, never a whole-run shortcut."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import copy,deepcopy
import hashlib
import math

from adapters.chat_journey.source_chunks import ChatSourceChunks,json_digest
from adapters.native_feature_observation import exact,fresh,need,number
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.observer_return import state,parent_node
from adapters.script_journey.history import MAX_RAW,canonical,same
from feature_journeys.contract import json_document
from feature_journeys.engine import Journey
from feature_journeys.scenarios import VERSION as CONTRACT_VERSION

VERSION=1


class PicoBrowserCleanupConsumption:
    """The actual callback's immutable bytes and complete original samples."""
    def __init__(self,primary):
        from adapters.pico4.tablet_web_feature import PicoTabletWebFeature
        need(type(primary) is PicoTabletWebFeature and primary.role=='primary')
        self.primary=primary;self.journey=None;self.callback=self.consume
        self.store=PrivateFeatureState(primary.store.path.with_name('pico-tablet-web-cleanup-consumption.json'))
        need(self.store.read() is None);ChatSourceChunks(self.store,{}).inventory(0)
        self.parent=parent_node(self.store);self.scope=None;self.chunks=None;self.previous=None
        self.raw=self.root_stamp=self.sealed=None;self.started=self.complete=self.failed=False

    def attach(self,journey):
        need(type(journey) is Journey and journey.area=='tablet-web' and journey.run==self.primary.run
            and journey.url==self.primary.fixture_url and journey.after_cleanup_baseline is self.callback
            and self.journey is None and not self.started and not journey.cleanup_hook_started)
        self.journey=journey

    def control(self):
        need(not self.failed and parent_node(self.store)==self.parent and same(self.store.read(),self.previous))
        if self.root_stamp is not None:need(state(self.store)[2]==self.root_stamp)
        if self.chunks is not None:self.chunks.verify()
        if self.sealed is not None:
            json_digest(dict(scope=self.scope,root=self.previous,stamp=self.root_stamp))
            need(self.raw is self._sealed_raw and type(self.raw) is bytes
                and canonical(dict(scope=self.scope,root=self.previous,stamp=self.root_stamp))==self.sealed)

    def save(self,phase,chunks,header):
        self.control();value={**self.scope,'phase':phase,'chunks':deepcopy(chunks),'header':deepcopy(header),
            'rawSha256':hashlib.sha256(self.raw).hexdigest(),'rawBytes':len(self.raw)}
        self.store.write(value,self.previous);observed,_raw,self.root_stamp=state(self.store)
        need(same(observed,value));self.previous=deepcopy(value);self.control()

    def final_clocks(self):
        _phase,started,epoch_started,epochs=self.primary.sample_fence
        measured=self.primary.monotonic();epoch=self.primary.source.epoch_ms();ended=self.primary.monotonic()
        need(number(measured,started,started+10) and number(ended,measured,started+10))
        for captured in epochs:
            fresh(captured,epoch)
            need(max(epoch-captured,epoch_started-captured+math.ceil((ended-started)*1000),
                epoch-captured+math.ceil((ended-measured)*1000))<=1500)

    def consume(self,raw):
        need(not self.started and not self.failed);self.started=True
        try:
            j=self.journey;f=self.primary
            need(j is not None and j.cleanup_hook_started and j.cleanup_consumption is raw
                and type(raw) is bytes and 0<len(raw)<=MAX_RAW)
            value=json_document(raw);json_digest(value)
            exact(value,{'cleanupConsumptionVersion','contractVersion','area','runId','fixtureUrl','ticket',
                'actionBarrierEpochMs','sequenceSucceeded','phase','samples','finalSequence'})
            need(type(value['cleanupConsumptionVersion']) is int and value['cleanupConsumptionVersion']==1
                and type(value['contractVersion']) is int and value['contractVersion']==CONTRACT_VERSION
                and value['area']=='tablet-web' and value['runId']==f.run and value['fixtureUrl']==f.fixture_url
                and type(value['sequenceSucceeded']) is bool and value['sequenceSucceeded'] is j._cleanup_sequence_succeeded
                and value['samples'] and same(value['phase'],j.phases[-1])
                and value['phase']['phase']=='cleanup-restored-baseline' and value['phase']['stableSeconds']>=3
                and same(value['samples'],j.samples[-len(value['samples']):]) and value['finalSequence']==j.sequence)
            with f.lock.held():
                owner=f.owner();role=f.role_state();history=f.source_history(owner);history.matches(role)
                need(owner['phase']=='cleaned' and role['sequence']==value['finalSequence'])
                original={row['sequence']:row['original'] for row in history.rows if row['event']=='sample'}
                if value['sequenceSucceeded']:
                    from feature_journeys.scenarios import SCENARIOS,expand
                    from feature_journeys.fixtures import context as fixture_context
                    steps=SCENARIOS['tablet-web']['steps'];activations=role['phase']['activations']
                    need(len(j.phases)==len(activations)==len(steps)+2
                        and activations[0]['stimulus']==dict(verb='baseline',inputs={})
                        and activations[-1]['stimulus']==dict(verb='cleanup',inputs={})
                        and all(row['stimulus']==dict(verb=step['verb'],inputs=expand(step['inputs'],fixture_context(f.run)))
                            for row,step in zip(activations[1:-1],steps)))
                for sample in j.samples if value['sequenceSucceeded'] else value['samples']:
                    saved=original[sample['sequence']];measured=saved['sample']
                    need(all(same(sample[key],measured[key]) for key in ('sequence','capturedEpochMs','state','resources','lifecycle'))
                        and saved['phaseBefore']['activations'][-1]['ticket']==sample['ticket'])
                need(all(sample['ticket']==value['ticket'] and sample['actionBarrierEpochMs']==value['actionBarrierEpochMs']
                    for sample in value['samples']))
                self.raw=raw
                self.scope=dict(picoBrowserCleanupConsumptionVersion=VERSION,runId=f.run,fixtureUrl=f.fixture_url,
                    binding=deepcopy(owner['binding']),ownerToken=owner['ownerToken'])
                self.chunks=ChatSourceChunks(self.store,self.scope);self.chunks.inventory(0)
                header={key:deepcopy(field) for key,field in value.items() if key!='samples'}
                self.save('reading',[],header)
                for sample in value['samples']:
                    chunks=self.chunks.append(sample,self.previous['chunks']);self.save('reading',chunks,header)
                self.save('ready',self.previous['chunks'],header)
                f.completion_fence(owner,originals=lambda:f.sample_originals(role,history))
                self._sealed_raw=self.raw;self.sealed=canonical(dict(scope=self.scope,root=self.previous,stamp=self.root_stamp));self.control()
            # Actual source-lock exit and its physical recheck precede the
            # final clocks of the same last original product sample.
            self.control();self.final_clocks();self.complete=True
        except BaseException:
            self.failed=True
            raise NativeUIError('Original common Browser cleanup consumption is unresolved; sources remain') from None

    def receipt(self):
        need(self.complete and not self.failed and self.sealed is not None)
        try:
            self.control();reader=copy(self.chunks);identities=tuple(self.chunks.identities);raw_bytes=self.chunks.raw_bytes
            rows=reader.load(self.previous['chunks'])
            need(tuple(reader.identities)==identities and reader.raw_bytes==raw_bytes
                and tuple(self.chunks.identities)==identities and self.chunks.raw_bytes==raw_bytes)
            need(canonical(dict(**self.previous['header'],samples=rows))==self.raw)
            result=deepcopy(self.previous);self.control();return result
        except BaseException:self.failed=True;raise
