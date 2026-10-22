"""Durable normal refresh/search joined to original consumed directory provenance.

The parent owns the open Places page, selected origin and input/source lock.
Arrival, app restart, independent publication and final retirement remain separate.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import re
import time
from adapters.native_feature_observation import exact,integer,need,number
from adapters.native_navigation_directory import validate,continuation,profile,joined_directory
from adapters.native_navigation_replies import origin
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.normal_ui import NativeUIError
from adapters.script_journey.history import pack,unpack
from adapters.token_places_ui import TokenPlacesUI,snapshot,sha
from adapters.token_create_ui import scope,nonce
from feature_journeys.fixtures import context as fixture_context
from feature_journeys.navigation_fixture import configuration,validate_status

VERSION=1

class NavigationDirectory:
    def __init__(self,ui_factory,native,status,path,run,binding,provider_instance,provider_inputs,owned_origin,source_profile,guard,
                 *,monotonic=time.monotonic,sleep=time.sleep):
        need(all(callable(f) for f in (ui_factory,status,guard,monotonic,sleep)) and type(run) is str and re.fullmatch('[0-9a-f]{32}',run))
        context(binding);configuration(provider_inputs);profile(source_profile);origin(owned_origin)
        need(binding['sourceRevision']==provider_inputs['sourceRevision']==source_profile['sourceRevision']
             and native.pid==int(binding['processIdentity'].split(':',1)[0]))
        self.native,self.status,self.run,self.binding=native,status,run,deepcopy(binding)
        self.provider_instance,self.inputs,self.origin,self.profile=provider_instance,deepcopy(provider_inputs),owned_origin,deepcopy(source_profile)
        self.guard,self.monotonic,self.sleep=guard,monotonic,sleep;self.clock=self.deadline=None
        self.store=PrivateFeatureState(path);self.disk=self.store.read();self.state=None
        if self.disk is not None:
            exact(self.disk,{'navigationDirectoryOwnerVersion','runId','binding','providerInstance','providerInputs','origin','profile','payload'})
            need(type(self.disk['navigationDirectoryOwnerVersion']) is int and self.disk['navigationDirectoryOwnerVersion']==VERSION
                 and self.disk['runId']==run and self.disk['binding']==binding and self.disk['providerInstance']==provider_instance
                 and self.disk['providerInputs']==provider_inputs and self.disk['origin']==owned_origin and self.disk['profile']==source_profile)
            rows=unpack(self.disk['payload']);need(len(rows)==1);self.validate_state(rows[0]);self.state=rows[0]
        self.ui=ui_factory(self.intent);need(isinstance(self.ui,TokenPlacesUI) and self.ui.run==run)
    def now(self):
        need(self.guard() is not False);value=self.monotonic()
        need(number(value,0,1e15) and (self.clock is None or value>=self.clock) and (self.deadline is None or value<=self.deadline))
        self.clock=value;return value
    def archive(self,group):
        exact(group,{'ui','native','provider'});snapshot(group['ui']);native=group['native']
        need(type(native) is dict)
        validate(native,dict(schemaVersion=1,commandId=native.get('commandId'),action='feature-navigation-directory',runId=self.run),
            self.native.pid,native.get('capturedEpochMs'))
        validate_status(group['provider'],instance=self.provider_instance,run=self.run,inputs=self.inputs)
        ui=group['ui'];scope_=ui['scope'];frame=native['ui']
        need(scope_['instance']==frame['bridgeId']==self.binding['sessionId'] and scope_['processId']==self.native.pid
             and scope_['generation']==frame['generation'] and scope_['sequence']==frame['sequence']
             and 0<=native['capturedEpochMs']-ui['observedEpochMs']<=1500)
        pages=[r for r in ui['controls'] if r['id']=='places.page'];need(len(pages)==1)
        return pages[0]
    def advance(self,old,new):
        continuation(old['native'],new['native'])
        validate_status(new['provider'],instance=self.provider_instance,run=self.run,inputs=self.inputs,previous=old['provider'])
        need(all(new['ui']['scope'][k]>=old['ui']['scope'][k] for k in ('sequence','elapsedMs'))
             and new['ui']['observedEpochMs']>=old['ui']['observedEpochMs'])
    def validate_state(self,value):
        exact(value,{'baseline','last','queries','refreshTicket','afterEpochMs','proof','active'})
        a=self.archive(value['baseline']);b=self.archive(value['last'])
        if value['last']!=value['baseline']:self.advance(value['baseline'],value['last'])
        need(a['rootInstance']==b['rootInstance'] and a['componentSourceSha256']==b['componentSourceSha256']
             and value['baseline']['ui']['scope']['generation']==value['last']['ui']['scope']['generation']
             and a['tab']==b['tab']==0 and a['maturity']==b['maturity'] and not a['dialog']['visible'] and not b['dialog']['visible']
             and type(value['refreshTicket']) is str and re.fullmatch('[0-9a-f]{32}',value['refreshTicket'])
             and integer(value['afterEpochMs'],1) and type(value['queries']) is list and 1<=len(value['queries'])<=256
             and all(type(v) is str and re.fullmatch('[0-9a-f]{32}',v) for v in value['queries'])
             and len(set(value['queries']))==len(value['queries'])
             and all(value[k]['native']['commandId'] in value['queries'] for k in ('baseline','last')))
        active=value['active'];exact(active,{'ticket','verb','stage','pending','quiet'})
        need(type(active['ticket']) is str and re.fullmatch('[0-9a-f]{32}',active['ticket'])
             and active['verb'] in ('refresh','hidden','owned') and integer(active['stage'],0,2)
             and type(active['quiet']) is list and len(active['quiet'])<=8)
        if active['verb']=='refresh':need(active['ticket']==value['refreshTicket'])
        if active['pending'] is not None:
            p=active['pending'];exact(p,{'placesInputVersion','action','controlId','controlToken','scope'});scope(p['scope'])
            need(type(p['placesInputVersion']) is int and p['placesInputVersion']==1 and nonce(p['controlToken'])
                 and p['controlId']==('places.refresh' if active['verb']=='refresh' else 'places.search')
                 and p['action']==('replace' if active['stage']==1 else 'activate') and active['stage']<2
                 and p['scope']['instance']==self.binding['sessionId'] and p['scope']['processId']==self.native.pid)
        if value['proof'] is not None:
            exact(value['proof'],{'readId','messageId','rootId','revision'})
            need(all(type(value['proof'][k]) is str and re.fullmatch('[0-9a-f]{32}',value['proof'][k]) for k in ('readId','messageId','rootId'))
                 and integer(value['proof']['revision'],1))
        previous=None
        for group in active['quiet']:
            self.archive(group);self.effect(group,value);self.advance(value['baseline'],group)
            need(group['native']['commandId'] in value['queries'])
            if previous is not None:self.advance(previous,group);self.quiet_advance(previous,group)
            previous=group
        if active['quiet']:
            need(active['stage']==2 and active['pending'] is None and value['proof'] is not None and len(active['quiet'])>=3)
            a,b=active['quiet'][0],active['quiet'][-1]
            need(b['native']['capturedEpochMs']-a['native']['capturedEpochMs']>=3000
                 and b['ui']['observedEpochMs']-a['ui']['observedEpochMs']>=3000
                 and b['ui']['scope']['elapsedMs']-a['ui']['scope']['elapsedMs']>=3000)
            if value['last']['native']['sequence']==b['native']['sequence']:need(value['last']==b)
            else:self.advance(b,value['last'])
    def save(self,value):
        self.validate_state(value)
        disk=dict(navigationDirectoryOwnerVersion=VERSION,runId=self.run,binding=self.binding,providerInstance=self.provider_instance,
            providerInputs=self.inputs,origin=self.origin,profile=self.profile,payload=pack([value]))
        self.store.write(disk,self.disk);self.disk=deepcopy(disk);self.state=deepcopy(value)
    def intent(self,value):
        self.now();need(self.state is not None and self.state['active']['pending'] is None)
        current=deepcopy(self.state);current['active']['pending']=value;self.save(current)
    def sample(self):
        self.now();ui=self.ui.capture();status=self.status();native=self.native.read(self.run);self.now()
        group=dict(ui=ui,provider=status,native=native);page=self.archive(group)
        if self.state is not None:
            original=self.archive(self.state['baseline'])
            need(page['rootInstance']==original['rootInstance'] and page['componentSourceSha256']==original['componentSourceSha256']
                 and group['ui']['scope']['generation']==self.state['baseline']['ui']['scope']['generation']
                 and page['maturity']==original['maturity'] and page['tab']==0 and not page['dialog']['visible'])
            self.advance(self.state['last'],group)
            need(native['commandId'] not in self.state['queries'] and len(self.state['queries'])<256)
            current=deepcopy(self.state);current['last']=group;current['queries'].append(native['commandId']);self.save(current)
        return group
    def effect(self,group,state=None):
        state=self.state if state is None else state;active=state['active'];query='' if active['verb']=='refresh' else fixture_context(self.run)['hidden' if active['verb']=='hidden' else 'name']
        page=self.archive(group)
        need(page['querySha256']==sha(query) and page['queryLength']==len(query)
             and page['maturity']==self.archive(state['baseline'])['maturity'])
        proof=joined_directory(group['native'],group['ui'],group['provider'],run=self.run,ticket=active['ticket'],
            receipt_ticket=state['refreshTicket'],after_epoch=state['afterEpochMs'],owned_origin=self.origin,
            provider_instance=self.provider_instance,provider_inputs=self.inputs,source_profile=self.profile,visible=active['verb']!='hidden')
        identity=dict(readId=proof['read']['readId'],messageId=proof['message']['messageId'],rootId=proof['root']['rootId'],revision=proof['root']['revision'])
        if state['proof'] is not None:need(identity==state['proof'])
        else:
            need(identity['readId'] not in {r['readId'] for r in state['baseline']['native']['reads']}
                 and identity['messageId'] not in {m['messageId'] for m in state['baseline']['native']['messages']})
        return identity
    @staticmethod
    def quiet_advance(old,new):
        need(new['ui']['scope']['sequence']==old['ui']['scope']['sequence']
             and new['native']['capturedEpochMs']-old['native']['capturedEpochMs']<=1500)
    def act(self,ticket,verb):
        need(type(ticket) is str and re.fullmatch('[0-9a-f]{32}',ticket) and verb in ('refresh','hidden','owned') and self.deadline is None)
        self.deadline=self.now()+20
        try:return self.execute(ticket,verb)
        except NativeUIError:raise
        except Exception:raise NativeUIError('Original directory input remains unresolved') from None
        finally:self.deadline=None
    def execute(self,ticket,verb):
        if self.state is None:
            need(verb=='refresh');group=self.sample();page=self.archive(group)
            need(page['tab']==0 and not page['loading'] and not page['dispatchTimerRunning'] and page['queueCount']==0
                 and page['querySha256']==sha('') and 'everyone' in page['maturity'])
            self.save(dict(baseline=group,last=group,queries=[group['native']['commandId']],refreshTicket=ticket,
                afterEpochMs=group['ui']['observedEpochMs'],proof=None,
                active=dict(ticket=ticket,verb=verb,stage=0,pending=None,quiet=[])))
        active=self.state['active']
        if ticket!=active['ticket']:
            need(verb!='refresh' and active['quiet'] and active['pending'] is None)
            current=deepcopy(self.state);current['active']=dict(ticket=ticket,verb=verb,stage=0,pending=None,quiet=[]);self.save(current)
        need(self.state['active']['verb']==verb)
        if self.state['active']['quiet']:self.effect(self.sample());return dict(performed=True)
        while self.state['active']['stage']<2:
            active=self.state['active'];stage=active['stage']
            if active['pending'] is None:
                if stage==1 and verb=='refresh':
                    current=deepcopy(self.state);current['active']['stage']=2;self.save(current);break
                if stage==0:self.ui.input('places.refresh' if verb=='refresh' else 'places.search')
                else:self.ui.input('places.search','replace',fixture_context(self.run)['hidden' if verb=='hidden' else 'name'])
            pending=self.state['active']['pending']
            for attempt in range(81):
                group=self.sample();seq=group['ui']['scope']['sequence'];before=pending['scope']['sequence']
                need(before<=seq<=before+1)
                try:
                    need(seq==before+1)
                    if verb=='refresh' or stage==1:identity=self.effect(group)
                    else:
                        row=self.ui.row(group['ui'],'places.search');need(row is not None and row['focused']);identity=None
                    break
                except NativeUIError:
                    need(attempt<80);self.sleep(.1)
            current=deepcopy(self.state);current['active']['pending']=None;current['active']['stage']+=1
            if identity is not None:current['proof']=identity
            self.save(current)
        groups=[];start=self.now()
        for _ in range(8):
            group=self.sample();self.effect(group)
            if groups:self.quiet_advance(groups[-1],group)
            groups.append(group)
            if self.now()-start>=3:
                current=deepcopy(self.state);current['active']['quiet']=groups;self.save(current);return dict(performed=True)
            self.sleep(.5)
        raise NativeUIError('Original directory quiet state remains unresolved')
