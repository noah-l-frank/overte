"""Original Worlds admission and ordinary active-run action coordination.

This is an internal vertical coordinator. Public observation, paired final
restoration and capability admission remain gated until their whole-run joins
are integrated. Child input journals, rather than this parent's ACK, determine
whether an interrupted operation may advance without resending an input.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
import time

from adapters.native_clock_join import digest
from adapters.native_feature_observation import exact,need,number
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import pack,unpack,same
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.contract import arguments,identifier
from feature_journeys.witness import Client
from ios.adapters.navigation_admission_owner import NavigationAdmissionOwner
from ios.adapters.navigation_fixture import NavigationFixtureReader
from ios.adapters.navigation_places_actions import VERBS as PLACE_VERBS
from ios.adapters.navigation_runtime import IOSNavigationRuntime

VERSION=1


class NavigationFeaturePending(NativeUIError):pass


class IOSNavigationFeature:
    def __init__(self,runtime,selector,client,run,root,*,role='primary',
                 epoch_ms=lambda:time.time()*1000,monotonic=time.monotonic,sleep=time.sleep):
        need(isinstance(runtime,IOSNavigationRuntime) and isinstance(client,Client)
            and role in ('primary','actor') and all(callable(fn) for fn in (epoch_ms,monotonic,sleep)))
        self.runtime,self.selector,self.client,self.run,self.role=runtime,selector,client,identifier(run),role
        self.root=Path(root);need(self.root.is_absolute() and self.root.resolve()==self.root and self.root.is_dir())
        PrivateFeatureState(self.root/'navigation-root-check')._parent()
        self.store=PrivateFeatureState(runtime.state_path(selector).with_name('ios-navigation-feature.json'))
        self.lock=ScriptSourceLock(self.store.path.with_name('script-feature-sources.lock'))
        self.fixture=NavigationFixtureReader(client,run,epoch_ms=lambda:int(epoch_ms()),monotonic=monotonic)
        self.epoch_ms,self.monotonic,self.sleep=epoch_ms,monotonic,sleep
        self.previous=self.state=None;self.deadline=self.last_clock=self.operation_clock=None

    def clock(self):
        now=self.monotonic();need(number(now,0,1e15) and (self.last_clock is None or now>=self.last_clock)
            and (self.deadline is None or now<self.deadline))
        if self.operation_clock is not None:
            first=self.operation_clock;epoch=self.epoch_ms()
            need(number(now,first['monotonic'],first['monotonic']+30) and now-first['monotonic']<30
                and number(epoch,first['epochMs'],first['epochMs']+30000) and epoch-first['epochMs']<30000
                and abs(epoch-first['epochMs']-(now-first['monotonic'])*1000)<=250)
        self.last_clock=now;return now

    @contextmanager
    def held(self):
        outer=self.deadline;now=self.clock();self.deadline=now+30 if outer is None else min(outer,now+30)
        error=None
        try:
            # Retain exceptions across ScriptSourceLock's context manager.
            with self.lock.held():
                try:yield;self.clock()
                except BaseException as caught:error=caught
            if error is not None:raise error
        finally:self.deadline=outer

    def envelope(self,state):
        return dict(iosNavigationFeatureVersion=VERSION,runId=self.run,artifactRoot=str(self.root),payload=pack([state]))

    def load(self):
        self.lock.assert_held();self.previous=self.store.read()
        if self.previous is None:self.state=None;return
        exact(self.previous,{'iosNavigationFeatureVersion','runId','artifactRoot','payload'})
        rows=unpack(self.previous['payload']);need(len(rows)==1 and type(self.previous['iosNavigationFeatureVersion']) is int
            and self.previous['iosNavigationFeatureVersion']==VERSION and same(self.previous,self.envelope(rows[0])))
        state=rows[0];exact(state,{'phase','binding','providerInstance','providerInputs','admissionSha256','entry','lastCall'})
        need(state['phase'] in ('preparing','ready','acting') and state['entry'] in ('pending','entered'))
        context(state['binding']);identifier(state['providerInstance'])
        need(state['admissionSha256'] is None or type(state['admissionSha256']) is str and len(state['admissionSha256'])==64)
        if state['phase']!='preparing':need(state['admissionSha256'] is not None and state['entry']=='entered')
        if state['lastCall'] is not None:
            row=state['lastCall'];exact(row,{'call','phase','started'})
            call=arguments('feature.world-navigation.act',row['call']);need(call['runId']==self.run
                and row['phase'] in ('issued','acknowledged'))
            exact(row['started'],{'epochMs','monotonic'})
            need(number(row['started']['epochMs'],1,1e15) and number(row['started']['monotonic'],0,1e15))
        self.state=deepcopy(state)

    def save(self):
        self.lock.assert_held();self.clock();need(same(self.store.read(),self.previous))
        value=self.envelope(self.state);self.store.write(value,self.previous)
        need(same(self.store.read(),value));self.previous=deepcopy(value);self.clock()

    def current(self):
        self.lock.assert_held();self.clock();source=self.runtime._sources(self.selector)
        need(source['check']() is not False)
        if self.state is not None:need(same(source['binding'],self.state['binding']))
        return source

    def admission(self):
        owner=self.runtime._navigation_admission_owner(self.selector,self.client,self.run,self.lock)
        need(isinstance(owner,NavigationAdmissionOwner) and owner.lock is self.lock
            and same(owner.binding,self.state['binding']))
        if self.state['admissionSha256'] is not None:
            need(digest(owner.store.read())==self.state['admissionSha256']);owner.archive()
        return self.limited(owner)

    def limited(self,owner):
        """Keep the enclosing deadline in every child's before-input guard."""
        original=owner.guard
        def guard():
            self.clock();result=original();self.clock();return result
        owner.guard=guard;return owner

    def prepare(self):
        with self.held():
            self.load();self.fixture.attach();source=self.current()
            if self.state is None:
                if self.role!='primary':raise NavigationFeaturePending('Primary original Worlds admission is pending')
                phase=self.fixture.read();need(phase['verb']=='baseline')
                self.state=dict(phase='preparing',binding=deepcopy(source['binding']),providerInstance=self.fixture.instance,
                    providerInputs=deepcopy(self.fixture.inputs),admissionSha256=None,entry='pending',lastCall=None);self.save()
            need(self.fixture.instance==self.state['providerInstance'] and same(self.fixture.inputs,self.state['providerInputs']))
            if self.state['phase']!='preparing':return
            if self.role!='primary':raise NavigationFeaturePending('Primary ordinary Worlds scene entry is pending')
            admission=self.admission()
            if self.state['admissionSha256'] is None:
                if admission.state is None:admission.acquire(self.epoch_ms())
                elif admission.state['phase']=='reading':admission.recover()
                admission.archive();self.state['admissionSha256']=digest(admission.store.read());self.save()
            inputs=self.runtime._navigation_scene_inputs(self.selector,admission)
            with self.runtime.existing_input_session(self.selector):inputs.enter()
            self.state.update(phase='ready',entry='entered');self.save()

    def act(self,call):
        outer,original=self.deadline,self.operation_clock;now=self.clock()
        self.deadline=now+30 if outer is None else min(outer,now+30)
        self.operation_clock=dict(epochMs=self.epoch_ms(),monotonic=now)
        try:return self._act(call)
        finally:self.deadline,self.operation_clock=outer,original

    def _act(self,call):
        need(self.role=='primary');call=deepcopy(arguments('feature.world-navigation.act',call));need(call['runId']==self.run)
        self.prepare()
        with self.held():
            self.load();self.current();admission=self.admission();phase=admission.fixture.read()
            need(call['fixtureUrl']==admission.fixture.fixture_url and phase['ticket']==call['ticket']
                and phase['verb']==call['verb'] and same(phase['inputs'],call['inputs']))
            prior=self.state['lastCall']
            if prior is not None and prior['call']['ticket']==call['ticket']:
                need(same(prior['call'],call))
                if prior['phase']=='issued':self.operation_clock=deepcopy(prior['started']);self.clock()
            else:
                need(prior is None or prior['phase']=='acknowledged')
                self.clock()
                self.state.update(phase='acting',lastCall=dict(call=call,phase='issued',started=deepcopy(self.operation_clock)));self.save()
            verb=call['verb']
            with self.runtime.existing_input_session(self.selector):
                if verb in ('open','close'):
                    self.runtime._navigation_surface_actions(self.selector,admission).act(call)
                elif verb in ('directory-select','bookmark-visit'):
                    child=self.runtime._navigation_composite_actions(self.selector,admission)
                    self.limited(child.places)
                    row=None if child.state is None or not child.state['actions'] else child.state['actions'][-1]
                    if row is not None and same(row['call'],call) and row['phase']=='arriving':child.settle()
                    elif row is not None and same(row['call'],call) and row['phase']=='closing':child.recover_close()
                    else:child.act(call)
                elif verb in PLACE_VERBS:self.limited(self.runtime._navigation_places_actions(self.selector,admission)).act(call)
                elif verb in ('navigate-missing','dismiss-error'):
                    child=self.runtime._navigation_missing_actions(self.selector,admission)
                    if verb=='navigate-missing':child.navigate(call)
                    else:
                        if child.state is None or child.state['proof'] is None:
                            raise NavigationFeaturePending('Actual owned named-lookup failure must be independently observed before dismissal')
                        child.dismiss(call)
                else:raise NavigationFeaturePending('Worlds process-transfer and final restoration coordination remain required')
            self.state.update(phase='ready');self.state['lastCall']['phase']='acknowledged';self.save()
            return {'performed':True}
