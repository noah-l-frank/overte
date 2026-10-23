"""Original normal Go To/404 child under the retained Navigation parent.

This supplies input ownership only; independent replies/modal/HTTP/pose sources
still establish all observed effects. No expected error or ACK is projected.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.chat_journey.source_chunks import json_digest
from adapters.native_feature_observation import exact,need,number
from adapters.navigation_missing import NavigationMissing
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_journey.history import same
from feature_journeys.contract import identifier
from openxr_input.controller_protocol import validate_envelope

VERSION=1


class NavigationMissingJoin:
    def __init__(self,parent,lookup,path):
        need(isinstance(lookup,NavigationMissing) and lookup.run==parent.run and same(lookup.binding,parent.binding)
            and lookup.ui.normal.io is parent.source.normal.io.original and lookup.navigation.io is parent.transport
            and lookup.provider==parent.source.provider_instance and lookup.inputs==parent.source.inputs
            and lookup.origin==parent.source.origin)
        self.parent,self.lookup=parent,lookup;self.store=PrivateFeatureState(path)
        previous=parent.transit();need(previous.state is not None and previous.state['phase']=='closed')
        self.prior_close=deepcopy(previous.state['controllers']['close']['envelope'])
        self.prior_sha=previous.state['closeSha256']
        self.anchor=self.anchor_sha=None;self.disk=self.store.read();self.state=None
        if self.disk is not None:self.load()

    def context(self,*,memory_only=False):
        p=self.parent;p.lock.assert_held();p.control()
        need(p.role=='primary' and same(p.state,p.disk) and p.state['phase']=='acting'
            and p.state['active']['verb']=='navigate-missing' and p.state['active']['stage']=='missing')
        if not memory_only:
            need(same(p.store.read(),p.disk) and same(self.lookup.store.read(),self.lookup.disk))

    def validate(self,value):
        exact(value,{'navigationMissingJoinVersion','runId','binding','parentScopeSha256','priorCloseSha256','ticket','phase','qml','controllers','lookupSha256'})
        p=self.parent;identifier(value['ticket'])
        need(type(value['navigationMissingJoinVersion']) is int and value['navigationMissingJoinVersion']==VERSION
            and value['runId']==p.run and same(value['binding'],p.binding) and value['parentScopeSha256']==p.scope_sha
            and value['priorCloseSha256']==self.prior_sha and value['phase'] in ('issued','visible')
            and type(value['qml']) is list and len(value['qml'])<=40 and type(value['controllers']) is list and len(value['controllers'])<=2
            and (value['lookupSha256'] is not None)==(value['phase']=='visible')
            and (any(row['ticket']==value['ticket'] and row['verb']=='navigate-missing' for row in p.state['completed'])
                 or p.state['active'] is not None and p.state['active']['ticket']==value['ticket'] and p.state['active']['verb']=='navigate-missing'))
        for command in value['qml']:need(any(same(command,row) for row in p.state['deliveries']))
        previous=self.prior_close;kinds=[]
        for record in value['controllers']:
            exact(record,{'envelope','sha256','anchor'});envelope=record['envelope'];validate_envelope(envelope,p.session.profile)
            anchor=record['anchor'];exact(anchor,{'kind','operation','arguments','hostMonotonic','nativeEpochMs','fixtureEpochMs'})
            need(anchor['kind'] in ('open','reopen') and anchor['kind'] not in kinds and anchor['operation']=='tablet.open'
                and anchor['arguments']==dict(holdMilliseconds=1000) and number(anchor['hostMonotonic'],0,1e15)
                and number(anchor['nativeEpochMs'],1,1e15) and number(anchor['fixtureEpochMs'],1,1e15)
                and -250<=anchor['nativeEpochMs']-anchor['fixtureEpochMs']<=1500
                and len(envelope['commands'])==1 and envelope['commands'][0]['operation']==anchor['operation']
                and same(envelope['commands'][0]['arguments'],anchor['arguments'])
                and envelope['sessionNonce']==previous['sessionNonce'] and type(envelope['sequence']) is int
                and envelope['sequence']==previous['sequence']+1 and record['sha256']==json_digest(envelope))
            kinds.append(anchor['kind']);previous=envelope
        need(not kinds or kinds[0]=='open')
        if value['lookupSha256'] is not None:
            need(self.lookup.state is not None and self.lookup.state['phase']=='visible'
                and self.lookup.state['ticket']==value['ticket'] and self.lookup.disk is not None
                and value['lookupSha256']==json_digest(self.lookup.disk) and self.lookup.state['joined'] is not None and kinds)

    def load(self):
        value=self.store.read();need(value is not None);self.validate(value);self.disk=deepcopy(value);self.state=deepcopy(value)

    def save(self,value):
        self.parent.lock.assert_held();self.validate(value);self.store.write(value,self.disk);self.disk=deepcopy(value);self.state=deepcopy(value)

    def record_qml(self,command):
        self.context();need(self.state['phase']=='issued' and self.lookup.state['pending']['kind']=='qt')
        current=deepcopy(self.state);current['qml'].append(deepcopy(command));self.save(current)

    def before_controller(self,operation):
        self.context();pending=self.lookup.state['pending']
        need(operation=='tablet.open' and self.state['phase']=='issued' and pending is not None and pending['kind'] in ('open','reopen')
            and not any(row['anchor']['kind']==pending['kind'] for row in self.state['controllers']))
        p=self.parent;current=p.fence()
        self.anchor=dict(kind=pending['kind'],operation=operation,arguments=dict(holdMilliseconds=1000),hostMonotonic=p.now(),
            nativeEpochMs=p.source.clock_ms(),fixtureEpochMs=current['status']['capturedEpochMs'])
        self.anchor_sha=json_digest(self.anchor);self.age()

    def age(self):
        # Session callbacks only validate retained original memory, host CAS and
        # monotonic age. No HTTP, source, SDK, native guard or Session reentry.
        self.context(memory_only=True)
        need(self.anchor is not None and self.anchor_sha==json_digest(self.anchor))
        a=self.anchor;now=self.parent.now()
        need(now>=a['hostMonotonic'] and max(a['nativeEpochMs']-a['fixtureEpochMs'],0)+(now-a['hostMonotonic'])*1000<=1500)

    def intent(self,envelope):
        self.age();need(not any(row['anchor']['kind']==self.anchor['kind'] for row in self.state['controllers']))
        current=deepcopy(self.state);current['controllers'].append(dict(envelope=deepcopy(envelope),sha256=json_digest(envelope),anchor=deepcopy(self.anchor)))
        self.save(current);self.before_publish(envelope)

    def before_publish(self,envelope):
        self.age();record=self.state['controllers'][-1]
        need(same(record['anchor'],self.anchor) and record['sha256']==json_digest(envelope) and same(record['envelope'],envelope))

    def receipt(self):
        need(self.state is not None and self.state['phase']=='visible');self.validate(self.state)
        return dict(ticket=self.lookup.state['ticket'],afterEpochMs=self.lookup.state['submitEpochMs'])

    def act(self,ticket):
        self.context()
        if self.state is None:
            self.save(dict(navigationMissingJoinVersion=VERSION,runId=self.parent.run,binding=deepcopy(self.parent.binding),
                parentScopeSha256=self.parent.scope_sha,priorCloseSha256=self.prior_sha,ticket=ticket,phase='issued',qml=[],controllers=[],lookupSha256=None))
        need(self.state['ticket']==ticket)
        if self.state['phase']=='issued':
            self.parent.fence();self.lookup.act(ticket)
            current=deepcopy(self.state);current.update(phase='visible',lookupSha256=json_digest(self.lookup.disk));self.save(current)
        self.parent.fence();return dict(performed=True)
