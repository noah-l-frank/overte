"""Closed Chat input admission and original references; never witness facts."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import ExitStack,contextmanager
from copy import deepcopy
import math
from pathlib import Path
import time
import uuid

from adapters.chat_journey.samples import ChatSamples,ChatCacheAbsence
from adapters.chat_journey.stage_join import initial as initial_stage,opened as opened_stage
from adapters.chat_journey.erase_restore import references
from adapters.native_feature_observation import exact,fresh,integer,need,number
from adapters.normal_feature_state import context
from adapters.script_journey.history import pack,unpack,same
from feature_journeys.contract import identifier
from feature_journeys.fixtures import context as texts
from feature_journeys.phase_fixture import PhaseFixtureReader,validate as phase
from feature_journeys.scenarios import SCENARIOS,expand,VERSION as CONTRACT_VERSION

VERSION=3


def recipe(run):
    # Select only the fixed original inputs. Checkpoint state/evidence is never
    # consulted by admission, input dispatch or an independent publisher.
    return [dict(verb='baseline',inputs={})]+[dict(verb=row['verb'],inputs=expand(row['inputs'],texts(run))) for row in SCENARIOS['chat']['steps']]


def validate_flow(value):
    exact(value,{'chatFlowInputsVersion','contractVersion','runId','fixtureUrl','binding','peerBinding','transcripts','baselineTranscripts','payload'})
    need(type(value['chatFlowInputsVersion']) is int and value['chatFlowInputsVersion']==VERSION
        and type(value['contractVersion']) is int and value['contractVersion']==CONTRACT_VERSION)
    identifier(value['runId']);context(value['binding']);context(value['peerBinding'])
    need(type(value['fixtureUrl']) is str and type(value['transcripts']) is list and len(value['transcripts'])==3
        and type(value['baselineTranscripts']) is list and len(value['baselineTranscripts'])==3
        and len(set(value['transcripts']+value['baselineTranscripts']))==6
        and all(type(name) is str and Path(name).name==name and name not in ('','.','..') for name in value['transcripts']+value['baselineTranscripts']))
    rows=unpack(value['payload']);need(1<=len(rows)<=26);original=None;tickets=set();previous_refs=None;queries=set()
    for index,row in enumerate(rows):
        exact(row,{'ticket','verb','inputs','phase','before','after','references'})
        identifier(row['ticket']);need(row['ticket'] not in tickets);tickets.add(row['ticket'])
        need(same(dict(verb=row['verb'],inputs=row['inputs']),recipe(value['runId'])[index])
            and row['phase'] in ('issued','completed') and (index==len(rows)-1 or row['phase']=='completed'))
        for key in ('before','after'):
            status=row[key]
            if status is None:need(key=='after' and row['phase']=='issued');continue
            phase(status,run=value['runId'],area='chat',request=status['requestId'],epoch=status['capturedEpochMs'],previous=original)
            need(status['active'] and len(status['activations'])==index+1)
            for entry,step in zip(status['activations'],rows):
                need(entry['ticket']==step['ticket'] and same(entry['stimulus'],dict(verb=step['verb'],inputs=step['inputs'])))
            original=status
        refs=row['references']
        if row['phase']=='issued':need(row['after'] is None and refs is None)
        else:
            need(row['after'] is not None and type(refs) is list and len(refs)==2)
            if previous_refs is not None and index>1:need(all(old['index']<new['index'] for old,new in zip(previous_refs,refs)))
            previous_refs=refs
            for ref in refs:
                exact(ref,{'index','ticket','queries','epochs'});identifier(ref['ticket'])
                need(integer(ref['index']) and type(ref['queries']) is list and len(ref['queries'])==4
                    and type(ref['epochs']) is list and len(ref['epochs'])==4 and all(integer(epoch,1) for epoch in ref['epochs']))
                need(min(ref['epochs'][index] for index in (0,2,3))>=math.ceil(row['before']['capturedEpochMs']))
                for nonce in ref['queries']:
                    identifier(nonce);need(nonce not in queries);queries.add(nonce)
    return rows


def fresh_roles(roles,started,now):
    clocks=[]
    for role in roles:
        for reader in (role.primary,role.peer,role.view,role.lifecycle):need(reader.guard() is not False)
        frame=role.frames[-1]
        for reader,oldest in ((role.primary,min(frame[key]['capturedEpochMs'] for key in ('primary','view','lifecycle'))),(role.peer,frame['peer']['capturedEpochMs'])):
            measured=now();epoch=reader.clock_ms();fresh(oldest,epoch);clocks.append((measured,epoch,oldest))
    finished=now();need(finished-started<=1.5 and all(epoch-oldest+math.ceil((finished-measured)*1000)<=1500 for measured,epoch,oldest in clocks))


class ChatFlowInputs:
    def __init__(self,source,roles,store,witness_store,*,initial_roles,initial_witness_store,monotonic=time.monotonic):
        need(isinstance(source,PhaseFixtureReader) and source.area=='chat' and type(roles) is tuple and len(roles)==2
            and all(isinstance(role,ChatSamples) and role.vr and not role.component_only and role.run==source.run for role in roles)
            and roles[0].role=='primary' and roles[1].role=='actor' and roles[0].binding==roles[1].binding
            and roles[0].peer_binding==roles[1].peer_binding and all(a is b for a,b in zip(roles[0].locks,roles[1].locks))
            and type(initial_roles) is tuple and len(initial_roles)==2
            and all(isinstance(role,ChatCacheAbsence) and role.vr and not role.component_only and role.run==source.run
                and role.binding==roles[0].binding and role.peer_binding==roles[0].peer_binding for role in initial_roles)
            and initial_roles[0].role=='primary' and initial_roles[1].role=='actor'
            and all(a is b for role in initial_roles for a,b in zip(roles[0].locks,role.locks))
            and len({store.path,witness_store.path,initial_witness_store.path,*[role.store.path for role in roles+initial_roles]})==7
            and all(path.parent==store.path.parent for path in (witness_store.path,initial_witness_store.path,*[role.store.path for role in roles+initial_roles]))
            and callable(monotonic))
        self.source,self.roles,self.initial_roles,self.store=source,roles,initial_roles,store;self.monotonic=monotonic;self.last_clock=None
        self.scope=dict(chatFlowInputsVersion=VERSION,contractVersion=CONTRACT_VERSION,runId=source.run,fixtureUrl=source.fixture_url,binding=roles[0].binding,
            peerBinding=roles[0].peer_binding,transcripts=[*[role.store.path.name for role in roles],witness_store.path.name],
            baselineTranscripts=[*[role.store.path.name for role in initial_roles],initial_witness_store.path.name])
        self.previous=store.read();self.rows=[]
        if self.previous is not None:
            need(all(same(self.previous.get(key),value) for key,value in self.scope.items()));self.rows=validate_flow(self.previous)
            for index,row in enumerate(self.rows):
                if row['references'] is not None:
                    self.originals(row['references'],initial=index==0)
                    if index==1:self.stage(row['references'])

    def now(self):
        value=self.monotonic();need(number(value,0,1e15) and (self.last_clock is None or value>=self.last_clock));self.last_clock=value;return value

    @contextmanager
    def session(self):
        with ExitStack() as held:
            for lock in sorted(self.roles[0].locks,key=lambda value:str(value.path)):held.enter_context(lock.held())
            yield

    def originals(self,refs,*,initial=False):
        for role,reference in zip(self.initial_roles if initial else self.roles,refs):
            need(integer(reference['index'],0,len(role.frames)-1));frame=role.frames[reference['index']]
            need(reference==dict(index=reference['index'],ticket=frame['ticket'],
                queries=[frame[key].get('commandId',frame[key].get('requestId')) for key in ('primary','peer','view','lifecycle')],
                epochs=[frame[key]['capturedEpochMs'] for key in ('primary','peer','view','lifecycle')])
                and 'state' in role._compose(frame))

    def stage(self,refs):
        need(self.rows and self.rows[0]['phase']=='completed')
        for initial,active,before,after in zip(self.initial_roles,self.roles,self.rows[0]['references'],refs):
            opened_stage(initial.frames[before['index']],active.frames[after['index']])

    def save(self):
        self.roles[0].locks[0].assert_held();need(same(self.store.read(),self.previous))
        value={**self.scope,'payload':pack(self.rows)};validate_flow(value);self.store.write(value,self.previous)
        need(same(self.store.read(),value));self.previous=deepcopy(value)

    def begin(self,active):
        self.roles[0].locks[0].assert_held()
        need(not self.rows or self.rows[-1]['phase']=='completed')
        index=len(self.rows);need(index<26 and same(active['status'],self.source.previous)
            and same(dict(verb=active['verb'],inputs=active['inputs']),recipe(self.source.run)[index]))
        self.rows.append(dict(ticket=active['ticket'],verb=active['verb'],inputs=deepcopy(active['inputs']),phase='issued',
            before=deepcopy(active['status']),after=None,references=None));self.save()

    def finish(self):
        self.roles[0].locks[0].assert_held();need(self.rows and self.rows[-1]['phase']=='issued')
        row=self.rows[-1];started=self.now();barrier=math.ceil(row['before']['capturedEpochMs'])
        roles=self.initial_roles if len(self.rows)==1 else self.roles
        measured=[role.read(uuid.uuid4().hex,barrier) for role in roles];need(measured[0]['state']==measured[1]['state'])
        if len(self.rows)==1:
            need(all(value['resources']==[] for value in measured))
            for role in roles:initial_stage(role.frames[-1])
        elif len(self.rows)==2:self.stage(references(roles))
        confirmed=self.source.read(row['before']);need(confirmed['ticket']==row['ticket']
            and same(dict(verb=confirmed['verb'],inputs=confirmed['inputs']),dict(verb=row['verb'],inputs=row['inputs'])))
        row.update(phase='completed',after=deepcopy(confirmed['status']),references=references(roles));self.save()
        result=deepcopy(measured);fresh_roles(roles,started,self.now);return result
