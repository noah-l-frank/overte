"""Separate-host, separate-client native Create originals; no product input.

This bounded Model witness is not the complete common Create Actor: GUI,
permissions, voxels, GPU pixels and stereo need their own original sources.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import math

from adapters.chat_journey.source_chunks import ChatSourceChunks,digest
from adapters.host_process_identity import host_identity
from adapters.native_feature_observation import decode,exact,fresh,integer,need,number
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.normal_ui import NativeUIError
from adapters.observer_return import host,parent_node,state as physical_state,ObserverReturnSender
from adapters.pico4.create_entities import NativeCreateEntities,validate as validate_entities,retired as entities_retired
from adapters.pico4.create_model_resources import NativeCreateModelResources,retired as resources_retired
from adapters.pico4.create_model_resource_join import ResourceJoinedCreateModels
from adapters.script_journey.history import canonical
from adapters.script_journey.lock import ScriptSourceLock
from adapters.token_create_ui import nonce
from feature_journeys.contract import typed_equal
from feature_journeys.phase_fixture import PhaseFixtureReader,validate as validate_phase

VERSION=1
FAMILY='pico-create-model-peer'


def scope(value):
    exact(value,{'createPeerScopeVersion','runId','binding','fixtureUrl','requestId','parentHostProcessIdentity',
        'entityId','createTicket','primaryEntities','primaryEntitiesSha256','phaseOriginal'})
    need(type(value['createPeerScopeVersion']) is int and value['createPeerScopeVersion']==VERSION)
    for key in ('runId','requestId','entityId','createTicket'):need(nonce(value[key]))
    context(value['binding']);need(type(value['primaryEntities']) is str
        and hashlib.sha256(value['primaryEntities'].encode()).hexdigest()==value['primaryEntitiesSha256'])
    packet=decode(value['primaryEntities']);validate_entities(packet,packet['requestId'],
        int(value['binding']['processIdentity'].split(':')[0]),packet['capturedEpochMs'],value['runId'])
    rows=[row for row in packet['source']['entities'] if row['id']==value['entityId']]
    need(packet['source']['createEntitySourceVersion'] in (4,5,6) and packet['source']['domainConnected']
        and len(rows)==1 and rows[0]['hostType']=='domain' and rows[0]['type']=='Model')
    phase=value['phaseOriginal'];validate_phase(phase,run=value['runId'],area='create',request=phase['requestId'],epoch=phase['capturedEpochMs'])
    need(phase['active'] and any(row['ticket']==value['createTicket'] and row['stimulus']['verb']=='model-create' for row in phase['activations']))
    return packet


def phase_scope(original_scope,value):
    original=original_scope['phaseOriginal'];prefix=original['activations']
    need(value['instance']==original['instance'] and value['createdEpochMs']==original['createdEpochMs']
        and len(value['activations'])>=len(prefix) and typed_equal(value['activations'][:len(prefix)],prefix))


def measured(primary,original_scope,entities,resources,known_model):
    a,b=entities['source'],resources['source'];origin=primary['source']
    need(entities['instance']==resources['instance'] and a['domainConnected']
        and a['createEntitySourceVersion'] in (4,5,6) and a['domainId']==origin['domainId']
        and a['sessionId']!=origin['sessionId'] and entities['instance']!=primary['instance']
        and b['domainSession']==a['domainSession'] and a['domainSession']['domainSha256']==origin['domainSession']['domainSha256'])
    identifiers={row['id'] for row in a['entities']}|set(a['absentIds'])
    need({row['entityId'] for row in b['bindings']}==identifiers)
    rows=[row for row in a['entities'] if row['id']==original_scope['entityId']];need(len(rows)<=1)
    row=rows[0] if rows else None;loaded=texture=False
    if row is not None:
        original=next(item for item in origin['entities'] if item['id']==original_scope['entityId'])
        need(row['type']=='Model' and row['createdEpochUs']==original['createdEpochUs']
            and row['hostType']=='domain' and row['parentId'] is None and not row['locked'])
        if row['type']=='Model':
            loaded=ResourceJoinedCreateModels.loaded(resources,row['id'],row['modelUrl'])
            assignment=decode(row['textures']) if row['textures'] else {}
            if set(assignment)=={'checker.png'}:
                bound=ResourceJoinedCreateModels.model_binding(resources,row['id'])
                texture=bool(loaded and ResourceJoinedCreateModels.texture_bound(resources,bound,assignment['checker.png']))
    dead=bool(known_model and original_scope['entityId'] in a['absentIds'] and entities_retired(a) and resources_retired(b))
    return dict(entityId=original_scope['entityId'],present=row is not None,entityType=None if row is None else row['type'],
        modelLoaded=bool(loaded),materialAssignmentBound=bool(texture),observedOriginalsRetired=dead,
        independentClient=True,gpuPixelsObserved=False,fullCreateActor=False)


def client_identity(packet):
    return packet['instance'],packet['source']['sessionId'],deepcopy(packet['source']['domainSession'])


def model_identity(previous,original_scope,entities,resources):
    present=[row for row in entities['source']['entities'] if row['id']==original_scope['entityId']]
    if not present:return previous
    life=next(row for row in entities['source']['entityLifetimes'] if row['id']==original_scope['entityId'])
    identity={key:life[key] for key in ('id','instance','firstObservedEpochMs')}
    binding=ResourceJoinedCreateModels.model_binding(resources,original_scope['entityId'])
    identity.update(model=binding['model'],geometry=binding.get('geometry'))
    if previous is not None:
        need(all(identity[key]==previous[key] for key in ('id','instance','firstObservedEpochMs')))
        for key in ('model','geometry'):
            if previous[key] is not None:need(identity[key]==previous[key])
    return identity


class PicoCreatePeerSource:
    def __init__(self,path,original_scope,binding,entities,resources,phases,source_lock,*,guard,monotonic,sleep):
        primary=scope(original_scope)
        need(type(entities) is NativeCreateEntities and type(resources) is NativeCreateModelResources
            and type(phases) is PhaseFixtureReader and type(source_lock) is ScriptSourceLock
            and all(callable(f) for f in (guard,monotonic,sleep)))
        self.scope,self.binding=deepcopy(original_scope),deepcopy(context(binding));self.run=self.scope['runId']
        self.primary,self.entities,self.resources,self.phases,self.lock=primary,entities,resources,phases,source_lock
        self.guard,self.monotonic,self.sleep=guard,monotonic,sleep;self.worker=host_identity()
        host(self.scope['parentHostProcessIdentity']);need(self.worker!=self.scope['parentHostProcessIdentity'])
        self.pid=int(self.binding['processIdentity'].split(':')[0])
        need(entities.pid==resources.pid==self.pid and entities.run==resources.run==self.run
            and entities.last is None and resources.last is None and phases.run==self.run and phases.area=='create'
            and phases.fixture_url==self.scope['fixtureUrl'])
        self.store=PrivateFeatureState(path);need(self.store.path.name=='create-peer-originals.json'
            and self.lock.path==self.store.path.with_name('script-sources.lock'))
        self.parent=parent_node(self.store);self.failed=False;self.anchor=self.client_identity=self.model_identity=None
        self.identity=dict(picoCreatePeerSourceVersion=VERSION,scope=self.scope,actorBinding=self.binding,
            producerHostProcessIdentity=self.worker)
        self.identity_sha=digest(self.identity);self.original_readers=(entities,resources,phases);self.history=ChatSourceChunks(self.store,self.identity)
        need(self.store.read() is None);self.history.inventory(0)
        self.disk=dict(self.identity,phase='reading',chunks=[],records=[],pending=None,quiet=None)
        self.store.write(self.disk,None);self.pin()

    def pin(self):
        current,_raw,physical=physical_state(self.store);need(typed_equal(current,self.disk))
        self.stamp=physical;self.disk_sha=digest(self.disk)

    def bound(self):
        need(not self.failed and host_identity()==self.worker and digest(self.identity)==self.identity_sha
            and parent_node(self.store)==self.parent and self.phases.run==self.run and self.phases.area=='create'
            and self.phases.fixture_url==self.scope['fixtureUrl'] and self.entities.pid==self.resources.pid==self.pid
            and self.entities.run==self.resources.run==self.run and self.original_readers==(self.entities,self.resources,self.phases)
            and typed_equal(self.primary,decode(self.scope['primaryEntities'])))
        host(self.scope['parentHostProcessIdentity']);host(self.worker,current=True)
        current,_raw,physical=physical_state(self.store)
        need(typed_equal(current,self.disk) and digest(self.disk)==self.disk_sha and physical==self.stamp)
        self.history.verify();need(self.guard() is not False and self.entities.guard() is not False and self.resources.guard() is not False)

    def save(self,value):
        self.bound();self.store.write(value,self.disk);self.disk=deepcopy(value);self.pin();self.bound()

    def archive(self,value):
        self.bound();index=len(self.disk['chunks']);manifest=self.history.append(value,self.disk['chunks'])
        updated=deepcopy(self.disk);updated['chunks']=manifest
        # The immutable child precedes its root CAS. An interrupted root write
        # leaves an orphan and cannot be adopted by another acquisition.
        self.store.write(updated,self.disk);self.disk=updated;self.pin();self.bound();return index

    def query(self,kind,reader):
        send,original=reader.send,reader.original;received=[]
        def issued(command):
            current=deepcopy(self.disk);need(current['pending']['query'] is None)
            current['pending']['query']=dict(kind=kind,command=deepcopy(command),responses=[]);self.save(current)
            current=deepcopy(self.disk);current['pending']['commands'][kind]=deepcopy(command);current['pending']['responses'][kind]=[];self.save(current)
            send(command)
        def retained():
            raw=original();need(type(raw) is str and len(raw.encode())<=2*1024*1024)
            index=self.archive(dict(kind=kind,raw=raw,sha256=hashlib.sha256(raw.encode()).hexdigest()))
            current=deepcopy(self.disk);current['pending']['query']['responses'].append(index);self.save(current)
            current=deepcopy(self.disk);current['pending']['responses'][kind].append(index);self.save(current)
            received.append((index,raw));return raw
        reader.send,reader.original=issued,retained
        try:value=reader.read()
        finally:reader.send,reader.original=send,original
        need(received and received[-1][1]==reader.last_raw and decode(reader.last_raw)==value)
        current=deepcopy(self.disk);current['pending'][kind]=received[-1][0];current['pending']['query']=None;self.save(current)
        return value

    def measured(self,entities,resources):
        facts=measured(self.primary,self.scope,entities,resources,self.model_identity is not None);identity=client_identity(entities)
        if self.client_identity is None:self.client_identity=identity
        else:need(identity==self.client_identity)
        self.model_identity=model_identity(self.model_identity,self.scope,entities,resources);return facts

    def fresh(self):
        self.bound();started,requested,oldest=self.anchor;epoch=self.entities.clock_ms();now=self.monotonic()
        need(integer(epoch,requested) and number(now,started,1e15));fresh(oldest,max(epoch,requested+math.ceil((now-started)*1000)))

    def read(self):
        try:
            with self.lock.held():
                self.bound();need(self.disk['pending'] is None and len(self.disk['records'])<64)
                started=self.monotonic();requested=self.entities.clock_ms();need(number(started,0,1e15) and integer(requested,1))
                before=self.phases.read();need(before['status']['active'])
                phase_index=self.archive(dict(kind='phase',packet=before['status']))
                phase_scope(self.scope,before['status'])
                current=deepcopy(self.disk);current['pending']=dict(ticket=before['ticket'],phase=phase_index,query=None,entities=None,resources=None,commands={},responses={});self.save(current)
                entities=self.query('entities',self.entities);resources=self.query('resources',self.resources)
                facts=self.measured(entities,resources);after=self.phases.read(before['status'])
                need(typed_equal(before['status']['activations'],after['status']['activations']))
                oldest=min(entities['requestedEpochMs'],entities['capturedEpochMs'],resources['requestedEpochMs'],resources['capturedEpochMs'],before['status']['capturedEpochMs'])
                self.anchor=started,requested,oldest
                after_index=self.archive(dict(kind='phase',packet=after['status']))
                record=dict(originals=deepcopy(self.disk['pending']),phase=after_index,facts=facts,
                    capturedEpochMs=min(entities['capturedEpochMs'],resources['capturedEpochMs']),hostMonotonic=started,
                    hostCompleted=self.monotonic())
                updated=deepcopy(self.disk);updated['records'].append(record);updated['pending']=None;self.save(updated)
                result=deepcopy(record);result['phase']=deepcopy(after['status']);self.fresh()
            need(self.lock._owner is None);self.fresh();return result
        except Exception:
            self.failed=True
            raise NativeUIError('Independent Create peer originals unresolved; ownership retained, no query replayed') from None

    def cleanup(self):
        started=self.monotonic();quiet=None;epochs=None;first=None;previous=None
        for attempt in range(67):
            row=self.read();current=self.monotonic();activation=row['phase']['activations'][-1]
            need(activation['stimulus']==dict(verb='cleanup',inputs={}))
            if previous is not None and current-previous>.5:quiet=epochs=first=None
            previous=current
            if row['facts']['observedOriginalsRetired']:
                if quiet is None:quiet=current;first=len(self.disk['records'])-1
                clocks=(self.entities.last['capturedEpochMs'],self.resources.last['capturedEpochMs'])
                epochs=clocks if epochs is None else epochs
                if current-quiet>=3 and all(b-a>=3000 for a,b in zip(epochs,clocks)):
                    updated=deepcopy(self.disk);updated['quiet']=dict(started=quiet,completed=current,originalEpochs=list(epochs),finalEpochs=list(clocks),firstRecord=first,record=len(updated['records'])-1)
                    self.save(updated);self.fresh();return row
            else:quiet=None;epochs=None;first=None
            need(current-started<13 and attempt<66);self.sleep(.2)
        need(False)

    def sender(self,store,ack_store):
        self.fresh();need(self.disk['quiet'] is not None)
        current,raw,physical=physical_state(self.store);need(typed_equal(current,self.disk))
        rows=self.history.load(self.disk['chunks']);final=deepcopy(self.disk['records'][-1]);final['phaseOriginal']=rows[final['phase']]['packet']
        payload=canonical(dict(createPeerReturnVersion=VERSION,scope=self.scope,actorBinding=self.binding,
            workerHostProcessIdentity=self.worker,sourcePath=str(self.store.path),sourceSha256=hashlib.sha256(raw).hexdigest(),
            final=final,quiet=self.disk['quiet']))
        identity=dict(runId=self.run,family=FAMILY,producerHostProcessIdentity=self.worker,originalRequestId=self.scope['requestId'])
        return ObserverReturnSender(store,ack_store,identity,payload,physical,guard=lambda:self.return_guard(raw,physical))

    def return_guard(self,raw,physical):
        self.bound();need(physical_state(self.store)[1:]==(raw,physical));return True
