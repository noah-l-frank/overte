"""One original independent Chat observer lifetime; never a cold live owner."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import ExitStack
from copy import deepcopy
import uuid
import time
import os
import hashlib

from adapters.chat_journey.evidence_archive import stamp,private
from adapters.chat_journey.source_chunks import ChatSourceChunks,digest
from adapters.chat_journey.owned_peer import OwnedChatPeer
from adapters.chat_journey.observation_cursor import plain
from adapters.native_fd_owner import OriginalDescriptor
from adapters.native_feature_observation import exact,integer,need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.observer_return import ObserverReturnSender,state as return_state
from adapters.pico4.chat_composition import PicoChatWitness,record
from adapters.pico4.chat_host_close import host_identity
from adapters.script_journey.history import same,canonical
from feature_journeys.phase_fixture import PhasePending,PhaseFixtureReader
from feature_journeys.witness import Client

VERSION=2
STOP_VERSION=1
RETURN_FAMILY='pico-chat-cursor-actor'


class PicoChatCursorActor:
    """The actual observer process owns publication, sealing and its handles.

    Its durable result reports its own captured descriptor pairs. Kernel
    absence of this observer process and remote graph consumption are separate
    Parent responsibilities; this writer never asserts them from an ACK.
    """
    def __init__(self,adapter,target,source,peer_config):
        self.adapter,self.target,self.source=adapter,target,source
        self.store=adapter._chat_cursor_actor_store(target)
        self.stop_store=adapter._chat_cursor_actor_stop_store(target)
        self.return_store=adapter._chat_cursor_actor_return_store(target)
        self.consumption_store=adapter._chat_cursor_actor_consumption_store(target)
        need(type(self.store) is PrivateFeatureState and type(self.stop_store) is PrivateFeatureState
            and self.store.path!=self.stop_store.path and self.store.path.parent==self.stop_store.path.parent
            and self.store.read() is None and self.stop_store.read() is None
            and all(type(store) is PrivateFeatureState and store.path.parent==self.store.path.parent
                and store.read() is None for store in (self.return_store,self.consumption_store))
            and len({store.path for store in (self.store,self.stop_store,self.return_store,self.consumption_store)})==4)
        for store in (self.store,self.stop_store,self.return_store,self.consumption_store):
            ChatSourceChunks(store,{}).inventory(0)
        self.return_sender=None;self.return_started=self.parent_consumed=False
        self.failed=self.started=self.closed=False;self.previous=None;self.previous_sha=digest(None);self.root_stamp=None
        self.original=self.publisher=self.seal=None
        self.pairs=();self.pairs_sha=digest([]);self.stop_value=self.stop_stamp=self.stop_raw=self.seal_receipt=None
        parent=record(adapter._chat_composition_store(target).read())
        need(parent['runId']==source.run and parent['fixtureUrl']==source.fixture_url
            and parent['phase']=='prepared' and parent['completedSteps']==0)
        self.scope=dict(picoChatCursorActorVersion=VERSION,instance=uuid.uuid4().hex,
            runId=source.run,fixtureUrl=source.fixture_url,binding=deepcopy(parent['binding']),
            peerBinding=deepcopy(parent['peerBinding']),hostProcessIdentity=host_identity())
        self.scope_sha=digest(self.scope)
        try:
            self.save('acquire-issued')
            self.original=adapter._chat_witness_composition(target,source,peer_config)
            need(type(self.original) is PicoChatWitness and not self.original.publisher.rows
                and type(self.original.peer) is OwnedChatPeer
                and self.original.publisher.previous is None and same(self.original.binding,self.scope['binding'])
                and same(self.original.peer.binding,self.scope['peerBinding']))
            with self.held():
                initial=adapter._chat_observation(target,source,self.original.publisher.initial_samples,stage='initial',witness=True)
                cursor=adapter._chat_observation_cursor(target,initial,witness=True)
                self.publisher=adapter._chat_observation_publisher(target,cursor)
            pairs=[]
            for label,owner in (('peer-directory',self.original.peer.files.fd_owner),
                ('peer-executable',self.original.peer.process.fd_owner)):
                need(type(owner) is OriginalDescriptor and all(owner is not old for old,_row in pairs))
                owner.require(owner.fd)
                pairs.append((owner,dict(label=label,node=list(owner.node),fd=owner.fd,anchor=owner.anchor)))
            self.pairs=tuple(pairs)
            self.pairs_sha=digest([row for _owner,row in self.pairs])
            self.save('publishing',pairs=[deepcopy(row) for _owner,row in self.pairs])
        except BaseException:
            self.quarantine()
            # Acquisition failure never supplies a closure receipt. Retain the
            # warm object/intent until its actual owning process finalizes.
            raise NativeUIError('Original independent Chat actor acquisition is unresolved') from None

    def held(self):
        held=ExitStack()
        try:
            need(self.original is not None)
            for lock in sorted((self.original.lock,self.original.peer.lock),key=lambda value:str(value.path)):
                held.enter_context(lock.held())
            return held
        except BaseException:held.close();raise

    def quarantine(self):
        self.failed=True
        if self.publisher is not None:self.publisher.failed=True
        if self.seal is not None:self.seal.failed=True

    def save(self,phase,**values):
        plain(self.previous);need(digest(self.previous)==self.previous_sha)
        need(not self.failed and digest(self.scope)==self.scope_sha and host_identity()==self.scope['hostProcessIdentity']
            and same(self.store.read(),self.previous)
            and (self.root_stamp is None or stamp(self.store.path.lstat())==self.root_stamp)
            and digest([row for _owner,row in self.pairs])==self.pairs_sha)
        value={**(self.previous or self.scope),**deepcopy(values),'phase':phase}
        self.store.write(value,self.previous)
        info=self.store.path.lstat();private(info);original_stamp=stamp(info)
        need(same(self.store.read(),value) and digest(self.scope)==self.scope_sha
            and host_identity()==self.scope['hostProcessIdentity'] and stamp(self.store.path.lstat())==original_stamp)
        self.previous=deepcopy(value);self.previous_sha=digest(value);self.root_stamp=original_stamp
        need(stamp(self.store.path.lstat())==original_stamp)

    def control(self):
        plain(self.previous);need(digest(self.previous)==self.previous_sha)
        need(not self.failed and not self.started and not self.closed and same(self.store.read(),self.previous)
            and self.previous['phase']=='publishing' and digest(self.scope)==self.scope_sha
            and stamp(self.store.path.lstat())==self.root_stamp
            and digest([row for _owner,row in self.pairs])==self.pairs_sha
            and host_identity()==self.scope['hostProcessIdentity'])
        parent=record(self.adapter._chat_composition_store(self.target).read())
        need(parent['runId']==self.source.run and parent['fixtureUrl']==self.source.fixture_url
            and same(parent['binding'],self.scope['binding']) and same(parent['peerBinding'],self.scope['peerBinding'])
            and same(self.adapter._scripts(self.target).binding,self.scope['binding'])
            and self.original.native.guard() is not False and self.original.peer.guard() is True)
        for owner,row in self.pairs:
            need(owner.node==tuple(row['node']) and owner.fd==row['fd'] and owner.anchor==row['anchor'])
            owner.require(owner.fd)
        return parent

    def advance(self,parent):
        current=self.publisher.observation.stage
        if current=='initial' and parent['completedSteps']>=2:
            with self.held():
                owner=self.adapter._chat_observation(self.target,self.source,self.original.publisher.samples,stage='active',witness=True)
                self.publisher.select(owner)
        if self.publisher.observation.stage=='active' and parent['phase']=='caches-retired':
            with self.held():
                samples=self.adapter._chat_cache_absence(self.target,self.source.run,self.original.peer.reader(),
                    self.original.peer.binding,role='actor',stage='final',witness=True,
                    source_lock=self.original.lock,peer_lock=self.original.peer.lock,
                    script_source=self.publisher.observation.samples.script_source)
                owner=self.adapter._chat_observation(self.target,self.source,samples,stage='cleanup',witness=True)
                self.publisher.select(owner)

    def publish(self):
        need(not self.failed and not self.started and not self.closed)
        try:
            parent=self.control()
            if parent['phase'] not in ('step-completed','caches-retired'):
                raise PhasePending('Original Chat input or cleanup owner has not completed')
            self.advance(parent);started=self.publisher.observation.now();sequence=self.publisher.publish()
            self.control();self.publisher.cursor.final(started)
            self.publisher.cursor.released_fresh(self.publisher.cursor.clocks(),started)
            return sequence
        except PhasePending:
            if not self.publisher.failed and not self.publisher.cursor.failed:raise
            self.quarantine()
            raise NativeUIError('Original Chat publication became uncertain while waiting') from None
        except BaseException:
            self.quarantine();raise NativeUIError('Original independent Chat publication is unresolved') from None

    def stop_bytes(self):
        self.stop_store._parent()
        descriptor=os.open(self.stop_store.path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC)
        try:
            info=os.fstat(descriptor);private(info);physical=stamp(info)
            raw=os.pread(descriptor,65537,0)
            need(len(raw)==info.st_size and stamp(os.fstat(descriptor))==physical==stamp(self.stop_store.path.lstat()))
            self.stop_store._parent();return raw,physical
        finally:os.close(descriptor)

    def stop_original(self):
        raw,physical=self.stop_bytes()
        need(self.stop_stamp is not None and physical==self.stop_stamp and raw==self.stop_raw
            and same(self.stop_store.read(),self.stop_value) and stamp(self.stop_store.path.lstat())==self.stop_stamp)

    def stop_once(self):
        """One fixed original request; no unknown/lost command replay."""
        need(not self.failed and not self.started and not self.closed)
        try:return self._stop_once()
        except BaseException:
            self.quarantine()
            raise NativeUIError('Original independent Chat stop/seal/host closure is unresolved; originals remain') from None

    def _stop_once(self):
        parent=self.control();self.started=True
        raw,original_stamp=self.stop_bytes();value=self.stop_store.read()
        need(stamp(self.stop_store.path.lstat())==original_stamp and raw==canonical(value)+b'\n')
        exact(value,{'picoChatCursorActorStopVersion','commandId','instance','runId','afterSequence','ticket'})
        need(type(value['picoChatCursorActorStopVersion']) is int and value['picoChatCursorActorStopVersion']==STOP_VERSION
            and type(value['commandId']) is str and len(value['commandId'])==32
            and all(c in '0123456789abcdef' for c in value['commandId'])
            and value['instance']==self.scope['instance'] and value['runId']==self.source.run
            and integer(value['afterSequence'],1) and value['afterSequence']==len(self.publisher.rows)
            and value['ticket']==self.publisher.rows[-1]['payload']['ticket']
            and parent['phase']=='caches-retired' and self.publisher.observation.stage=='cleanup'
            and self.publisher.base['phase']=='ready' and self.publisher.base['delivery']=='ready'
            and self.publisher.base['pending'] is None and not self.publisher.query_pending and not self.publisher.cursor.query_pending)
        self.stop_value=deepcopy(value);self.stop_stamp=original_stamp;self.stop_raw=raw
        try:
            self.save('stop-issued',stopCommand=deepcopy(value),stopStamp=original_stamp,stopSha256=hashlib.sha256(raw).hexdigest());self.stop_original()
            self.seal=self.adapter._chat_cursor_source_seal(self.target,self.publisher,witness=True)
            self.seal_receipt=self.seal.run();self.stop_original()
            self.save('sealed',seal=deepcopy(self.seal_receipt),sealSha256=digest(self.seal_receipt))
            self.seal.receipt(self.seal_receipt);self.stop_original()
            need(self.original.peer.retirement_files is None)
            for owner,row in self.pairs:
                need(owner.node==tuple(row['node']) and owner.fd==row['fd'] and owner.anchor==row['anchor'])
                owner.require(owner.fd)
            self.save('host-close-issued');self.stop_original()
            okay=True
            for owner,_row in self.pairs:okay=OriginalDescriptor.close(owner) is True and okay
            okay=PicoChatWitness.detach(self.original) is True and okay
            need(okay and all(owner.closed and not owner.lost and owner.fd==owner.anchor==-1 for owner,_row in self.pairs))
            self.stop_original();self.seal.receipt(self.seal_receipt)
            self.save('host-closed',closedPairs=len(self.pairs),sourceScope='original-independent-chat-host-handles')
            self.stop_original();self.closed=True;return deepcopy(self.previous)
        except BaseException:
            self.quarantine()
            raise NativeUIError('Original independent Chat stop/seal/host closure is unresolved; originals remain') from None

    def return_control(self):
        """Historical original ownership only: no native guard or new query."""
        plain(self.previous);need(digest(self.previous)==self.previous_sha)
        need(self.closed and not self.failed and digest(self.scope)==self.scope_sha
            and self.scope['picoChatCursorActorVersion']==VERSION
            and host_identity()==self.scope['hostProcessIdentity']
            and self.previous['phase'] in ('host-closed','parent-consumed')
            and same(self.store.read(),self.previous) and stamp(self.store.path.lstat())==self.root_stamp
            and digest([row for _owner,row in self.pairs])==self.pairs_sha
            and all(owner.closed and not owner.lost and owner.fd==owner.anchor==-1 for owner,_row in self.pairs))
        self.stop_original();self.seal.receipt(self.seal_receipt)
        for store in (self.store,self.stop_store):ChatSourceChunks(store,{}).inventory(0)
        need(same(self.store.read(),self.previous) and stamp(self.store.path.lstat())==self.root_stamp)
        return True

    def publish_return(self):
        """Publish only a successfully received warm host-close result."""
        need(not self.return_started and not self.failed);self.return_started=True
        try:
            self.return_control();value,raw,physical=return_state(self.store)
            need(value['phase']=='host-closed' and same(value,self.previous) and physical==self.root_stamp)
            identity=dict(runId=self.source.run,family=RETURN_FAMILY,producerHostProcessIdentity=self.scope['hostProcessIdentity'],
                originalRequestId=self.stop_value['commandId'])
            self.return_sender=ObserverReturnSender(self.return_store,self.consumption_store,identity,raw,physical,
                guard=self.return_control)
            result=self.return_sender.publish();self.return_control();return result
        except BaseException:
            self.quarantine();raise NativeUIError('Original Chat host return publication is unresolved; originals remain') from None

    def consume_return(self):
        """One independent read of the Parent nonce, then normal return only."""
        need(self.return_started and self.return_sender is not None and not self.parent_consumed and not self.failed)
        try:
            self.return_control();value=self.return_sender.consume()
            self.save('parent-consumed',returnId=value['returnId'],returnSha256=digest(value),
                consumptionSha256=value['consumptionSha256'],parentHostProcessIdentity=value['consumption']['consumerHostProcessIdentity'])
            result=deepcopy(self.previous);self.return_sender.control();self.return_control();self.parent_consumed=True
            return result
        except BaseException:
            self.quarantine();raise NativeUIError('Original Chat Parent consumption is unresolved; originals remain') from None

    def detach(self):
        """Best-effort original handles only; no durable Actor/process claim."""
        return self.original is None or PicoChatWitness.detach(self.original) is True


def run(adapter,config,*,monotonic=time.monotonic,sleep=time.sleep):
    """Existing independent entrypoint; no discovery, start or input route."""
    from adapters.native_feature_observation import number
    need(config['area']=='chat' and callable(monotonic) and callable(sleep))
    started=previous=monotonic();need(number(started,0,1e15));actor=None
    client=Client(config['fixtureUrl'],config['actorToken'])
    def bound():
        nonlocal previous
        now=monotonic();need(number(now,previous,started+config['durationSeconds'])
            and now-started<config['durationSeconds']);previous=now
    while True:
        bound()
        if actor is None:
            parent=adapter._chat_composition_store(config['target']).read()
            if parent is not None:
                parent=record(parent)
                need(parent['fixtureUrl']==config['fixtureUrl']+'/runs/'+parent['runId']+'/')
                if parent['phase']=='prepared':
                    native=adapter._native_feature_observer(config['target']);native.guard()
                    source=PhaseFixtureReader(client,parent['runId'],'chat',epoch_ms=native.clock_ms,monotonic=monotonic)
                    actor=adapter._chat_cursor_actor(config['target'],source,PrivateFeatureState(config['peerConfig']))
                else:need(parent['phase'] in ('admitted','bound','profile-acquire-issued','profile-acquired'))
        if actor is not None:
            bound()
            if not actor.closed:
                if actor.stop_store.read() is not None:
                    actor.stop_once();bound();need(actor.closed and not actor.failed)
                    actor.publish_return();bound()
                else:
                    try:actor.publish()
                    except PhasePending:pass
            if actor.closed:
                actor.return_control();actor.return_sender.control()
                if actor.consumption_store.read() is not None:
                    actor.consume_return();bound();need(actor.parent_consumed and not actor.failed);return 0
            bound()
        sleep(.25)
