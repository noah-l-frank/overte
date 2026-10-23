"""Actual shared consumed cleanup bytes and one original remote Stop2 intent.

No second baseline, live Actor restoration, Stop ACK, process absence or whole
cleanup claim is provided. The complete typed return/archive join is separate.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import math
import uuid

from adapters.chat_journey.flow_inputs import fresh_roles
from adapters.chat_journey.observation_cursor import ChatObservationCursor,plain
from adapters.chat_journey.remote_publication import ChatRemotePublication
from adapters.chat_journey.source_chunks import ChatSourceChunks,digest
from adapters.host_process_identity import host_identity
from adapters.native_feature_observation import exact,need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.observer_return import state,parent_node
from adapters.script_journey.history import MAX_RAW,same
from feature_journeys.contract import arguments,json_document
from feature_journeys.engine import Journey
from feature_journeys.phase_fixture import PhasePending
from feature_journeys.scenarios import VERSION as CONTRACT_VERSION

VERSION=1


class ChatRemoteCleanupSlot:
    def __init__(self):
        self.journey=self.consumer=None;self.issued=self.completed=self.failed=False;self.callback=self.consume

    def attach(self,journey):
        need(self.journey is None and type(journey) is Journey and journey.area=='chat'
            and journey.after_cleanup_baseline is self.callback and not journey.cleanup_hook_started)
        self.journey=journey

    def bind(self,consumer):
        need(type(consumer) is ChatRemoteCleanupPrefix and self.journey is not None and self.consumer is None
            and not self.issued and not self.failed)
        self.consumer=consumer
        try:consumer.attach(self);consumer.begin()
        except BaseException:self.failed=True;consumer.quarantine();raise

    def consume(self,raw):
        need(not self.failed and not self.issued);self.issued=True
        try:
            need(self.consumer is not None and self.journey.cleanup_hook_started and raw is self.journey.cleanup_consumption)
            self.consumer.consume(raw);self.completed=True
        except BaseException:
            self.failed=True
            if self.consumer is not None:self.consumer.quarantine()
            raise


class ChatRemoteCleanupPrefix:
    """A completed prefix/Stop request is not a completed Actor or feature."""
    def __init__(self,primary,actor,stop_store,store,*,guard):
        need(type(primary) is ChatObservationCursor and primary.scope['role']=='primary' and primary.current.stage=='cleanup'
            and primary.rows and not primary.current.rows and not primary.failed
            and type(actor) is ChatRemotePublication and actor.rows and not actor.failed and actor.stop_intent is None
            and actor.scope['chatRemotePublicationVersion'] in (2,3)
            and all(same(primary.scope[key],actor.expected[key]) for key in ('runId','fixtureUrl','binding','peerBinding'))
            and all(first is second for first,second in zip(primary.current.samples.locks,actor.locks))
            and len(primary.current.samples.locks)==len(actor.locks)==2
            and primary.current.samples.script_source.store.path!=actor.stores['code'].path
            and type(store) is PrivateFeatureState and type(stop_store) is PrivateFeatureState
            and store.read() is None and stop_store.read() is None and callable(guard))
        paths=[store.path,stop_store.path,primary.store.path,actor.store.path]
        need(len(set(paths))==len(paths) and all(path.parent==store.path.parent for path in paths))
        for value in (store,stop_store):ChatSourceChunks(value,{}).inventory(0)
        self.primary,self.actor,self.stop_store,self.store,self.guard=primary,actor,stop_store,store,guard
        self.parent=parent_node(store)
        self.primary_start=len(primary.rows);self.actor_start=None
        self.scope=dict(chatRemoteCleanupPrefixVersion=VERSION,runId=primary.scope['runId'],fixtureUrl=primary.scope['fixtureUrl'],
            binding=deepcopy(primary.scope['binding']),peerBinding=deepcopy(primary.scope['peerBinding']),
            actorInstance=actor.expected['instance'],actorHostProcessIdentity=actor.expected['hostProcessIdentity'],
            primaryCursor=primary.store.path.name,remoteReader=actor.store.path.name,stopJournal=stop_store.path.name,
            primaryStart=self.primary_start,actorStart=self.actor_start,parentHostProcessIdentity=host_identity())
        self.history=ChatSourceChunks(store,self.scope);self.history.inventory(0)
        self.previous=None;self.root_stamp=None;self.rows=[];self.raw=None;self.command=None
        self.slot=self.journey=None;self.started=self.issued=self.completed=self.failed=False
        self.cache_sha=self.cache_digest()

    def cache_digest(self):
        need(type(self.history) is ChatSourceChunks and self.history.root is self.store and self.history.scope==digest(self.scope)
            and type(self.history.raw_bytes) is int and type(self.history.identities) is list
            and all(type(row) is tuple and len(row)==8 and all(type(field) is int for field in row) for row in self.history.identities))
        for value in (self.scope,self.previous,self.root_stamp,self.rows,self.command):plain(value)
        need(self.raw is None or type(self.raw) is bytes)
        return digest(dict(scope=self.scope,previous=self.previous,stamp=self.root_stamp,rows=self.rows,command=self.command,
            raw=None if self.raw is None else hashlib.sha256(self.raw).hexdigest(),
            history=dict(rawBytes=self.history.raw_bytes,identities=[list(row) for row in self.history.identities])))

    def control(self):
        need(not self.failed and self.cache_digest()==self.cache_sha and host_identity()==self.scope['parentHostProcessIdentity']
            and parent_node(self.store)==self.parent and same(self.store.read(),self.previous)
            and self.primary.store.path.name==self.scope['primaryCursor'] and self.actor.store.path.name==self.scope['remoteReader']
            and self.stop_store.path.name==self.scope['stopJournal']
            and all(path.parent==self.store.path.parent for path in (self.primary.store.path,self.actor.store.path,self.stop_store.path))
            and self.actor.expected['instance']==self.scope['actorInstance']
            and self.actor.expected['hostProcessIdentity']==self.scope['actorHostProcessIdentity'])
        if self.root_stamp is not None:need(state(self.store)[2]==self.root_stamp)
        self.history.verify()

    def save(self,phase,**changes):
        self.control();value={**(self.previous or {**self.scope,'chunks':[]}),'phase':phase,**deepcopy(changes)}
        self.store.write(value,self.previous);observed,_raw,physical=state(self.store);need(same(observed,value))
        self.previous=deepcopy(value);self.root_stamp=physical;self.cache_sha=self.cache_digest();self.control()

    def quarantine(self):
        self.failed=True;self.actor.failed=True;self.primary.failed=True

    def attach(self,slot):
        need(type(slot) is ChatRemoteCleanupSlot and slot.consumer is self and not slot.issued and not slot.failed
            and self.slot is None and not self.started and not self.failed
            and slot.journey.run==self.scope['runId'] and slot.journey.url==self.scope['fixtureUrl']
            and slot.journey.sequence==self.primary_start
            and 0<slot.journey.last_actor_sequence<=self.actor.rows[-1]['publication']['sequence'])
        actual=[sample['witness'] for sample in slot.journey.samples if sample.get('witness') is not None
            and sample['witness']['actorSequence']==slot.journey.last_actor_sequence]
        need(actual and any(same(entry,actual[-1]) for record in self.actor.rows for entry in record['received']['entries'])
            and self.previous is None and self.store.read() is None and not self.history.identities)
        self.actor_start=slot.journey.last_actor_sequence;self.scope['actorStart']=self.actor_start
        self.history=ChatSourceChunks(self.store,self.scope);self.history.inventory(0);self.cache_sha=self.cache_digest()
        self.slot,self.journey=slot,slot.journey

    def begin(self):
        need(self.slot is not None and not self.started and not self.failed);self.started=True
        try:self.save('external-observing')
        except BaseException:self.quarantine();raise

    def fresh_current(self):
        self.control();need(self.guard() is not False)
        self.primary.final(self.primary.started);self.actor.fresh_current()
        need(self.guard() is not False);self.control()
        fresh_roles((self.primary.current.samples,),self.primary.started,self.primary.current.now)
        self.actor.fresh_current()

    def observe(self,fields):
        fields=arguments('feature.chat.observe',fields)
        need(self.started and not self.issued and not self.failed and fields['runId']==self.scope['runId']
            and fields['afterSequence']==len(self.primary.rows))
        try:
            self.control();result=deepcopy(self.primary.read(fields['afterSequence']))
            self.control();self.primary.final(self.primary.started);return result
        except BaseException:self.quarantine();raise

    def received(self):
        need(self.started and not self.issued and not self.failed)
        try:
            self.control();result=self.actor.acquire(self.journey.last_actor_sequence)
            self.control();self.actor.released_fresh_current();return result
        except PhasePending:
            if not self.actor.failed:raise
            self.quarantine();raise NativeUIError('Actual remote Chat observation became uncertain') from None
        except BaseException:self.quarantine();raise

    def consume(self,raw):
        need(self.started and not self.issued and not self.failed);self.issued=True
        try:
            need(self.slot.issued and not self.slot.failed and type(raw) is bytes and 0<len(raw)<=MAX_RAW
                and raw is self.journey.cleanup_consumption and self.journey.cleanup_hook_started)
            value=json_document(raw)
            exact(value,{'cleanupConsumptionVersion','contractVersion','area','runId','fixtureUrl','ticket',
                'actionBarrierEpochMs','sequenceSucceeded','phase','samples','finalSequence'})
            need(type(value['cleanupConsumptionVersion']) is int and value['cleanupConsumptionVersion']==1
                and type(value['contractVersion']) is int and value['contractVersion']==CONTRACT_VERSION
                and value['area']=='chat' and value['runId']==self.scope['runId'] and value['fixtureUrl']==self.scope['fixtureUrl']
                and type(value['sequenceSucceeded']) is bool and type(value['samples']) is list and value['samples']
                and len(value['samples'])==len(self.primary.current.rows)
                and value['finalSequence']==self.journey.sequence==len(self.primary.rows)
                and same(value['phase'],self.journey.phases[-1]) and value['phase']['phase']=='cleanup-restored-baseline'
                and value['phase']['stableSeconds']>=3 and same(value['samples'],self.journey.samples[-len(value['samples']):])
                and value['samples'][-1]['witness']['actorSequence']==self.journey.last_actor_sequence
                ==self.actor.rows[-1]['publication']['sequence'])
            joined=[]
            for index,sample in enumerate(value['samples']):
                primary=self.primary.rows[self.primary_start+index];self.primary.original(primary)
                need(primary['stageIndex']==2 and primary['sourceSequence']==index+1 and sample['sequence']==primary['sequence']
                    and sample['ticket']==value['ticket'] and sample['actionBarrierEpochMs']==value['actionBarrierEpochMs']
                    and all(same(sample[key],primary['sample'][key]) for key in ('capturedEpochMs','state','resources','lifecycle')))
                matches=[]
                if sample['witness'] is not None:
                    matches=[record for record in self.actor.rows if any(same(row,sample['witness']) for row in record['received']['entries'])]
                    need(matches and sample['witness']['actorSequence']>self.actor_start)
                joined.append(dict(common=deepcopy(sample),primaryCursorSha256=digest(primary),
                    remoteReadSha256=None if not matches else digest(matches[0])))
            with self.primary.held():
                _authority,phase=self.primary.current.current();activation=phase['activations'][-1]
                need(value['ticket']==activation['ticket'] and activation['stimulus']==dict(verb='cleanup',inputs={})
                    and value['actionBarrierEpochMs']>=math.ceil(activation['activatedEpochMs']))
                self.fresh_current();self.raw=raw;self.cache_sha=self.cache_digest()
                self.save('reading',consumptionSha256=hashlib.sha256(raw).hexdigest(),
                    header={key:deepcopy(field) for key,field in value.items() if key!='samples'})
                for row in joined:
                    chunks=self.history.append(row,self.previous['chunks']);self.rows.append(row);self.cache_sha=self.cache_digest()
                    self.save('reading',chunks=chunks)
                published=self.actor.rows[-1]['publication'];self.command=dict(picoChatCursorActorStopVersion=2,
                    commandId=uuid.uuid4().hex,instance=self.scope['actorInstance'],runId=self.scope['runId'],ticket=value['ticket'],
                    consumedSequence=published['sequence'],consumedPayloadSha256=digest(published['payload']),
                    cleanupConsumptionSha256=hashlib.sha256(raw).hexdigest())
                self.cache_sha=self.cache_digest();self.save('stop-issued',command=self.command)
                self.actor.freeze(self.command);self.fresh_current();need(self.stop_store.read() is None)
                ChatSourceChunks(self.stop_store,{}).inventory(0)
                self.stop_store.write(self.command,None)
                actual,stop_raw,physical=state(self.stop_store);need(same(actual,self.command))
                self.save('stop-requested',stopSha256=hashlib.sha256(stop_raw).hexdigest(),stopStamp=physical)
                result=deepcopy(self.previous);self.fresh_current()
            self.control();self.primary.released_fresh(self.primary.clocks(),self.primary.started)
            self.actor.released_fresh_current();self.completed=True;return result
        except BaseException:
            self.quarantine();raise NativeUIError('Actual consumed Chat prefix or Stop2 delivery is unresolved; originals remain') from None
