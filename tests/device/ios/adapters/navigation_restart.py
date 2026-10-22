"""One-send ordinary iOS restart after original Worlds resource admission.

This owns lifecycle input and its original receipt. Fresh process-local source
transfer, post-restart images, restoration and whole cleanup remain separate.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import time
from urllib.parse import urlsplit

from adapters.native_feature_observation import exact,need,number,validate as native_packet
from adapters.native_clock_join import digest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.restart_inputs import RestartInputs
from adapters.script_feature.history import pack,unpack,same
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.contract import arguments
from feature_journeys.phase_fixture import validate as phase_original
from ios.adapters.graphics_history import follow_native,restore_native
from ios.adapters.navigation_before_restart import NavigationBeforeRestart
from ios.adapters.navigation_fixture import NavigationFixtureReader
from ios.adapters.navigation_restart_proof import OWNERS,validate as restart_original
from ios.adapters.navigation_samples import NavigationSamples
from ios.adapters.navigation_scene_admission import validate as initial_original
from ios.adapters.pointer_state import drained

VERSION=1


class NavigationRestart:
    def __init__(self,runtime,selector,initial,samples,lock,fixture,*,epoch_ms=lambda:time.time()*1000,monotonic=time.monotonic):
        from ios.adapters.navigation_runtime import IOSNavigationRuntime
        need(isinstance(runtime,IOSNavigationRuntime) and isinstance(lock,ScriptSourceLock)
            and callable(epoch_ms) and callable(monotonic))
        self.runtime,self.selector,self.initial,self.lock=runtime,selector,initial_original(initial),lock
        self.binding,self.run=deepcopy(self.initial['binding']),self.initial['runId']
        need(isinstance(fixture,NavigationFixtureReader) and fixture.run==self.run
            and fixture.instance==self.initial['providerInstance'] and same(fixture.inputs,self.initial['providerInputs']))
        self.fixture=fixture
        self.epoch_ms,self.monotonic=epoch_ms,monotonic
        self.store=PrivateFeatureState(runtime.state_path(selector).with_name('ios-navigation-restart.json'))
        need(lock.path==self.store.path.with_name('script-feature-sources.lock'));lock.assert_held()
        exact(samples,{'primary','actor'});self.samples=samples
        for role,source in samples.items():
            need(isinstance(source,NavigationSamples) and source.role==role and source.stage==0 and source.run==self.run
                and same(source.binding,self.binding) and source.lock is lock
                and source.store.path==self.store.path.with_name('ios-navigation-'+role+'-0-samples.json'))
        self.inputs=RestartInputs(PrivateFeatureState(self.store.path.with_name('ios-navigation-restart-inputs.json')),
            [PrivateFeatureState(self.store.path.with_name(name)) for name in OWNERS],monotonic=monotonic)
        self.previous=self.store.read();self.state=None if self.previous is None else self.decode(self.previous)

    def envelope(self,state):
        return dict(iosNavigationRestartVersion=VERSION,binding=self.binding,runId=self.run,
            initialAdmissionSha256=digest(self.initial),payload=pack([state]))

    def frozen_samples(self,role):
        source=self.samples[role]
        return NavigationSamples(source.store,source.root,self.binding,self.run,role,0,self.lock,lambda:True,historical=True)

    def prepared(self,state):
        before=NavigationBeforeRestart.archive(state['before'],self.initial)
        for role in ('primary','actor'):
            value=self.frozen_samples(role).validate_drain(state['drains'][role])
            need(bool(value['rows']))
            for row in value['rows']:
                need(row['absence']['capturedEpochMs']<=before['clockJoin']['nativeBefore']['capturedEpochMs'])
        first,last=state['pointerBefore'],state['pointerAfter']
        need(first['processId']==last['processId']==int(self.binding['processIdentity'])
            and first['clockAfter']['epochMs']<=before['clockJoin']['nativeBefore']['capturedEpochMs']
            and last['clockBefore']['epochMs']>=before['clockJoin']['nativeAfter']['capturedEpochMs'])
        drained(first,last,after_epoch=first['clockAfter']['epochMs'])
        old=state['oldNative'];native_packet(old,old['requestId'],int(self.binding['processIdentity']),old['capturedEpochMs'])
        follow_native(before['clockJoin']['nativeAfter'],old)
        need(last['clockAfter']['epochMs']<=old['capturedEpochMs']
            and same(old['graphics'],self.initial['clockJoin']['nativeAfter']['graphics']))
        status=state['phase'];phase_original(status,run=self.run,area='world-navigation',request=status['requestId'],epoch=status['capturedEpochMs'])
        call=arguments('feature.world-navigation.act',state['arguments'])
        need(call['verb']=='restart-app' and call['runId']==self.run and status['active'] and status['activations']
            and status['activations'][-1]['ticket']==call['ticket']
            and status['activations'][-1]['stimulus']==dict(verb='restart-app',inputs={})
            and status['capturedEpochMs']>=before['clockJoin']['hostAfterEpochMs'])
        return before

    def decode(self,value):
        exact(value,{'iosNavigationRestartVersion','binding','runId','initialAdmissionSha256','payload'})
        rows=unpack(value['payload']);need(type(value['iosNavigationRestartVersion']) is int
            and value['iosNavigationRestartVersion']==VERSION and len(rows)==1 and same(value,self.envelope(rows[0])))
        state=rows[0];exact(state,{'arguments','status','before','drains','pointerBefore','pointerAfter','oldNative','phase','newNative','exit','receipt'})
        call=arguments('feature.world-navigation.act',state['arguments'])
        origin=urlsplit(self.initial['providerInputs']['sceneUrl'])
        fixture_url=origin.scheme+'://'+origin.netloc+'/feature-fixture/v1/runs/'+self.run+'/'
        need(call['verb']=='restart-app' and call['runId']==self.run and call['fixtureUrl']==fixture_url
            and state['status'] in ('prepared','observed'))
        exact(state['drains'],{'primary','actor'});self.prepared(state)
        if state['newNative'] is not None:
            plan=state['receipt']['input'] if state['status']=='observed' else self.inputs.read()
            packet=state['newNative'];need(plan['phase']=='observed')
            native_packet(packet,packet['requestId'],int(plan['newBinding']['processIdentity']),packet['capturedEpochMs'])
            need(same(plan['newNative'],dict(pid=packet['processId'],instance=packet['instance'],lifecycle=packet['lifecycle'])))
        else:need(state['exit'] is None and state['status']=='prepared')
        if state['exit'] is not None:
            plan=state['receipt']['input'] if state['status']=='observed' else self.inputs.read()
            restart_original(dict(input=plan,oldNative=state['oldNative'],native=state['newNative'],exit=state['exit']),self.inputs.owner_files)
        if state['status']=='observed':
            receipt=restart_original(state['receipt'],self.inputs.owner_files)
            need(same(receipt['input']['oldBinding'],self.binding) and same(receipt['oldNative'],state['oldNative'])
                and same(receipt['native'],state['newNative']) and same(receipt['exit'],state['exit']))
        else:need(state['receipt'] is None)
        return deepcopy(state)

    def bound(self):
        self.lock.assert_held();need(same(self.store.read(),self.previous))

    def authorize_input(self,runtime,selector,operation):
        """The held owner authorizes only its actual durable issued input."""
        self.bound();need(runtime is self.runtime and selector==self.selector and operation in ('app.stop','app.launch')
            and self.state is not None and self.state['status']=='prepared' and same(self.envelope(self.state),self.previous))
        plan=self.inputs.read();old=self.state['oldNative']
        need(plan['phase']==('stop-issued' if operation=='app.stop' else 'launch-issued') and same(plan['oldBinding'],self.binding)
            and same(plan['oldNative'],dict(pid=old['processId'],instance=old['instance'],lifecycle=old['lifecycle'])))
        if operation=='app.stop':self.stop_deadline()

    def stop_deadline(self):
        started=unpack(self.state['before']['payload'])[0]['started'];now,mono=self.epoch_ms(),self.monotonic()
        need(number(now,started['epoch'],started['epoch']+1500) and now-started['epoch']<1500
            and number(mono,started['monotonic'],started['monotonic']+1.5) and mono-started['monotonic']<1.5
            and abs(now-started['epoch']-(mono-started['monotonic'])*1000)<=250)

    def save(self):
        self.bound();value=self.envelope(self.state);self.decode(value)
        self.store.write(value,self.previous);need(same(self.store.read(),value));self.previous=deepcopy(value)

    def prepare(self,call,before,drains,pointer_before,pointer_after):
        """Retain actual source closure before any lifecycle input is issued."""
        self.bound();need(self.state is None and self.inputs.store.read() is None and isinstance(before,NavigationBeforeRestart))
        call=deepcopy(arguments('feature.world-navigation.act',call));need(call['verb']=='restart-app' and call['runId']==self.run)
        group=before.for_input();need(same(before.initial,self.initial) and same(before.binding,self.binding)
            and self.fixture is before.admission.fixture)
        source=self.runtime._sources(self.selector);need(same(source['binding'],self.binding))
        native=source['observer'].bound_native_observer(source['clock_source']);restore_native(native,group['clockJoin']['nativeAfter'])
        old=native.read(native.sequence)
        phase=self.fixture.phase.status()
        self.state=dict(arguments=call,status='prepared',before=deepcopy(before.previous),drains=deepcopy(drains),
            pointerBefore=deepcopy(pointer_before),pointerAfter=deepcopy(pointer_after),oldNative=deepcopy(old),phase=phase,newNative=None,exit=None,receipt=None)
        self.save();before.for_input()
        # Only a passive capture is repeated when the parent exists but no
        # child intent was ever stored. Stop/launch delivery remains one-send.
        self.inputs.capture(self.binding,native)
        need(same(self.inputs.read()['oldNative'],dict(pid=old['processId'],instance=old['instance'],lifecycle=old['lifecycle'])))

    def restart(self):
        self.bound();need(self.state is not None);self.decode(self.previous)
        if self.state['status']=='observed':return deepcopy(self.state['receipt'])
        need(self.inputs.store.read() is not None)
        plan=self.inputs.read();need(same(plan['oldBinding'],self.binding) and same(plan['oldNative'],dict(
            pid=self.state['oldNative']['processId'],instance=self.state['oldNative']['instance'],lifecycle=self.state['oldNative']['lifecycle'])))
        if self.state['exit'] is not None:
            # Both full originals survived. Adopt the exact lost parent return
            # without an SDK read, a new clock or another lifecycle input.
            receipt=dict(input=plan,oldNative=self.state['oldNative'],native=self.state['newNative'],exit=self.state['exit'])
            restart_original(receipt,self.inputs.owner_files)
            self.state.update(status='observed',receipt=deepcopy(receipt));self.save();return deepcopy(receipt)
        with self.runtime.existing_input_session(self.selector):
            if plan['phase']=='prepared':
                # Fresh input metadata can revoke an old prepared ticket. It
                # never supplies a product observation or a new source clock.
                self.state['phase']=self.fixture.phase.status();self.save()
                # Never treat historical originals as a new input deadline.
                self.stop_deadline()
                self.inputs.stop(lambda:self.runtime._navigation_restart_input(self.selector,'app.stop',self))
            if self.inputs.read()['phase']=='stop-issued':
                self.inputs.launch(lambda:self.runtime._navigation_restart_stopped(self.selector,self.binding),
                    lambda:self.runtime._navigation_restart_input(self.selector,'app.launch',self))
            self.runtime._navigation_recover_launch(self.selector,self.inputs)
            source=self.runtime._sources(self.selector)
            if self.state['newNative'] is None:
                native=source['observer'].bound_native_observer(source['clock_source'])
                packet=self.inputs.observe(source['binding'],native)
                self.state['newNative']=deepcopy(packet);self.save()
            else:need(same(source['binding'],self.inputs.read()['newBinding']))
            exit_=source['observer'].process_presence().require_absent(self.state['oldNative']['processId'])
            self.state['exit']=deepcopy(exit_);self.save()
            receipt=dict(input=self.inputs.read(),oldNative=self.state['oldNative'],native=self.state['newNative'],exit=exit_)
            restart_original(receipt,self.inputs.owner_files);source['check']()
            self.state.update(status='observed',receipt=deepcopy(receipt));self.save()
        return deepcopy(receipt)
