"""Normal original OK/retirement and existing Close-v2 under one parent.

Lookup/dismissal remain original immutable source owners. No synthetic Transit,
callback acknowledgement, forced QObject destruction or second close system.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.chat_journey.source_chunks import json_digest
from adapters.native_feature_observation import exact,need,number
from adapters.navigation_error_dismissal import NavigationErrorDismissal
from adapters.normal_feature_state import PrivateFeatureState
from adapters.pico4.navigation_missing_join import NavigationMissingJoin
from adapters.pico4.navigation_lookup_close import NavigationDismissedLookup
from adapters.pico4.navigation_close import NavigationTabletClose
from adapters.pico4.normal_scripts import PicoScriptIO
from adapters.pico4.graphics_source import PicoGraphicsSource
from adapters.script_journey.history import same
from adapters.token_script_ui import TokenScriptUI
from feature_journeys.contract import identifier
from openxr_input.controller_protocol import validate_envelope

VERSION=1


class NavigationDismissalJoin:
    def __init__(self,parent,missing,dismissal,normal,graphics,path):
        need(isinstance(missing,NavigationMissingJoin) and missing.parent is parent and missing.state is not None and missing.state['phase']=='visible'
            and isinstance(dismissal,NavigationErrorDismissal) and isinstance(normal,TokenScriptUI) and isinstance(normal.io,PicoScriptIO)
            and isinstance(graphics,PicoGraphicsSource) and dismissal.run==parent.run and same(dismissal.binding,parent.binding)
            and dismissal.ui.io.original is normal.io is parent.source.normal.io.original
            and missing.lookup.navigation is normal.io.navigation and dismissal.provider_instance==missing.lookup.provider
            and dismissal.inputs==missing.lookup.inputs and dismissal.origin==missing.lookup.origin)
        self.parent,self.missing,self.lookup,self.dismissal=parent,missing,missing.lookup,dismissal
        self.normal,self.graphics=normal,graphics;self.store=PrivateFeatureState(path);self.disk=self.store.read();self.state=None
        self.missing_sha=json_digest(missing.state);self.lookup_sha=json_digest(self.lookup.disk)
        self.prior=deepcopy(missing.state['controllers'][-1]['envelope']);self.close_owner=None
        self.anchor=self.anchor_sha=None
        if self.disk is not None:self.load()

    def context(self,*,memory_only=False):
        p=self.parent;p.lock.assert_held();p.control()
        need(p.role=='primary' and same(p.state,p.disk) and p.state['phase']=='acting'
            and p.state['active']['verb']=='dismiss-error' and p.state['active']['stage']=='dismiss')
        need(json_digest(self.missing.state)==self.missing_sha and json_digest(self.lookup.disk)==self.lookup_sha)
        if not memory_only:need(same(p.store.read(),p.disk) and same(self.lookup.store.read(),self.lookup.disk)
            and same(self.dismissal.store.read(),self.dismissal.disk))

    def validate(self,value):
        exact(value,{'navigationDismissalJoinVersion','runId','binding','parentScopeSha256','ticket','missingSha256','lookupSha256',
            'phase','qml','controller','dismissalSha256','closeSha256'})
        p=self.parent;identifier(value['ticket'])
        need(type(value['navigationDismissalJoinVersion']) is int and value['navigationDismissalJoinVersion']==VERSION
            and value['runId']==p.run and same(value['binding'],p.binding) and value['parentScopeSha256']==p.scope_sha
            and value['missingSha256']==self.missing_sha and value['lookupSha256']==self.lookup_sha
            and value['phase'] in ('dismiss-issued','dismissed','close-issued','closed')
            and type(value['qml']) is list and len(value['qml'])<=1
            and (value['dismissalSha256'] is not None)==(value['phase']!='dismiss-issued')
            and (value['closeSha256'] is not None)==(value['phase']=='closed')
            and (any(row['ticket']==value['ticket'] and row['verb']=='dismiss-error' for row in p.state['completed'])
                or p.state['active'] is not None and p.state['active']['ticket']==value['ticket'] and p.state['active']['verb']=='dismiss-error'))
        for command in value['qml']:
            need(any(same(command,row) for row in p.state['deliveries']) and self.dismissal.state is not None and self.dismissal.state['input'] is not None)
            original=self.dismissal.state['input'];scope=original['scope']
            need(command['controlId']==original['controlId'] and command['controlToken']==original['controlToken'] and command['action']=='activate'
                and command['bridgeId']==scope['instance'] and command['generation']==scope['generation'] and command['sequence']==scope['sequence']+1)
        if value['dismissalSha256'] is not None:
            need(self.dismissal.state is not None and self.dismissal.state['phase']=='complete'
                and self.dismissal.state['ticket']==value['ticket'] and self.dismissal.state['lookupTicket']==self.lookup.state['ticket']
                and self.dismissal.state['afterEpochMs']==self.lookup.state['submitEpochMs']
                and self.dismissal.state['joined']==self.lookup.state['joined'] and value['dismissalSha256']==json_digest(self.dismissal.disk)
                and value['qml'])
        record=value['controller']
        if record is not None:
            exact(record,{'envelope','sha256','anchor'});envelope=record['envelope'];validate_envelope(envelope,p.session.profile)
            anchor=record['anchor'];exact(anchor,{'operation','arguments','hostMonotonic','nativeEpochMs','fixtureEpochMs'})
            need(value['phase'] in ('close-issued','closed') and anchor['operation']=='tablet.close' and anchor['arguments']==dict(holdMilliseconds=1000)
                and number(anchor['hostMonotonic'],0,1e15) and number(anchor['nativeEpochMs'],1,1e15) and number(anchor['fixtureEpochMs'],1,1e15)
                and -250<=anchor['nativeEpochMs']-anchor['fixtureEpochMs']<=1500 and len(envelope['commands'])==1
                and envelope['commands'][0]['operation']==anchor['operation'] and same(envelope['commands'][0]['arguments'],anchor['arguments'])
                and envelope['sessionNonce']==self.prior['sessionNonce'] and type(envelope['sequence']) is int
                and envelope['sequence']==self.prior['sequence']+1 and record['sha256']==json_digest(envelope))
        if value['phase']=='closed':
            owner=self.close_original()
            need(record is not None and owner.state is not None and owner.state['phase']=='closed' and owner.source_kind=='dismissed-lookup'
                and value['closeSha256']==json_digest(owner.disk))

    def load(self):
        value=self.store.read();need(value is not None);self.validate(value);self.disk=deepcopy(value);self.state=deepcopy(value)

    def save(self,value):
        self.parent.lock.assert_held();self.validate(value);self.store.write(value,self.disk);self.disk=deepcopy(value);self.state=deepcopy(value)

    def record_qml(self,command):
        self.context();need(self.state['phase']=='dismiss-issued' and self.dismissal.state['phase']=='pending' and not self.state['qml'])
        current=deepcopy(self.state);current['qml'].append(deepcopy(command));self.save(current)

    def before_controller(self,operation):
        self.context();need(operation=='tablet.close' and self.state['phase']=='close-issued' and self.state['controller'] is None
            and self.close_original().state is not None and self.close_original().state['phase']=='closing')
        p=self.parent;current=p.fence()
        self.anchor=dict(operation=operation,arguments=dict(holdMilliseconds=1000),hostMonotonic=p.now(),
            nativeEpochMs=p.source.clock_ms(),fixtureEpochMs=current['status']['capturedEpochMs'])
        self.anchor_sha=json_digest(self.anchor);self.age()

    def age(self):
        # Original Session publication remains strictly host/CAS/memory only.
        self.context(memory_only=True);need(self.anchor is not None and self.anchor_sha==json_digest(self.anchor))
        a=self.anchor;now=self.parent.now()
        need(now>=a['hostMonotonic'] and max(a['nativeEpochMs']-a['fixtureEpochMs'],0)+(now-a['hostMonotonic'])*1000<=1500)

    def intent(self,envelope):
        self.age();need(self.state['controller'] is None)
        current=deepcopy(self.state);current['controller']=dict(envelope=deepcopy(envelope),sha256=json_digest(envelope),anchor=deepcopy(self.anchor))
        self.save(current);self.before_publish(envelope)

    def before_publish(self,envelope):
        self.age();record=self.state['controller'];need(record is not None and same(record['anchor'],self.anchor)
            and record['sha256']==json_digest(envelope) and same(record['envelope'],envelope))

    def close_original(self):
        if self.close_owner is None:
            proxy=NavigationDismissedLookup(self.lookup,self.dismissal)
            self.close_owner=NavigationTabletClose(proxy,self.normal,self.graphics,self.store.path.with_name('navigation-prefix-dismissal-close.json'),
                self.parent.source.guard,monotonic=self.parent.monotonic,sleep=self.parent.source.normal.sleep)
        return self.close_owner

    def act(self,ticket):
        self.context()
        if self.state is None:
            self.save(dict(navigationDismissalJoinVersion=VERSION,runId=self.parent.run,binding=deepcopy(self.parent.binding),
                parentScopeSha256=self.parent.scope_sha,ticket=ticket,missingSha256=self.missing_sha,lookupSha256=self.lookup_sha,
                phase='dismiss-issued',qml=[],controller=None,dismissalSha256=None,closeSha256=None))
        need(self.state['ticket']==ticket)
        if self.state['phase']=='dismiss-issued':
            self.parent.fence();self.dismissal.act(ticket,self.lookup.state['submitEpochMs'],lookup_ticket=self.lookup.state['ticket'])
            current=deepcopy(self.state);current.update(phase='dismissed',dismissalSha256=json_digest(self.dismissal.disk));self.save(current);self.parent.fence()
        if self.state['phase']=='dismissed':
            current=deepcopy(self.state);current['phase']='close-issued';self.save(current);self.parent.fence()
        if self.state['phase']=='close-issued':
            owner=self.close_original();owner.close(ticket)
            current=deepcopy(self.state);current.update(phase='closed',closeSha256=json_digest(owner.disk));self.save(current)
        self.parent.fence();return dict(performed=True)
