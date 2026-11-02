"""Measured Create ownership scope and original independent cleanup return.

This does not launch a worker, select a target or supply Actor effect facts.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import math
from pathlib import Path
import uuid

from adapters.chat_journey.source_chunks import ChatSourceChunks,digest
from adapters.host_process_identity import host_identity
from adapters.native_feature_observation import decode,exact,fresh,need,integer,number
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.observer_return import ObserverReturnReceiver,state as physical_state
from adapters.pico4.create_peer_source import scope,VERSION,FAMILY,measured,client_identity,model_identity,phase_scope
from adapters.pico4.create_entities import validate as validate_entities,continuity as entity_continuity
from adapters.pico4.create_model_resources import validate as validate_resources,continuity as resource_continuity
from feature_journeys.contract import typed_equal
from feature_journeys.phase_fixture import validate as validate_phase


def admit_return(raw,physical,original_scope):
    primary=scope(original_scope);value=decode(raw.decode())
    exact(value,{'createPeerReturnVersion','scope','actorBinding','workerHostProcessIdentity','sourcePath','sourceSha256','final','quiet'})
    need(type(value['createPeerReturnVersion']) is int and value['createPeerReturnVersion']==VERSION
        and typed_equal(value['scope'],original_scope) and value['workerHostProcessIdentity']!=original_scope['parentHostProcessIdentity'])
    source=PrivateFeatureState(Path(value['sourcePath']));root,source_raw,source_physical=physical_state(source)
    need(source_physical==physical and hashlib.sha256(source_raw).hexdigest()==value['sourceSha256'])
    identity=dict(picoCreatePeerSourceVersion=VERSION,scope=original_scope,actorBinding=context(value['actorBinding']),
        producerHostProcessIdentity=value['workerHostProcessIdentity'])
    exact(root,set(identity)|{'phase','chunks','records','pending','quiet'})
    need(all(typed_equal(root[key],field) for key,field in identity.items()) and root['phase']=='reading' and root['pending'] is None
        and root['quiet']==value['quiet'] and type(root['records']) is list and 1<=len(root['records'])<=64)
    history=ChatSourceChunks(source,identity);rows=history.load(root['chunks']);previous_entities=previous_resources=None
    client=model=None
    pid=int(value['actorBinding']['processIdentity'].split(':')[0]);last_time=None
    for record in root['records']:
        exact(record,{'originals','phase','facts','capturedEpochMs','hostMonotonic','hostCompleted'})
        need(number(record['hostMonotonic'],0,1e15) and number(record['hostCompleted'],record['hostMonotonic'],1e15)
            and integer(record['phase'],0,len(rows)-1))
        references=record['originals'];packets={}
        exact(references,{'ticket','phase','query','entities','resources','commands','responses'})
        need(references['query'] is None and integer(references['phase'],0,len(rows)-1))
        exact(references['commands'],{'entities','resources'});exact(references['responses'],{'entities','resources'})
        for kind,validate in (('entities',validate_entities),('resources',validate_resources)):
            command=references['commands'][kind]
            exact(command,{'schemaVersion','commandId','action','runId'})
            need(command['schemaVersion']==1 and type(command['schemaVersion']) is int and command['runId']==original_scope['runId']
                and command['action']==('feature-create-entities-observe' if kind=='entities' else 'feature-create-models-observe')
                and references['responses'][kind] and references[kind]==references['responses'][kind][-1])
            for index in references['responses'][kind]:
                response=rows[index];need(response['kind']==kind and hashlib.sha256(response['raw'].encode()).hexdigest()==response['sha256'])
            retained=rows[references[kind]];need(retained['kind']==kind and hashlib.sha256(retained['raw'].encode()).hexdigest()==retained['sha256'])
            packet=decode(retained['raw']);need(packet['requestId']==command['commandId']);validate(packet,packet['requestId'],pid,packet['capturedEpochMs'],original_scope['runId']);packets[kind]=packet
        entities,resources=packets['entities'],packets['resources'];entity_continuity(previous_entities,entities);resource_continuity(previous_resources,resources)
        need(record['capturedEpochMs']==min(entities['capturedEpochMs'],resources['capturedEpochMs']))
        need(typed_equal(measured(primary,original_scope,entities,resources,model is not None),record['facts']))
        current_client=client_identity(entities);need(client is None or client==current_client);client=current_client
        model=model_identity(model,original_scope,entities,resources)
        phase=rows[record['phase']]['packet'];validate_phase(phase,run=original_scope['runId'],area='create',request=phase['requestId'],epoch=phase['capturedEpochMs'])
        phase_scope(original_scope,phase)
        need(references['ticket']==phase['activations'][-1]['ticket'])
        previous_entities,previous_resources=entities,resources
        if last_time is not None:need(record['hostMonotonic']>=last_time)
        last_time=record['hostMonotonic']
    final=deepcopy(root['records'][-1]);final['phaseOriginal']=rows[final['phase']]['packet'];need(typed_equal(final,value['final']))
    quiet=value['quiet'];exact(quiet,{'started','completed','originalEpochs','finalEpochs','firstRecord','record'})
    need(final['facts']['observedOriginalsRetired'] and quiet['record']==len(root['records'])-1
        and quiet['completed']-quiet['started']>=3 and len(quiet['originalEpochs'])==len(quiet['finalEpochs'])==2
        and all(b-a>=3000 for a,b in zip(quiet['originalEpochs'],quiet['finalEpochs'])))
    need(type(quiet['firstRecord']) is int and 0<=quiet['firstRecord']<quiet['record'])
    included=root['records'][quiet['firstRecord']:quiet['record']+1]
    need(len(included)>=2 and all(record['facts']['observedOriginalsRetired'] for record in included)
        and all(0<=b['hostCompleted']-a['hostCompleted']<=.5 for a,b in zip(included,included[1:])))
    need(included[0]['hostCompleted']<=quiet['started']<=included[1]['hostCompleted']
        and included[-1]['hostCompleted']<=quiet['completed']<=included[-1]['hostCompleted']+1.5)
    phases=[rows[record['phase']]['packet'] for record in included]
    need(all(phase['active'] and phase['activations']==phases[-1]['activations'] for phase in phases))
    for record,clocks in ((included[0],quiet['originalEpochs']),(included[-1],quiet['finalEpochs'])):
        actual=[decode(rows[record['originals'][kind]]['raw'])['capturedEpochMs'] for kind in ('entities','resources')]
        need(clocks==actual)
    phase=final['phaseOriginal'];need(phase['active'] and phase['activations'][-1]['stimulus']==dict(verb='cleanup',inputs={}))
    history.verify();need(physical_state(source)[1:]==(source_raw,source_physical));return True


class CreatePeerParent:
    def peer_state(self):
        value=self.source_store('peer').read()
        if value is not None:
            exact(value,{'createPeerParentVersion','binding','runId','scope','phase','receipt','payload','sourceStamp'})
            need(type(value['createPeerParentVersion']) is int and value['createPeerParentVersion']==VERSION
                and context(value['binding'])==context(self.state()['binding']) and value['runId']==self.run
                and value['phase'] in ('issued','returned'))
            scope(value['scope'])
            need(value['scope']['runId']==self.run and context(value['scope']['binding'])==context(value['binding'])
                and value['scope']['fixtureUrl']==self.source.fixture_url)
            need((value['receipt'] is None and value['payload'] is None and value['sourceStamp'] is None) if value['phase']=='issued'
                else type(value['receipt']) is dict and type(value['payload']) is str and type(value['sourceStamp']) is list)
        return value

    def issue_peer_scope(self):
        with self.lock.held():
            self.runtime();root=self.state();need(self.peer_state() is None and not root['cleanupStarted'] and root['pending'] is None)
            model=self.component('models');owned=model.state();step=owned['steps'][-1]
            need(owned['pending'] is None and step['entityId'] is not None and step['outcome'] in ('created','texture-property-applied'))
            started=self.source.monotonic();requested=model.entities.reader.clock_ms();actual=model.capture();row=model.actual_entity(actual)
            need(row is not None and row['id']==step['entityId'])
            active=self.source.read(root['phase']);call=root['calls'][-1]
            need(active['ticket']==call['ticket'] and active['verb']==call['verb'] and typed_equal(active['inputs'],call['inputs']))
            raw=model.entities.reader.last_raw
            original=dict(createPeerScopeVersion=VERSION,runId=self.run,binding=deepcopy(root['binding']),fixtureUrl=self.source.fixture_url,
                requestId=uuid.uuid4().hex,parentHostProcessIdentity=host_identity(),entityId=row['id'],createTicket=step['ticket'],
                primaryEntities=raw,primaryEntitiesSha256=hashlib.sha256(raw.encode()).hexdigest(),phaseOriginal=deepcopy(active['status']))
            scope(original)
            value=dict(createPeerParentVersion=VERSION,binding=deepcopy(root['binding']),runId=self.run,scope=original,phase='issued',receipt=None,payload=None,sourceStamp=None)
            self.source_store('peer').write(value,None)
            self.runtime();epoch=model.entities.reader.clock_ms();now=self.source.monotonic()
            for packet in (actual['entities'],actual['resources'],active['status']):fresh(packet['capturedEpochMs'],max(epoch,requested+math.ceil((now-started)*1000)))
            return deepcopy(original)

    def accept_peer_return(self,receiver):
        need(type(receiver) is ObserverReturnReceiver)
        with self.lock.held():
            self.runtime();value=self.peer_state();need(value is not None and value['phase']=='issued' and self.state()['cleanupStarted'])
            original=value['scope'];need(receiver.scope['runId']==self.run and receiver.scope['family']==FAMILY
                and receiver.scope['originalRequestId']==original['requestId'] and original['parentHostProcessIdentity']==host_identity())
            admit_return(receiver.raw,receiver.scope['sourceStamp'],original)
            payload=decode(receiver.raw.decode());need(payload['workerHostProcessIdentity']==receiver.scope['producerHostProcessIdentity'])
            phase=payload['final']['phaseOriginal'];active=self.phase_fence()
            need(phase['instance']==active['instance'] and phase['createdEpochMs']==active['createdEpochMs']
                and typed_equal(phase['activations'],active['activations']))
            receipt=receiver.receipt();need(receiver.owner.close() is True)
            current=deepcopy(value);current.update(phase='returned',receipt=receipt,payload=receiver.raw.decode(),sourceStamp=receiver.scope['sourceStamp'])
            self.source_store('peer').write(current,value);need(self.peer_state()==current)
            self.phase_fence();return deepcopy(receipt)

    def peer_cleanup_ready(self):
        value=self.peer_state()
        if value is not None:
            need(value['phase']=='returned');admit_return(value['payload'].encode(),value['sourceStamp'],value['scope'])

