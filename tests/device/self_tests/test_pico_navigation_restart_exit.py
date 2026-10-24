"""Actual SourceLock exit must precede G12 publication; all producers modeled."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from adapters.normal_ui import NativeUIError
from adapters.normal_feature_state import PrivateFeatureState
from self_tests import test_pico_navigation_restart_prefix as original


class NavigationRestartExitTests(unittest.TestCase):
    model_type=original.Model
    process_start='10001'
    setUpClass=classmethod(original.NavigationRestartPrefixTests.setUpClass.__func__)
    tearDownClass=classmethod(original.NavigationRestartPrefixTests.tearDownClass.__func__)
    setUp=original.NavigationRestartPrefixTests.setUp
    make=original.NavigationRestartPrefixTests.make
    write=original.NavigationRestartPrefixTests.write
    read=original.NavigationRestartPrefixTests.read
    installed=original.NavigationRestartPrefixTests.installed
    activate=original.NavigationRestartPrefixTests.activate
    target_fingerprint=original.NavigationRestartPrefixTests.target_fingerprint
    first_eleven=original.NavigationRestartPrefixTests.first_eleven
    bind_restart=original.NavigationRestartPrefixTests.bind_restart
    twelve_call=original.NavigationRestartPrefixTests.twelve_call
    launch_receiver=original.NavigationRestartPrefixTests.launch_receiver
    native_reader=original.NavigationRestartPrefixTests.native_reader
    successor=original.NavigationRestartPrefixTests.successor

    def exiting(self,flow,kind,operation):
        original_held=self.lock.held;changed=[]
        role=self.root/'navigation-prefix-generation-1-primary-sources.json'
        @contextmanager
        def held():
            with original_held():yield
            # This is AFTER the real contextmanager checked/closed the actual
            # flock descriptor, not a synthetic pre-exit guard callback.
            parent=flow.continuation_store.read()
            eligible=parent is not None and parent['phase']=='ready'
            if operation=='observe':eligible=eligible and role.is_file() and json.loads(role.read_text())['phase']=='ready'
            if eligible and not changed:
                self.assertIsNone(self.lock._owner)
                changed.append(True)
                self.exit_counts=self.target_counts()
                if kind=='clock':self.native_offset=2000
                else:self.new_model.alive=False
                PrivateFeatureState(self.root/'navigation-prefix-generation-1-exit-event.json').write(dict(
                    outerReleased=self.lock._owner is None,phase=parent['phase'],operation=operation,
                    nativeEpochMs=flow.prefix.phase.epoch_ms(),hostMonotonic=flow.prefix.now(),
                    g1GuardAlive=self.new_model.alive,sourceCounts=self.exit_counts),None)
        return held,changed

    def target_counts(self):
        m=self.new_model
        return dict(native=self.new_native.sequence,bookmarks=m.native_sequence,environmentDirectory=m.source_sequence,
            panelsModals=dict(m.native_counters),replies=m.modal.replies.sequence,pose=self.new_world.probe_sequence,
            subject=self.new_world.subject.sequence)

    def refusal(self,kind,operation):
        self.first_eleven();flow,_factory=self.bind_restart();call=self.twelve_call()
        if operation=='observe':flow.act(call)
        held,changed=self.exiting(flow,kind,operation);phase=self.original_parent.phase
        self.native_offset=0;clock=phase.epoch_ms;host=self.original_parent.now()
        with patch.object(self.lock,'held',held),patch.object(phase,'epoch_ms',lambda:clock()+self.native_offset):
            with self.assertRaises(NativeUIError):
                if operation=='observe':flow.observe()
                else:flow.act(call)
        self.assertTrue(changed);self.assertEqual(host,self.original_parent.now())
        self.assertEqual(self.exit_counts,self.target_counts())
        self.assertEqual(2,len(self.sdk_calls));self.assertEqual('ready',flow.continuation_store.read()['phase'])
        self.assertEqual(self.original_prefix,self.original_parent.store.path.read_bytes())
        owner=flow.restart();self.assertEqual('observed',owner.state['phase'])
        # The actual source frame and clocks remain unchanged, not retimed to
        # make the final validation pass. No extra capture is requested here.
        self.assertEqual(owner.state['newFrame']['before']['ui']['observedEpochMs'],clock())

    def test_observe_real_exit_advances_native_clock_with_frozen_host_before_publication(self):
        self.refusal('clock','observe')

    def test_act_real_exit_loses_actual_g1_process_guard_before_publication(self):
        self.refusal('guard','act')

    def test_new_native_clock_regresses_after_exit_while_phase_clock_stays_fresh(self):
        self.first_eleven();flow,_factory=self.bind_restart();flow.act(self.twelve_call());owner=flow.restart()
        actual_successor=owner.successor;runtime=[];calls=[];events=[]
        def successor(inputs,state):
            value=actual_successor(inputs,state);runtime.append(value);return value
        owner.successor=successor;actual_held=self.lock.held;phase=self.original_parent.phase
        phase_clock=phase.epoch_ms;host=self.original_parent.now()
        @contextmanager
        def held():
            with actual_held():yield
            samples=self.root/'navigation-prefix-generation-1-primary-sources.json'
            if runtime and samples.is_file() and json.loads(samples.read_text())['phase']=='ready' and not events:
                self.assertIsNone(self.lock._owner);events.append(True);self.exit_counts=self.target_counts()
                native=runtime[-1]['native'];actual_clock=native.clock_ms
                def regressed():calls.append(True);return actual_clock()-2000
                native.clock_ms=regressed
                PrivateFeatureState(self.root/'navigation-prefix-generation-1-exit-native-clock.json').write(dict(
                    outerReleased=True,newNativeEpochMs=actual_clock()-2000,phaseEpochMs=phase_clock(),
                    hostMonotonic=host,sourceCounts=self.exit_counts),None)
        caught=None;result=None
        with patch.object(self.lock,'held',held):
            try:result=flow.observe()
            except NativeUIError as error:caught=error
        self.assertTrue(events);self.assertEqual(host,self.original_parent.now());self.assertEqual(self.exit_counts,self.target_counts())
        self.assertIs(phase_clock,phase.epoch_ms)  # Independent source untouched.
        PrivateFeatureState(self.root/'navigation-prefix-generation-1-exit-native-result.json').write(dict(
            returned=result,nativeClockCalls=len(calls),refused=caught is not None),None)
        self.assertIsNotNone(caught,'A new Native clock 2000ms behind its unchanged frame must refuse publication')
        self.assertTrue(calls,'Finalization must read the actual new Native observer clock')

    def test_landed_ready_cas_cannot_reset_original_host_age_with_frozen_native_clock(self):
        self.first_eleven();flow,_factory=self.bind_restart();call=self.twelve_call()
        parent=self.original_parent;actual_write=flow.continuation_store.write;clock=parent.monotonic
        phase_clock=parent.phase.monotonic;offset=[0.];events=[]
        def write(value,previous):
            actual_write(value,previous)
            if value['phase']=='ready' and not events:
                self.assertEqual(value,flow.continuation_store.read())  # Real landed CAS.
                before=clock()+offset[0];offset[0]+=2;events.append(True)
                owner=flow.restart();native=owner.runtime['native'];self.exit_counts=self.target_counts()
                PrivateFeatureState(self.root/'navigation-prefix-generation-1-ready-cas-delay.json').write(dict(
                    readyLanded=True,hostBefore=before,hostAfter=clock()+offset[0],
                    nativeEpochMs=native.clock_ms(),phaseEpochMs=parent.phase.epoch_ms(),
                    capturedEpochMs=owner.state['newFrame']['before']['ui']['observedEpochMs'],sourceCounts=self.exit_counts),None)
        caught=None;result=None
        with patch.object(flow.continuation_store,'write',write),patch.object(parent,'monotonic',lambda:clock()+offset[0]),\
             patch.object(parent.phase,'monotonic',lambda:phase_clock()+offset[0]):
            try:result=flow.act(call)
            except NativeUIError as error:caught=error
        self.assertTrue(events);self.assertEqual(self.exit_counts,self.target_counts())
        PrivateFeatureState(self.root/'navigation-prefix-generation-1-ready-cas-result.json').write(dict(
            refused=caught is not None,returned=result),None)
        self.assertIsNotNone(caught,'Landed parent CAS time must remain in the original capture age')

if __name__=='__main__':unittest.main()
