"""Durable whole Places actions, over the existing original-token recipes.

This scoped owner requires an already owned open page. It provides eight
ordinary action recipes, not the complete Worlds act/observe/cleanup triple.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import time

from adapters.native_clock_join import digest
from adapters.native_feature_observation import exact,need,number
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.script_feature.history import pack,unpack,same
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.contract import arguments,identifier
from feature_journeys.phase_fixture import validate as phase_packet
from ios.adapters import places_controls as controls
from ios.adapters.navigation_fixture import NavigationFixtureReader
from ios.adapters.navigation_observation_owner import fixture_original
from ios.adapters.navigation_places_inputs import IOSPlacesFlow

VERSION=1
VERBS=frozenset(('bookmark-add-cancel','bookmark-add','bookmark-rename-cancel','bookmark-rename',
    'directory-search','directory-select','bookmark-visit','bookmark-delete'))


class NavigationPlacesActions:
    def __init__(self,store,binding,run,lock,guard,fixture,factory,*,monotonic=time.monotonic):
        need(isinstance(store,PrivateFeatureState) and isinstance(lock,ScriptSourceLock)
             and isinstance(fixture,NavigationFixtureReader) and all(callable(fn) for fn in (guard,factory,monotonic)))
        context(binding);identifier(run)
        need(store.path.name=='ios-navigation-places-actions.json' and lock.path==store.path.parent/'script-feature-sources.lock'
             and fixture.run==run and fixture.instance is not None and fixture.inputs['sourceRevision']==binding['sourceRevision'])
        self.store,self.binding,self.run,self.lock=store,deepcopy(binding),run,lock
        self.guard,self.fixture,self.factory,self.monotonic=guard,fixture,factory,monotonic
        self.started=self.last_clock=None;lock.assert_held();self.previous=store.read()
        self.state=None if self.previous is None else self.decode(self.previous);self.bound()

    def envelope(self,state):
        return dict(iosNavigationPlacesActionsVersion=VERSION,binding=self.binding,runId=self.run,payload=pack([state]))

    def validate_call(self,call):
        call=arguments('feature.world-navigation.act',call)
        need(call['runId']==self.run and call['fixtureUrl']==self.fixture.fixture_url and call['verb'] in VERBS)
        return call

    def decode(self,value):
        exact(value,{'iosNavigationPlacesActionsVersion','binding','runId','payload'})
        rows=unpack(value['payload']);need(len(rows)==1 and type(value['iosNavigationPlacesActionsVersion']) is int
             and value['iosNavigationPlacesActionsVersion']==VERSION and same(value,self.envelope(rows[0])))
        state=rows[0];exact(state,{'providerInstance','providerInputs','actions'})
        need(state['providerInstance']==self.fixture.instance and same(state['providerInputs'],self.fixture.inputs)
             and type(state['actions']) is list and 1<=len(state['actions'])<=32)
        tickets=set();previous_phase=previous_ui=None
        for index,row in enumerate(state['actions']):
            exact(row,{'phase','call','fixture','intents','observed'})
            call=self.validate_call(row['call']);ticket=call['ticket'];need(ticket not in tickets);tickets.add(ticket)
            need(row['phase'] in ('checking','issued','acknowledged')
                 and (index==len(state['actions'])-1 or row['phase']=='acknowledged')
                 and type(row['intents']) is list and len(row['intents'])<=32)
            phase=row['fixture']
            if phase is not None:
                fixture_original(phase,self.run,self.fixture.inputs,self.fixture.instance)
                if row['phase']!='checking':
                    need((phase['ticket'],phase['verb'])==(ticket,call['verb']) and same(phase['inputs'],call['inputs']))
                if previous_phase is not None:
                    packet=phase['originals']['phaseBefore']
                    phase_packet(packet,run=self.run,area='world-navigation',request=packet['requestId'],
                        epoch=packet['capturedEpochMs'],previous=previous_phase)
                previous_phase=phase['originals']['phaseAfter']
            if row['phase']!='checking':need(phase is not None)
            before=previous_ui
            for event in row['intents']:
                self.validate_intent(event,call)
                packet=event['original'];self.follow(before,packet)
                if before is not None and before is not previous_ui:
                    need(packet['scope']['sequence']==before['scope']['sequence']+1)
                before=packet
            if row['phase']=='acknowledged':
                packet=controls.snapshot(row['observed']);need(row['intents'])
                self.follow(before,packet);need(packet['scope']['sequence']==before['scope']['sequence']+1)
                previous_ui=packet
            else:need(row['observed'] is None)
        return state

    def validate_intent(self,event,call):
        exact(event,{'iosPlacesInputVersion','runId','controlId','action','value','call','original','reference'})
        need(type(event['iosPlacesInputVersion']) is int and event['iosPlacesInputVersion']==1
             and event['runId']==self.run and same(event['call'],call))
        current=controls.snapshot(event['original']);need(current['placesControlsVersion']==2
            and current['scope']['processId']==int(self.binding['processIdentity']))
        row=controls.reference(current,event['controlId'])
        need(same(row,event['reference']) and row['control']['enabled'] and row['control']['inputReady']
             and event['action'] in ('activate','replace'))
        if event['action']=='activate':need(event['value'] is None)
        else:
            from feature_journeys.fixtures import context as run_context
            ctx=run_context(self.run);need(row['control']['focused']
                and event['controlId'] in ('places.search','places.bookmark-name')
                and event['value'] in (ctx['name'],ctx['renamed'],ctx['hidden']))

    @staticmethod
    def follow(before,after):
        if before is None:return
        old,new=before['scope'],after['scope']
        need(all(old[key]==new[key] for key in ('instance','processId'))
             and new['sequence']>=old['sequence'] and new['observationSequence']>old['observationSequence']
             and new['sampleEpochMs']>=old['sampleEpochMs'] and new['elapsedMs']>=old['elapsedMs'])

    def bound(self):
        self.lock.assert_held();need(self.guard() is not False and same(self.store.read(),self.previous))
        now=self.monotonic();need(number(now,0,1e15) and (self.last_clock is None or now>=self.last_clock))
        self.last_clock=now
        if self.started is not None:need(now-self.started<30)
        if self.state is not None:need(self.state['providerInstance']==self.fixture.instance
            and same(self.state['providerInputs'],self.fixture.inputs))
        return now

    def save(self):
        self.bound();value=self.envelope(self.state);self.decode(value)
        self.store.write(value,self.previous);need(same(self.store.read(),value));self.previous=deepcopy(value);self.bound()

    def intent(self,value):
        self.bound();row=self.state['actions'][-1];need(row['phase']=='issued')
        self.validate_intent(value,row['call']);need(len(row['intents'])<32)
        row['intents'].append(deepcopy(value));self.save()

    def act(self,call):
        call=deepcopy(self.validate_call(call));self.bound();need(self.started is None);self.started=self.bound()
        try:
            if self.state is None:self.state=dict(providerInstance=self.fixture.instance,providerInputs=deepcopy(self.fixture.inputs),actions=[])
            rows=self.state['actions']
            if rows:
                last=rows[-1]
                if call['ticket'] in [row['call']['ticket'] for row in rows]:
                    need(last['phase']=='acknowledged' and same(last['call'],call));self.decode(self.previous)
                    return {'performed':True}
                need(last['phase']=='acknowledged')
            need(len(rows)<32);row=dict(phase='checking',call=call,fixture=None,intents=[],observed=None)
            rows.append(row);self.save()
            row['fixture']=self.fixture.read();self.save()
            row['phase']='issued';self.save()
            previous=rows[-2]['observed'] if len(rows)>1 else None
            flow=self.factory(self.intent,previous);need(isinstance(flow,IOSPlacesFlow)
                and flow.lock is self.lock and same(flow.binding,self.binding) and flow.run==self.run
                and flow.intent==self.intent)
            flow.guard=self.bound
            flow.invoke(call);self.bound();need(flow.last is not None and row['intents'])
            row.update(phase='acknowledged',observed=deepcopy(flow.last));self.save()
            return {'performed':True}
        finally:self.started=None
