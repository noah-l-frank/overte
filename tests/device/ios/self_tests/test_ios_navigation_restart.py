"""Real retained scene/GPU journals; lifecycle, native Qt and SDK are modeled."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from copy import deepcopy
from types import SimpleNamespace
import unittest
import time
from unittest.mock import patch

from adapters.native_feature_observation import NativeFeatureObservation
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import unpack
from ios.adapters.navigation_restart import NavigationRestart
from ios.adapters.navigation_runtime import IOSNavigationRuntime
from ios.adapters.navigation_samples import NavigationSamples
from ios.adapters.navigation_sample import NavigationSampleOwner
from ios.adapters.navigation_fixture import NavigationFixtureReader
from ios.self_tests.test_ios_navigation_before_restart import NavigationBeforeRestartTests
from ios.self_tests.test_ios_navigation_before_restart import Native as BeforeNative
from ios.self_tests.test_ios_navigation_sample import SDK
from ios.self_tests.test_ios_navigation_sample import Navigation as NavigationSDK
from ios.self_tests.test_ios_navigation_samples import GPU
from ios.self_tests.test_ios_pointer_state import NativePointerBoundary
from ios.self_tests.test_ios_navigation_world_measurements import global_packet
from navigation_observation import viewpoint_urls
from self_tests.test_native_feature_observation import Boundary as NativeBoundary
from self_tests.test_native_process_presence import Boundary as PresenceBoundary
from adapters.restart_inputs import RestartDeliveryUncertain


class OldNative(NativeFeatureObservation):
    def __init__(self,h):
        self.h=h;self.stamp=h.last+10;self.boundary=NativeBoundary();self.boundary.sequence=h.fixture.proof.before['clockJoin']['nativeAfter']['sequence']
        def tick():
            self.stamp+=1;h.fixture.clock(self.stamp);return self.stamp
        def original(value):
            request=value['requestId'];value.update(global_packet(tick(),1),requestId=request,sequence=self.boundary.sequence)
        self.boundary.mutate=original
        super().__init__(self.boundary.send,self.boundary.original,tick,lambda:True,42,ios=True,native_clock_bound=True,
            monotonic=h.h.mono,sleep=lambda seconds:None)


class LifecycleBoundary:
    """Explicit SDK/OS model; real runtime and RestartInputs own delivery."""
    def __init__(self,h):
        self.h=h;self.pid=42;self.phase='bound';self.calls=[];self._operation='feature.world-navigation.act'
        self.ignore_stop=self.ignore_launch=self.lost_stop=self.lost_launch=False
        self.unknown_kernel=False;self.stamp=h.last+100;self.new_native=NativeBoundary()
        self.new_native.mutate=self.native_original
    def tick(self):
        self.stamp+=1;self.h.fixture.clock(self.stamp);return self.stamp
    def native_original(self,value):
        request=value['requestId'];value.update(global_packet(self.tick(),1),requestId=request,
            sequence=self.new_native.sequence,processId=self.pid,instance='f'*32,lifecycle=dict(backgrounds=0,activations=2,launches=2))
    @contextmanager
    def session(self,selector):yield
    def invoke(self,selector,operation,values):
        if values!={} or selector!='existing':raise AssertionError('Foreign normal lifecycle input')
        self.calls.append(operation)
        if operation=='app.stop':
            self.phase='retiring'
            if not self.ignore_stop:self.pid=None
            if self.lost_stop:raise OSError('Synthetic lost actual stop return')
        elif operation=='app.launch':
            self.phase='preparing'
            if not self.ignore_launch:self.pid=43
            if self.lost_launch:raise OSError('Synthetic lost actual launch return')
            if self.pid==43:self.phase='bound'
        else:raise AssertionError('Unexpected lifecycle operation')
        return {'performed':True}
    def _candidate_guard(self,*,complete):
        if complete is not True:raise AssertionError('Complete candidate guard required')
    def _script_restart_session(self,selector,*,inputs):return object(),dict(sessionId=self.h.initial['binding']['sessionId']),object()
    def _binding(self,*args):return self
    def _binding_store(self,selector):return SimpleNamespace(read=self.record)
    def record(self):return dict(phase=self.phase)
    def finish_retirement(self):
        if self.pid is not None:raise NativeUIError('Actual modeled OS process still exists')
        self.phase='retired'
    def retired_absence(self):
        if self.pid is not None or self.phase!='retired':raise NativeUIError('Original modeled OS absence unavailable')
    def reset_launch_state(self,selector,state):state['processIdentity']=None
    def _recover_script_restart_launch(self,selector,*,inputs):
        if self.pid!=43 or inputs.read()['phase']!='launch-issued':raise NativeUIError('Actual modeled launch unavailable')
        self.phase='bound'
    def presence(self):
        boundary=PresenceBoundary(pid=self.pid,epoch_ms=self.tick)
        boundary.presence='unknown' if self.unknown_kernel else ('absent' if self.pid==43 else 'present')
        boundary.edit=lambda value:value.update(instance='f'*32)
        return boundary.reader(ios=True)
    def sources(self,selector):
        if self.pid==42:
            return dict(binding=deepcopy(self.h.initial['binding']),observer=SimpleNamespace(
                bound_native_observer=lambda clock:OldNative(self.h)),clock_source=object(),check=lambda:True)
        if self.pid!=43:raise NativeUIError('No actual modeled current process')
        def native(clock):
            return NativeFeatureObservation(self.new_native.send,self.new_native.original,self.tick,lambda:self.pid==43,43,
                ios=True,native_clock_bound=True,monotonic=self.h.h.mono,sleep=lambda seconds:None)
        return dict(binding=self.h.initial['binding']|dict(processIdentity='43'),observer=SimpleNamespace(
            bound_native_observer=native,process_presence=self.presence),clock_source=object(),check=lambda:self.pid==43)


class NavigationRestartTests(unittest.TestCase):
    def setUp(self):
        self.fixture=NavigationBeforeRestartTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.h=self.fixture.h;self.lock=self.h.lock;self.root=self.h.root;self.initial=self.fixture.proof.initial
        self.run=self.initial['runId'];self.last=self.fixture.proof.before['clockJoin']['nativeAfter']['capturedEpochMs']
        self.h.fixture.harness.provider.clock_ms=lambda:int(time.time()*1000)
        self.sdk=SDK(self.h.fixture.harness,self.run);self.gpu=GPU(self.sdk);self.sample_sources={}
        self.provider=NavigationFixtureReader(self.h.fixture.harness.client,self.run);self.provider.attach()
        self.runtime=object.__new__(IOSNavigationRuntime)
        self.runtime.state_path=lambda selector:self.root/'ios-state.json'
        self.runtime._sources=lambda selector:dict(binding=deepcopy(self.initial['binding']),observer=SimpleNamespace(
            bound_native_observer=lambda clock:OldNative(self)),clock_source=object(),check=lambda:True)
        with self.fixture.held():
            for role in ('primary','actor'):
                def child(request,role=role):
                    return NavigationSampleOwner(PrivateFeatureState(self.root/('ios-navigation-'+role+'-0-'+request[4:]+'-sample.json')),
                        self.root,self.initial['binding'],self.run,role,0,request,self.lock,lambda:True,
                        native=self.sdk.native(),navigation=self.sdk.navigation.reader(),fixture=self.provider,frame_factory=self.gpu.factory,
                        sleep=self.sdk.gpu.sleep,monotonic=lambda:self.sdk.gpu.clock,epoch_ms=lambda:1_000_000+self.sdk.gpu.clock*1000)
                source=NavigationSamples(PrivateFeatureState(self.root/('ios-navigation-'+role+'-0-samples.json')),
                    self.root,self.initial['binding'],self.run,role,0,self.lock,lambda:True,factory=child)
                self.sample_sources[role]=source
                ticket=self.provider.phase.status()['activations'][-1]['ticket']
                source.read(ticket,viewpoint_urls(self.h.fixture.inputs['sceneUrl'])['A'],'A',1_000_000+self.sdk.gpu.clock*1000-1)
            self.drains={role:source.drain() for role,source in self.sample_sources.items()}
            # Emit an independently fresh modeled native scene read AFTER
            # both real image/retirement acquisitions, retaining its original
            # tree/import history. Production does not retime old evidence.
            old_raw=self.fixture.proof.before['originals'];inventory=self.h.fixture.inventory
            inventory.clock=self.sdk.gpu.clock+.1;current=inventory.reader().read(self.run)
            clock=SimpleNamespace(clock=inventory.clock+.002)
            navigation=NavigationSDK(clock,self.run,viewpoint_urls(self.h.fixture.inputs['sceneUrl'])['A'],self.sdk.body)
            clock.clock=inventory.clock+.002
            navigation.sequence=max(current['source']['sceneLoads']['sequence'],old_raw['navigation']['sequence'])
            navigation.mutate=lambda value:value['source']['sceneLoads'].update(
                currentGeneration=inventory.generation,requests=deepcopy(inventory.loads))
            self.h.fixture.originals.update(inventory=current,navigation=navigation.reader().read(self.run))
            group=self.fixture.proof.before_group()
            old_raw.clear();old_raw.update(deepcopy(group['originals']));self.fixture.proof.before=group
            counter=self.sdk.native_boundary.sequence
            for index,key in enumerate(('nativeBefore','nativeAfter'),1):group['clockJoin'][key]['sequence']=counter+index
            self.fixture.first=group['clockJoin']['nativeBefore']['capturedEpochMs']
            self.last=group['clockJoin']['nativeAfter']['capturedEpochMs'];self.h.ms=self.fixture.first-self.h.native_first
            self.fixture.admission.native=BeforeNative(self.fixture)
            pointer=NativePointerBoundary();pointer.now=self.fixture.first-10
            pointer_reader=pointer.reader();self.pointer_before=pointer_reader.read(self.run)
            self.h.host=time.time()*1000-self.h.ms
            self.h.fixture.harness.provider.clock_ms=lambda:int(self.h.epoch())
            self.before=self.fixture.owner();self.before.acquire()
            pointer.now=self.last;self.pointer_after=pointer_reader.read(self.run)
        self.ticket='9'*32;self.h.fixture.harness.client.activate(self.ticket,'restart-app',{})
        self.call=dict(contractVersion=16,runId=self.run,ticket=self.ticket,
            fixtureUrl=self.provider.fixture_url,verb='restart-app',inputs={})
        self.lifecycle=LifecycleBoundary(self);self.runtime.adapter=self.lifecycle
        self.runtime.existing_input_session=self.lifecycle.session;self.runtime._sources=self.lifecycle.sources

    def owner(self):return NavigationRestart(self.runtime,'existing',self.initial,self.sample_sources,self.lock,self.fixture.admission.fixture,
        epoch_ms=self.h.epoch,monotonic=self.h.mono)

    def test_preparation_preserves_scene_and_image_originals_before_any_normal_lifecycle_input(self):
        with self.fixture.held():
            owner=self.owner();owner.prepare(self.call,self.before,self.drains,self.pointer_before,self.pointer_after)
            self.assertEqual('prepared',owner.state['status']);self.assertEqual('prepared',owner.inputs.read()['phase'])
            self.assertIsNone(owner.state['receipt']);self.assertEqual(self.drains,owner.state['drains'])
            self.assertEqual(owner.state,self.owner().state)

    def prepare(self):
        owner=self.owner();owner.prepare(self.call,self.before,self.drains,self.pointer_before,self.pointer_after);return owner

    def test_actual_modeled_new_birth_and_kernel_esrch_are_retained_without_scene_transfer_claim(self):
        with self.fixture.held():
            owner=self.prepare();receipt=owner.restart()
            self.assertEqual(['app.stop','app.launch'],self.lifecycle.calls)
            self.assertEqual('43',receipt['input']['newBinding']['processIdentity']);self.assertEqual('ESRCH',receipt['exit']['errorSymbol'])
            self.assertEqual('observed',owner.state['status']);self.assertNotIn('restored',owner.state)
            self.assertEqual(receipt,self.owner().restart());self.assertEqual(['app.stop','app.launch'],self.lifecycle.calls)
            self.assertEqual('feature.world-navigation.act',self.lifecycle._operation)

    def test_lost_actual_stop_return_recovers_by_os_absence_without_repeating_stop(self):
        with self.fixture.held():
            owner=self.prepare();self.lifecycle.lost_stop=True
            with self.assertRaises(RestartDeliveryUncertain):owner.restart()
            self.assertEqual('stop-issued',owner.inputs.read()['phase']);self.assertEqual(['app.stop'],self.lifecycle.calls)
            self.assertEqual('ESRCH',self.owner().restart()['exit']['errorSymbol'])
            self.assertEqual(['app.stop','app.launch'],self.lifecycle.calls)

    def test_lost_actual_launch_return_recovers_only_existing_new_process_without_repeating_launch(self):
        with self.fixture.held():
            owner=self.prepare();self.lifecycle.lost_launch=True
            with self.assertRaises(RestartDeliveryUncertain):owner.restart()
            self.assertEqual('launch-issued',owner.inputs.read()['phase']);self.assertEqual('preparing',self.lifecycle.phase)
            self.assertEqual('ESRCH',self.owner().restart()['exit']['errorSymbol'])
            self.assertEqual(['app.stop','app.launch'],self.lifecycle.calls)

    def test_acknowledged_ignored_stop_cannot_authorize_launch_or_a_second_stop(self):
        with self.fixture.held():
            owner=self.prepare();self.lifecycle.ignore_stop=True
            with self.assertRaises(NativeUIError):owner.restart()
            with self.assertRaises(NativeUIError):self.owner().restart()
            self.assertEqual(['app.stop'],self.lifecycle.calls);self.assertEqual('stop-issued',owner.inputs.read()['phase'])

    def test_unknown_kernel_result_and_expired_pre_stop_input_remain_owned(self):
        with self.fixture.held():
            owner=self.prepare();self.h.ms+=2000
            with self.assertRaises(NativeUIError):owner.restart()
            self.assertEqual([],self.lifecycle.calls);self.assertEqual('prepared',owner.inputs.read()['phase'])

    def test_unknown_old_pid_death_cannot_become_observed_despite_stop_and_launch_acks(self):
        with self.fixture.held():
            owner=self.prepare();self.lifecycle.unknown_kernel=True
            with self.assertRaises(NativeUIError):owner.restart()
            self.assertEqual('prepared',self.owner().state['status']);self.assertEqual('observed',owner.inputs.read()['phase'])
            with self.assertRaises(NativeUIError):self.owner().restart()
            self.assertEqual(['app.stop','app.launch'],self.lifecycle.calls)

    def test_slow_stop_issued_journal_cannot_deliver_an_expired_pre_stop_gate(self):
        with self.fixture.held():
            owner=self.prepare();write=owner.inputs.store.write
            def slow(value,previous):
                result=write(value,previous)
                if value['phase']=='stop-issued':self.h.ms+=2000
                return result
            owner.inputs.store.write=slow
            with self.assertRaises(RestartDeliveryUncertain):owner.restart()
            self.assertEqual([],self.lifecycle.calls);self.assertEqual('stop-issued',owner.inputs.read()['phase'])
            with self.assertRaises(NativeUIError):self.owner().restart()
            self.assertEqual([],self.lifecycle.calls)

    def test_new_fixture_phase_revokes_old_prepared_restart_without_sending_input(self):
        with self.fixture.held():
            owner=self.prepare();self.h.fixture.harness.client.activate('8'*32,'cleanup',{})
            with self.assertRaises(NativeUIError):owner.restart()
            self.assertEqual([],self.lifecycle.calls);self.assertEqual('prepared',owner.inputs.read()['phase'])

    def test_lost_complete_parent_result_recovers_exact_originals_without_sdk_or_new_clock(self):
        with self.fixture.held():
            owner=self.prepare();write=owner.store.write
            def lost(value,previous):
                if unpack(value['payload'])[0]['status']=='observed':raise OSError('Synthetic lost final parent write')
                return write(value,previous)
            owner.store.write=lost
            with self.assertRaises(OSError):owner.restart()
            rebuilt=self.owner();self.assertIsNotNone(rebuilt.state['newNative']);self.assertIsNotNone(rebuilt.state['exit'])
            originals=deepcopy((rebuilt.state['newNative'],rebuilt.state['exit']));calls=list(self.lifecycle.calls)
            self.runtime._sources=lambda selector:self.fail('Lost-final recovery read SDK')
            receipt=rebuilt.restart();self.assertEqual(originals,(receipt['native'],receipt['exit']));self.assertEqual(calls,self.lifecycle.calls)

    def test_acknowledged_ignored_launch_keeps_issued_intent_and_never_launches_again(self):
        with self.fixture.held():
            owner=self.prepare();self.lifecycle.ignore_launch=True
            with self.assertRaises(NativeUIError):owner.restart()
            with self.assertRaises(NativeUIError):self.owner().restart()
            self.assertEqual(['app.stop','app.launch'],self.lifecycle.calls);self.assertEqual('launch-issued',owner.inputs.read()['phase'])


if __name__=='__main__':unittest.main()
