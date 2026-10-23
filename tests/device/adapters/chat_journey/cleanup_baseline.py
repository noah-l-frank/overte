"""Consume the actual common Chat cleanup baseline before sealing its sources."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import ExitStack
from copy import deepcopy,copy
import math

from adapters.chat_journey.cleanup_witness import ChatCleanupWitness
from adapters.chat_journey.observation import ChatObservationOwner
from adapters.chat_journey.source_seal import ChatSourceSeal
from adapters.chat_journey.source_chunks import ChatSourceChunks,digest
from adapters.native_feature_observation import integer,need,fresh,number
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_journey.history import same
from feature_journeys.engine import Journey
from feature_journeys.scenarios import SCENARIOS

VERSION=1


class ChatCleanupBaseline:
    """Warm baseline consumption only; no restart, IPC, retirement or capability.

    Independent publication precedes its separately received journal read.
    The original common checker decides the three-second baseline. Expected
    facts never enter a source request or publisher payload.
    """
    def __init__(self,primary,actor,seals,store,*,guard,sleep):
        need(type(primary) is ChatObservationOwner and primary.stage=='cleanup' and primary.samples.role=='primary'
            and type(actor) is ChatCleanupWitness and actor.observation.stage=='cleanup'
            and primary.source.run==actor.observation.source.run
            and primary.source.fixture_url==actor.observation.source.fixture_url
            and primary.source.client is not actor.observation.source.client
            and same(primary.samples.binding,actor.observation.samples.binding)
            and same(primary.samples.peer_binding,actor.observation.samples.peer_binding)
            and primary.samples.script_source is not actor.observation.samples.script_source
            and tuple(lock.path for lock in primary.samples.locks)==tuple(lock.path for lock in actor.observation.samples.locks)
            and not primary.rows and not actor.rows and not actor.observation.rows
            and type(seals) is tuple and len(seals)==2 and all(type(value) is ChatSourceSeal for value in seals)
            and seals[0].owner is primary and seals[1].owner is actor and all(value.live() for value in seals)
            and type(store) is PrivateFeatureState and store.read() is None and callable(guard) and callable(sleep))
        self.primary,self.actor,self.seals,self.store=primary,actor,seals,store
        paths=[store.path,primary.store.path,actor.store.path,*[value.store.path for value in seals]]
        need(len(set(paths))==len(paths) and all(path.parent==store.path.parent for path in paths))
        self.guard,self.sleep=guard,sleep;self.previous=None;self.failed=self.started=self.completed=False
        self.rows=[];self.latest_started=None;self.journey=None;self.seal_receipts=None;self.root_stamp=None
        self.scope=dict(chatCleanupBaselineVersion=VERSION,runId=primary.source.run,fixtureUrl=primary.source.fixture_url,
            binding=deepcopy(primary.samples.binding),peerBinding=deepcopy(primary.samples.peer_binding),
            primaryObservation=primary.store.path.name,actorPublisher=actor.store.path.name,
            sourceSeals=[value.store.path.name for value in seals])
        self.history=ChatSourceChunks(store,self.scope);self.history.inventory(0)

    def held(self,observation):
        held=ExitStack()
        try:
            for lock in sorted(observation.samples.locks,key=lambda value:str(value.path)):held.enter_context(lock.held())
            return held
        except BaseException:held.close();raise

    def control(self):
        need(not self.failed and self.guard() is not False and same(self.store.read(),self.previous));self.history.verify()

    def save(self,stage,**changes):
        with self.held(self.primary):
            self.control();value={**(self.previous or {**self.scope,'phase':'reading','chunks':[]}),
                **deepcopy(changes),'stage':stage}
            self.store.write(value,self.previous);need(same(self.store.read(),value));self.previous=deepcopy(value)
            self.control()

    def clocks(self,observation):
        role=observation.samples;frame=role.frames[-1]
        oldest=min(frame[key]['capturedEpochMs'] for key in ('primary','view','lifecycle'))
        oldest=min(oldest,frame['compiledChat']['before']['requestedEpochMs'])
        return [(reader.clock_ms,epoch) for reader,epoch in ((role.primary,oldest),
            (role.peer,frame['peer']['capturedEpochMs']),*role._extra_clocks(frame))]+[
                (observation.source.epoch_ms,observation.source.previous['capturedEpochMs'])]

    def fresh_pair(self):
        need(self.latest_started is not None);clocks=[]
        # Independent roles may have different lock objects at the same OS
        # inodes. Release one complete role before taking the other; never nest.
        for observation in (self.actor.observation,self.primary):
            with self.held(observation):
                observation.final(observation.rows[-1],self.latest_started);clocks.extend(self.clocks(observation))
        measured=[]
        for clock,oldest in clocks:
            before=self.primary.now();epoch=clock();fresh(oldest,epoch);measured.append((before,epoch,oldest))
        ended=self.primary.now()
        need(number(ended,self.latest_started,self.latest_started+1.5)
            and all(epoch-oldest+math.ceil((ended-before)*1000)<=1500 for before,epoch,oldest in measured))

    def invoke(self,operation,fields):
        need(self.started and not self.completed and operation=='feature.chat.observe'
            and fields['afterSequence']==len(self.primary.rows));self.control()
        self.latest_started=self.primary.now();self.actor.publish()
        value=deepcopy(self.primary.read(fields['afterSequence']));self.fresh_pair();return value

    def received(self):
        self.control();source=self.actor.observation.source
        value=deepcopy(source.client.request('/runs/'+self.scope['runId']))
        need(type(value) is dict and type(value.get('entries')) is list)
        ticket=self.actor.rows[-1]['payload']['ticket']
        rows=[row for row in value['entries'] if row.get('ticket')==ticket]
        need(len(rows)==len(self.actor.rows))
        for received,published in zip(rows,self.actor.rows):
            need(all(key in received and same(received[key],field) for key,field in published['payload'].items()))
        self.fresh_pair();return value

    def run(self,after_epoch):
        need(not self.failed and not self.started and integer(after_epoch,1));self.started=True
        try:
            self.save('measuring')
            with self.held(self.primary):
                _authority,phase=self.primary.current();activation=phase['activations'][-1]
                need(after_epoch>=math.ceil(activation['activatedEpochMs']))
                ticket=activation['ticket'];barrier=max(after_epoch,self.primary.source.epoch_ms())
            def no_input(*_args,**_kwargs):need(False)
            self.journey=Journey('chat',self.scope['runId'],self.scope['fixtureUrl'],invoke=self.invoke,
                witness=self.received,activate=no_input,read_artifact=no_input,image_policy={},
                continuity=lambda *_args:self.control(),monotonic=self.primary.monotonic,
                epoch_ms=self.primary.source.epoch_ms,sleep=self.sleep,report=lambda _value:None)
            self.journey.required_lifecycle=deepcopy(self.actor.active_original['lifecycle']['lifecycle'])
            self.journey.wait('cleanup-restored-baseline',ticket,barrier,deepcopy(SCENARIOS['chat']['baseline']),['peer'],duration=3.0)
            for index,sample in enumerate(self.journey.samples):
                source=self.primary.rows[index]
                need(sample['sequence']==source['sequence'] and sample['capturedEpochMs']==source['sample']['capturedEpochMs']
                    and same(sample['state'],source['sample']['state']) and same(sample['resources'],source['sample']['resources'])
                    and sample['witness'] is not None)
                published=self.actor.rows[index]
                need(all(same(sample['witness'][key],field) for key,field in published['payload'].items()))
                row=dict(common=deepcopy(sample),primaryObservationSha256=digest(source),actorPublicationSha256=digest(published))
                with self.held(self.primary):
                    chunks=self.history.append(row,self.previous['chunks'])
                    self.save('measured',chunks=chunks);self.rows.append(row)
            self.fresh_pair();self.save('sealing-actor');actor=self.seals[1].run()
            self.save('sealing-primary');primary=self.seals[0].run()
            self.seal_receipts=(primary,actor)
            receipts=[seal.receipt(value) for seal,value in zip(self.seals,self.seal_receipts)]
            self.save('complete',phase='ready',common=deepcopy(self.journey.phases[-1]),
                sealSha256=[digest(value) for value in receipts])
            from adapters.chat_journey.evidence_archive import stamp,private
            info=self.store.path.lstat();private(info);self.root_stamp=stamp(info)
            value=deepcopy(self.previous);self.control();self.fresh_pair();self.completed=True;return value
        except Exception:
            self.failed=True
            # Quarantine the exact already-bound warm sources. No new owner
            # can acquire their existing journals or replace these callbacks.
            for seal in self.seals:seal.failed=True
            raise

    def receipt(self,value):
        from adapters.chat_journey.evidence_archive import stamp
        need(self.completed and not self.failed and same(value,self.previous) and same(self.store.read(),value)
            and stamp(self.store.path.lstat())==self.root_stamp)
        admitted=tuple(self.history.identities);admitted_bytes=self.history.raw_bytes
        self.history.verify()
        reader=copy(self.history);frames=reader.load(value['chunks'])
        need(tuple(reader.identities)==admitted and reader.raw_bytes==admitted_bytes
            and tuple(self.history.identities)==admitted and self.history.raw_bytes==admitted_bytes
            and same(frames,self.rows));self.history.verify()
        for seal,original in zip(self.seals,self.seal_receipts):seal.receipt(original)
        need(same(self.store.read(),value) and stamp(self.store.path.lstat())==self.root_stamp)
        return deepcopy(value)
