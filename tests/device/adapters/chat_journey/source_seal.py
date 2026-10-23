"""Warm fully consumed original Chat source seals, without cold adoption."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import ExitStack
from copy import deepcopy,copy
import math

from adapters.chat_journey.cleanup_witness import ChatCleanupWitness
from adapters.chat_journey.observation import ChatObservationOwner
from adapters.chat_journey.source_chunks import digest,ChatSourceChunks
from adapters.chat_journey.evidence_archive import stamp,private
from adapters.native_feature_observation import need,fresh,number
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_journey.history import same

VERSION=1


class ChatSourceSeal:
    """Freeze the exact warm operation objects before taking their originals.

    A sealed-looking physical row does not prove its final checks returned.
    Only this actual warm owner's returned receipt can qualify completion.
    Unknown/cold seals remain retained, with no read/publication replay.
    """
    def __init__(self,owner,store):
        need(type(owner) in (ChatObservationOwner,ChatCleanupWitness) and type(store) is PrivateFeatureState)
        self.owner=owner;self.observation=owner.observation if type(owner) is ChatCleanupWitness else owner
        need(self.observation.stage=='cleanup' and store.path.parent==self.observation.store.path.parent
            and store.read() is None)
        self.publisher=owner if type(owner) is ChatCleanupWitness else None
        self.owners=tuple(value for value in (self.publisher,self.observation,self.observation.samples,
            self.observation.samples.script_source) if value is not None)
        need(len({value.store.path for value in self.owners}|{store.path})==len(self.owners)+1)
        self.store,self.previous,self.failed,self.completed=store,None,False,False
        self.seal_stamp=None
        self.scope=dict(chatSourceSealVersion=VERSION,runId=self.observation.source.run,role=self.observation.samples.role,
            binding=deepcopy(self.observation.samples.binding),peerBinding=deepcopy(self.observation.samples.peer_binding),
            kind='cleanup-witness' if self.publisher is not None else 'cleanup-observation',journal=owner.store.path.name)
        self.empty_history=ChatSourceChunks(store,self.scope);self.empty_history.inventory(0)
        self.read_guard=self.live
        need(all(value is None or value._freeze_guard is None for value in (self.observation,self.publisher)))
        for value in (self.observation,self.publisher):
            if value is not None:value.bind_freeze(self.read_guard)

    def live(self):
        return not self.failed and not self.completed and self.previous is None and self.store.read() is None

    def originals(self,*,control=True):
        result=[]
        if self.publisher is not None and control:self.publisher.control()
        for owner in self.owners:
            info=owner.store.path.lstat();private(info);original_stamp=stamp(info)
            root=owner.store.read();need(root is not None and same(root,owner.previous) and root['phase']=='ready'
                and stamp(owner.store.path.lstat())==original_stamp)
            history=owner.history;need(type(history) is ChatSourceChunks)
            admitted=tuple(history.identities);admitted_bytes=history.raw_bytes
            history.verify()
            # load() restores reader identities. It must never replace this
            # live owner's already-admitted originals, including on failure.
            reader=copy(history);frames=reader.load(root['chunks'])
            need(tuple(reader.identities)==admitted and reader.raw_bytes==admitted_bytes
                and tuple(history.identities)==admitted and history.raw_bytes==admitted_bytes)
            history.verify()
            cached=owner.rows if hasattr(owner,'rows') else owner.frames
            need(same(frames,cached) and frames)
            if hasattr(owner,'transactions'):need(same(owner.transactions,{frame['ticket']:frame for frame in frames}))
            result.append(dict(journal=owner.store.path.name,sha256=digest(root),chunkCount=len(root['chunks']),
                stamp=original_stamp,chunkManifestSha256=digest(root['chunks']),framesSha256=digest(frames),
                chunkStampsSha256=digest([list(value) for value in owner.history.identities])))
            need(stamp(owner.store.path.lstat())==original_stamp)
        return result

    def write(self,value):
        need(same(self.store.read(),self.previous));self.store.write(value,self.previous)
        need(same(self.store.read(),value));self.previous=deepcopy(value)

    def run(self):
        need(not self.failed and not self.completed and self.previous is None)
        try:
            with ExitStack() as held:
                for lock in sorted(self.observation.samples.locks,key=lambda value:str(value.path)):held.enter_context(lock.held())
                need(self.observation.rows and not self.observation.failed
                    and (self.publisher is None or self.publisher.rows and not self.publisher.failed))
                started=self.observation.now();originals=self.originals();row=self.observation.rows[-1]
                self.observation.final(row,started)
                self.write({**self.scope,'phase':'sealing','originals':originals})
                need(same(self.originals(),originals));self.observation.final(row,started)
                self.write({**self.previous,'phase':'sealed'})
                info=self.store.path.lstat();private(info);self.seal_stamp=stamp(info)
                value=deepcopy(self.previous);need(same(self.originals(),originals))
                need(stamp(self.store.path.lstat())==self.seal_stamp)
                self.observation.final(row,started)
                role=self.observation.samples;frame=role.frames[-1]
                oldest=min(frame[key]['capturedEpochMs'] for key in ('primary','view','lifecycle'))
                oldest=min(oldest,frame['compiledChat']['before']['requestedEpochMs'])
                clocks=[(reader.clock_ms,epoch) for reader,epoch in ((role.primary,oldest),
                    (role.peer,frame['peer']['capturedEpochMs']),*role._extra_clocks(frame))]
                clocks.append((self.observation.source.epoch_ms,self.observation.source.previous['capturedEpochMs']))
            # Source-lock exit also performs real metadata checks. Their cost
            # cannot escape final freshness, and failed lock exit is never a
            # completed seal. These are the same original clocks, with no new
            # source acquisition or old-PID guard/lock reentry.
            measured=[]
            for clock,oldest in clocks:
                before=self.observation.now();epoch=clock();fresh(oldest,epoch);measured.append((before,epoch,oldest))
            ended=self.observation.now()
            need(number(ended,started,started+1.5) and all(epoch-oldest+math.ceil((ended-before)*1000)<=1500
                for before,epoch,oldest in measured))
            self.completed=True;return value
        except Exception:self.failed=True;raise

    def receipt(self,value):
        """Historical closure only; never refresh or adopt native target facts."""
        need(self.completed and not self.failed and self.previous is not None and self.previous['phase']=='sealed'
            and same(value,self.previous) and same(self.store.read(),value)
            and stamp(self.store.path.lstat())==self.seal_stamp)
        # This actual warm receipt was received AFTER final clocks. Frozen
        # physical originals can now be checked under the parent's distinct
        # lock objects, without reacquiring the actor's same-inode OS locks or
        # touching native old-PID guards after process finalization.
        need(same(self.originals(control=False),value['originals']));self.empty_history.inventory(0)
        need(stamp(self.store.path.lstat())==self.seal_stamp)
        return deepcopy(value)
