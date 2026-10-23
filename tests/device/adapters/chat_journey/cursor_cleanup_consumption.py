"""Shared consumed global Chat rows joined to their exact warm source graph."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
import math

from adapters.chat_journey.cleanup_baseline import ChatCleanupBaseline
from adapters.chat_journey.cursor_source_seal import ChatCursorSourceSeal
from adapters.chat_journey.observation_cursor import ChatObservationCursor
from adapters.chat_journey.observation_publisher import ChatObservationPublisher
from adapters.chat_journey.source_chunks import ChatSourceChunks,digest
from adapters.native_feature_observation import exact,fresh,integer,need,number
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_journey.history import same,MAX_RAW
from feature_journeys.contract import arguments,json_document
from feature_journeys.engine import Journey
from feature_journeys.scenarios import VERSION as CONTRACT_VERSION

VERSION=1


class ChatCleanupFinalizationSlot:
    """Original once-bound hook, registered before later cleanup owners exist."""
    def __init__(self):
        self.journey=self.consumer=None;self.issued=self.completed=self.failed=False;self.callback=self.consume

    def attach(self,journey):
        need(self.journey is None and type(journey) is Journey and journey.area=='chat'
            and journey.after_cleanup_baseline is self.callback and not journey.cleanup_hook_started)
        self.journey=journey

    def bind(self,consumer):
        need(self.journey is not None and self.consumer is None and not self.issued and not self.failed
            and type(consumer) is ChatCursorCleanupConsumption)
        self.consumer=consumer
        try:consumer.attach(self);consumer.begin()
        except Exception:self.failed=True;consumer.quarantine();raise

    def consume(self,raw):
        need(not self.failed and not self.issued);self.issued=True
        try:
            need(self.journey is not None and self.consumer is not None and self.journey.cleanup_hook_started
                and raw is self.journey.cleanup_consumption)
            self.consumer.consume(raw);self.completed=True
        except Exception:
            self.failed=True
            if self.consumer is not None:self.consumer.quarantine()
            raise


class ChatCursorCleanupConsumption(ChatCleanupBaseline):
    """No second wait and no caller offset; only the actual global ledger joins.

    This explicit new family reuses the existing physical baseline/receipt and
    original-clock machinery. Legacy private 26-row baselines remain separate.
    """
    def __init__(self,primary,actor,seals,store,*,guard):
        need(type(primary) is ChatObservationCursor and primary.scope['role']=='primary'
            and type(actor) is ChatObservationPublisher and primary.current.stage==actor.observation.stage=='cleanup'
            and not primary.current.rows and not actor.observation.rows and primary.rows and actor.rows
            and primary.current.source.run==actor.observation.source.run
            and primary.current.source.fixture_url==actor.observation.source.fixture_url
            and primary.current.source.client is not actor.observation.source.client
            and primary.current.samples.script_source is not actor.observation.samples.script_source
            and same(primary.scope['binding'],actor.cursor.scope['binding'])
            and same(primary.scope['peerBinding'],actor.cursor.scope['peerBinding'])
            and tuple(lock.path for lock in primary.current.samples.locks)==tuple(lock.path for lock in actor.observation.samples.locks)
            and type(seals) is tuple and len(seals)==2 and all(type(value) is ChatCursorSourceSeal for value in seals)
            and seals[0].owner is primary and seals[1].owner is actor and all(value.live() for value in seals)
            and type(store) is PrivateFeatureState and store.read() is None and callable(guard))
        self.primary_cursor,self.primary,self.actor=primary,primary.current,actor
        self.primary_start,self.actor_start=len(primary.rows),len(actor.rows)
        self.seals,self.store,self.guard=seals,store,guard;self.previous=None;self.failed=self.started=self.completed=False
        self.issued=False;self.slot=self.journey=None;self.rows=[];self.latest_started=None
        self.seal_receipts=self.root_stamp=self.raw=self.result=None
        self.scope=dict(chatCursorCleanupConsumptionVersion=VERSION,runId=primary.scope['runId'],fixtureUrl=primary.scope['fixtureUrl'],
            binding=deepcopy(primary.scope['binding']),peerBinding=deepcopy(primary.scope['peerBinding']),
            primaryCursor=primary.store.path.name,actorCursor=actor.cursor.store.path.name,actorPublisher=actor.store.path.name,
            primaryStart=self.primary_start,actorStart=self.actor_start,sourceSeals=[value.store.path.name for value in seals])
        paths=[store.path,primary.store.path,actor.store.path,*[value.store.path for value in seals]]
        need(len(set(paths))==len(paths) and all(path.parent==store.path.parent for path in paths))
        self.history=ChatSourceChunks(store,self.scope);self.history.inventory(0)

    def attach(self,slot):
        need(type(slot) is ChatCleanupFinalizationSlot and slot.consumer is self and not slot.issued and not slot.failed
            and self.slot is None and not self.failed and not self.started
            and slot.journey.run==self.scope['runId'] and slot.journey.url==self.scope['fixtureUrl']
            and slot.journey.sequence==self.primary_start and slot.journey.last_actor_sequence==self.actor_start)
        self.slot,self.journey=slot,slot.journey

    def begin(self):
        need(self.slot is not None and not self.started and not self.failed);self.started=True
        try:self.save('external-observing')
        except Exception:self.quarantine();raise

    def run(self,*_args,**_kwargs):need(False) # No duplicate private common wait.

    def quarantine(self):
        self.failed=True
        for seal in self.seals:seal.failed=True

    def control(self):
        super().control();self.primary_cursor.control();self.actor.control()

    def observe(self,fields):
        fields=arguments('feature.chat.observe',fields)
        need(self.started and not self.failed and not self.completed and fields['runId']==self.scope['runId']
            and fields['afterSequence']==len(self.primary_cursor.rows))
        try:
            self.control();self.latest_started=self.primary.now()
            value=deepcopy(self.primary_cursor.read(fields['afterSequence']))
            self.latest_started=min(self.primary_cursor.started,self.actor.cursor.started)
            self.fresh_pair();return value
        except Exception:self.quarantine();raise

    def received(self):
        self.control();started=self.primary.now();value=deepcopy(self.actor.client.request('/runs/'+self.scope['runId']))
        exact(value,{'schemaVersion','runId','area','ticket','sampleEpochMs','entries'})
        need(type(value['schemaVersion']) is int and value['schemaVersion']==1
            and value['runId']==self.scope['runId'] and value['area']=='chat'
            and type(value['entries']) is list and len(value['entries'])<=512 and len(self.actor.rows)>self.actor_start)
        ticket=self.actor.rows[-1]['payload']['ticket'];rows=[row for row in value['entries'] if row.get('ticket')==ticket]
        published=self.actor.rows[self.actor_start:];need(value['ticket']==ticket and len(rows)==len(published))
        last=0
        for actual in value['entries']:
            exact(actual,{'ticket','actor','actorSequence','capturedEpochMs','facts','sequence','receivedEpochMs'})
            need(integer(actual['sequence'],last+1) and integer(actual['actorSequence'],1));last=actual['sequence']
        for actual,source in zip(rows,published):
            need(all(same(actual[key],field) for key,field in source['payload'].items())
                and number(actual['capturedEpochMs'],1) and number(actual['receivedEpochMs'],1)
                and actual['capturedEpochMs']<=actual['receivedEpochMs']+250
                and actual['receivedEpochMs']<=value['sampleEpochMs']+250)
        before=self.primary.now();epoch=self.actor.observation.source.epoch_ms()
        self.fresh_pair();ended=self.primary.now()
        need(number(ended,started,started+1.5));fresh(value['sampleEpochMs'],epoch+math.ceil((ended-before)*1000))
        return value

    def append(self,row,stage):
        with self.held(self.primary):
            chunks=self.history.append(row,self.previous['chunks']);self.save(stage,chunks=chunks);self.rows.append(row)

    def consume(self,raw):
        need(self.started and not self.issued and not self.failed);self.issued=True
        try:
            need(self.slot.issued and not self.slot.failed and type(raw) is bytes and 0<len(raw)<=MAX_RAW
                and raw is self.journey.cleanup_consumption and self.journey.cleanup_hook_started
                and self.actor.base['phase']=='ready' and self.actor.base['delivery']=='ready'
                and self.actor.base['pending'] is None and not self.actor.query_pending and not self.actor.cursor.query_pending)
            value=json_document(raw)
            exact(value,{'cleanupConsumptionVersion','contractVersion','area','runId','fixtureUrl','ticket',
                'actionBarrierEpochMs','sequenceSucceeded','phase','samples','finalSequence'})
            need(type(value['cleanupConsumptionVersion']) is int and value['cleanupConsumptionVersion']==1
                and type(value['contractVersion']) is int and value['contractVersion']==CONTRACT_VERSION
                and value['area']=='chat' and value['runId']==self.scope['runId'] and value['fixtureUrl']==self.scope['fixtureUrl']
                and type(value['sequenceSucceeded']) is bool and type(value['samples']) is list and value['samples']
                and len(value['samples'])==len(self.primary.rows)
                and value['finalSequence']==self.journey.sequence==len(self.primary_cursor.rows)
                and same(value['phase'],self.journey.phases[-1]) and value['phase']['phase']=='cleanup-restored-baseline'
                and value['phase']['stableSeconds']>=3 and same(value['samples'],self.journey.samples[-len(value['samples']):])
                and self.journey.last_actor_sequence==self.actor.rows[-1]['payload']['actorSequence']
                and value['samples'][-1]['witness']['actorSequence']==self.journey.last_actor_sequence)
            with self.held(self.primary):
                _authority,phase=self.primary.current();activation=phase['activations'][-1]
                need(value['ticket']==activation['ticket'] and activation['stimulus']==dict(verb='cleanup',inputs={})
                    and value['actionBarrierEpochMs']>=math.ceil(activation['activatedEpochMs']))
            joined=[]
            for index,sample in enumerate(value['samples']):
                primary=self.primary_cursor.rows[self.primary_start+index];source=self.primary.rows[index]
                actor_index=sample['witness']['actorSequence']-1
                need(type(actor_index) is int and self.actor_start<=actor_index<len(self.actor.rows))
                published=self.actor.rows[actor_index];actor=self.actor.cursor.rows[actor_index]
                self.primary_cursor.original(primary);self.actor.cursor.original(actor)
                need(primary['sourceSequence']==source['sequence']==index+1 and primary['stageIndex']==2 and actor['stageIndex']==2
                    and primary['observationSha256']==digest(source) and published['cursorSha256']==digest(actor)
                    and sample['sequence']==primary['sequence'] and sample['ticket']==value['ticket']
                    and sample['actionBarrierEpochMs']==value['actionBarrierEpochMs']
                    and all(same(sample[key],primary['sample'][key]) for key in ('capturedEpochMs','state','resources','lifecycle'))
                    and all(same(sample['witness'][key],field) for key,field in published['payload'].items()))
                joined.append(dict(kind='sample',common=deepcopy(sample),primaryObservationSha256=digest(source),
                    primaryCursorSha256=digest(primary),actorPublicationSha256=digest(published),actorCursorSha256=digest(actor)))
            receiver=self.received();received={row['actorSequence']:row for row in receiver['entries'] if row['ticket']==value['ticket']}
            need(all(same(sample['witness'],received[sample['witness']['actorSequence']]) for sample in value['samples']))
            self.raw=raw
            header={key:deepcopy(field) for key,field in value.items() if key!='samples'}
            self.save('externally-consumed',externalConsumption=dict(header=header,sha256=hashlib.sha256(raw).hexdigest()))
            self.append(dict(kind='receiver',journal=receiver),'received')
            for row in joined:self.append(row,'measured')
            self.fresh_pair();self.save('sealing-actor');actor=self.seals[1].run()
            self.save('sealing-primary');primary=self.seals[0].run();self.seal_receipts=(primary,actor)
            receipts=[seal.receipt(original) for seal,original in zip(self.seals,self.seal_receipts)]
            self.save('complete',phase='ready',common=deepcopy(value['phase']),sealSha256=[digest(row) for row in receipts])
            from adapters.chat_journey.evidence_archive import stamp,private
            info=self.store.path.lstat();private(info);self.root_stamp=stamp(info)
            self.result=deepcopy(self.previous);self.control();self.fresh_pair();self.completed=True
        except Exception:self.quarantine();raise

    def receipt(self):
        need(self.completed and not self.failed and self.raw is self.journey.cleanup_consumption)
        value=super().receipt(self.result);extension=value['externalConsumption']
        reconstructed={**extension['header'],'samples':[deepcopy(row['common']) for row in self.rows if row['kind']=='sample']}
        raw=json.dumps(reconstructed,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf-8')
        need(raw==self.raw and extension['sha256']==hashlib.sha256(raw).hexdigest());return value
