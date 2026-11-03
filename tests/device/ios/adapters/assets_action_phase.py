"""Original current shared action custody, without target/peer assertions.

Only the real input phase before/after a completed action is journaled. Tickets
are read from the independent fixture, never substituted from upload/marker
birth. A current action lease checks the live original before SDK sends; its
historical completed source remains readable after later actions are activated.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import time
from adapters.native_feature_observation import exact,integer,need
from adapters.native_clock_join import digest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.original_frame_store import OriginalFrameStore
from adapters.script_feature.history import same,pack,unpack
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.contract import identifier,typed_equal
from feature_journeys.fixtures import context as fixture_context
from feature_journeys.phase_fixture import PhaseFixtureReader,validate as phase_original
from feature_journeys.scenarios import SCENARIOS,VERSION as SCENARIO_VERSION,expand
from ios.adapters.assets_end_graph import AssetsFinalArchive

VERSION=1


def input_plan(run):
    return [dict(verb=row['verb'],inputs=expand(row['inputs'],fixture_context(run))) for row in SCENARIOS['assets']['steps']]


class AssetsActionPhases:
    def __init__(self,selected,store,locks,phase,*,historical=False,monotonic=time.monotonic):
        need(type(selected) is AssetsFinalArchive and isinstance(store,PrivateFeatureState) and set(locks)=={'primary','actor'}
            and all(isinstance(lock,ScriptSourceLock) for lock in locks.values()) and type(historical) is bool and callable(monotonic))
        self.selected,self.store,self.locks,self.phase,self.historical,self.monotonic=selected,store,locks,phase,historical,monotonic
        self.context=deepcopy(selected.context);self.binding=deepcopy(self.context['roles']['primary']['binding']);self.run=selected.run;self.role='primary'
        need(store.path==Path(self.context['roles']['primary']['stateRoot'])/('ios-assets-actions-'+self.run+'.json'))
        for role,lock in locks.items():need(lock.path==Path(self.context['roles'][role]['stateRoot'])/'script-feature-sources.lock')
        if not historical:
            need(isinstance(phase,PhaseFixtureReader) and phase.run==self.run and phase.area=='assets' and phase.fixture_url==self.context['fixtureUrl'])
        else:need(phase is None)
        self.originals=OriginalFrameStore(store.path.parent,self.binding,self.run,'primary',self.guard,self.intent,
            namespace='assets-action',schema_prefix='iosAssetsActionSource',monotonic=monotonic)
        self.previous=store.read();self.state=None
        if self.previous is not None:self.state=self.decode(self.previous)
    def guard(self):
        for lock in self.locks.values():lock.assert_held()
        self.selected.selected_guard();return True
    def live(self):self.guard();need(not self.historical and self.selected.state==dict(phase='selected'))
    def plan(self):return input_plan(self.run)
    def envelope(self):
        return dict(iosAssetsActionsVersion=VERSION,runId=self.run,selectedPair=self.selected.link(),scenarioVersion=SCENARIO_VERSION,
            inputPlanSha256=digest(self.plan()),payload=pack([self.state]))
    def save(self):
        self.live();need(same(self.store.read(),self.previous));value=self.envelope();self.store.write(value,self.previous);self.previous=deepcopy(value)
    def intent(self,kind,value):
        need(kind=='original' and self.state is not None and self.state['pending'] is not None)
        self.state['pending']['original']=deepcopy(value);self.save()
    def reserve(self):
        self.live();need(self.state is None);self.state=dict(records=[],pending=None,complete=False);self.save()
    def phase_packet(self,value,index,ticket):
        phase_original(value,run=self.run,area='assets',request=value['requestId'],epoch=value['capturedEpochMs'])
        need(value['active'] and value['instance']==self.context['inputPhaseOriginal']['instance'] and value['activations'])
        before=self.context['inputPhaseOriginal'];phase_original(value,run=self.run,area='assets',request=value['requestId'],epoch=value['capturedEpochMs'],previous=before)
        activations=value['activations'];initial=self.context['inputPhaseOriginal']['activations']
        need(len(activations)==len(initial)+index and typed_equal(activations[:len(initial)],initial))
        for number,activation in enumerate(activations[len(initial):],1):need(typed_equal(activation['stimulus'],self.plan()[number-1]))
        current=activations[-1];wanted=self.plan()[index-1]
        need(current['ticket']==ticket and typed_equal(current['stimulus'],wanted));return current
    def frame(self,value,index):
        exact(value,{'iosAssetsActionVersion','index','ticket','input','phaseBefore','phaseAfter'})
        need(type(value['iosAssetsActionVersion']) is int and value['iosAssetsActionVersion']==VERSION and type(value['index']) is int
            and value['index']==index and integer(index,1,len(self.plan())) and typed_equal(value['input'],self.plan()[index-1]))
        identifier(value['ticket']);self.phase_packet(value['phaseBefore'],index,value['ticket']);self.phase_packet(value['phaseAfter'],index,value['ticket'])
        phase_original(value['phaseAfter'],run=self.run,area='assets',request=value['phaseAfter']['requestId'],epoch=value['phaseAfter']['capturedEpochMs'],previous=value['phaseBefore'])
        need(typed_equal(value['phaseBefore']['activations'],value['phaseAfter']['activations']));return value
    def read(self,index):
        self.guard();need(self.state is not None and same(self.store.read(),self.previous) and same(self.envelope(),self.previous)
            and integer(index,1,len(self.state['records'])))
        ref=self.originals.expand(self.state['records'][index-1]);need(ref['index']==index);return self.frame(self.originals.read(ref),index)
    def decode(self,value):
        exact(value,{'iosAssetsActionsVersion','runId','selectedPair','scenarioVersion','inputPlanSha256','payload'})
        need(type(value['iosAssetsActionsVersion']) is int and value['iosAssetsActionsVersion']==VERSION and value['runId']==self.run
            and same(value['selectedPair'],self.selected.link()) and value['scenarioVersion']==SCENARIO_VERSION and value['inputPlanSha256']==digest(self.plan()))
        rows=unpack(value['payload']);need(len(rows)==1);state=rows[0];exact(state,{'records','pending','complete'})
        need(type(state['records']) is list and len(state['records'])<=len(self.plan()) and type(state['complete']) is bool)
        prior=None
        for index,ref in enumerate(state['records'],1):
            full=self.originals.expand(ref);need(full['index']==index);row=self.frame(self.originals.read(full),index)
            if prior is not None:
                phase_original(row['phaseBefore'],run=self.run,area='assets',request=row['phaseBefore']['requestId'],epoch=row['phaseBefore']['capturedEpochMs'],previous=prior['phaseAfter'])
            prior=row
        pending=state['pending']
        if pending is not None:
            exact(pending,{'index','ticket','before','after','original'});need(pending['index']==len(state['records'])+1 and integer(pending['index'],1,len(self.plan())))
            self.phase_packet(pending['before'],pending['index'],pending['ticket'])
            if pending['after'] is not None:self.frame(self.body(pending),pending['index'])
            if pending['original'] is not None:
                from ios.adapters.assets_model_sources import AssetsModelSources
                self.originals.original(pending['original']);AssetsModelSources.prefix(self,pending['original'])
        need(state['complete']==(len(state['records'])==len(self.plan()) and pending is None));return state
    def begin(self,index,ticket,verb,inputs):
        self.live();need(self.state is not None and self.state['pending'] is None and not self.state['complete']
            and integer(index,1,len(self.plan())) and index==len(self.state['records'])+1)
        identifier(ticket);need(typed_equal(dict(verb=verb,inputs=inputs),self.plan()[index-1]))
        packet=self.phase.status();self.phase_packet(packet,index,ticket)
        self.state['pending']=dict(index=index,ticket=ticket,before=packet,after=None,original=None);self.save();return AssetsActionScope(self,index,ticket)
    def body(self,pending):
        return dict(iosAssetsActionVersion=VERSION,index=pending['index'],ticket=pending['ticket'],input=deepcopy(self.plan()[pending['index']-1]),
            phaseBefore=deepcopy(pending['before']),phaseAfter=deepcopy(pending['after']))
    def current(self,index,ticket):
        self.live();need(same(self.store.read(),self.previous) and self.state is not None and same(self.envelope(),self.previous) and self.state['pending'] is not None)
        pending=self.state['pending'];need(pending['index']==index and pending['ticket']==ticket and pending['after'] is None and pending['original'] is None)
        packet=self.phase.status();self.phase_packet(packet,index,ticket)
        need(typed_equal(packet['activations'],pending['before']['activations']));return True
    def complete(self,scope):
        need(type(scope) is AssetsActionScope and scope.owner is self);scope.guard();pending=self.state['pending']
        packet=self.phase.status();pending['after']=packet;self.frame(self.body(pending),scope.index);self.save()
        ref=self.originals.write(scope.index,self.body(pending));self.state['records'].append(ref);self.state['pending']=None
        self.state['complete']=len(self.state['records'])==len(self.plan());self.save();return self.read(scope.index)
    def recover_completed(self):
        self.live();need(same(self.store.read(),self.previous) and self.state is not None and same(self.envelope(),self.previous) and self.state['pending'] is not None)
        pending=self.state['pending'];ref=pending['original'];need(ref is not None and ref['phase']=='saved' and pending['after'] is not None)
        body=self.originals.read(ref);self.frame(body,pending['index']);need(same(body,self.body(pending)))
        self.state['records'].append(self.originals.compact(ref));self.state['pending']=None
        self.state['complete']=len(self.state['records'])==len(self.plan());self.save();return self.read(len(self.state['records']))
    def ticket_for(self,index):return self.read(index)['ticket']


class AssetsActionScope:
    def __init__(self,owner,index,ticket):
        need(type(owner) is AssetsActionPhases and integer(index,1,len(owner.plan())));self.owner,self.index,self.ticket=owner,index,identifier(ticket)
    def guard(self):return self.owner.current(self.index,self.ticket)
    def runtime_guard(self,runtime,selector,binding=None):
        self.guard();roles=[role for role,info in self.owner.context['roles'].items() if info['target']==selector];need(len(roles)==1);role=roles[0]
        info=self.owner.context['roles'][role];need(runtime.state_path(selector).parent==Path(info['stateRoot']))
        self.owner.locks[role].assert_held()
        if binding is not None:need(same(binding,info['binding']))
        return True
