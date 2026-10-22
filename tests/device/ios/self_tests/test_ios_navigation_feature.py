"""Original scene entry and active dispatcher over real input owner journals.

HTTP, Python transports and private carriers are real; Qt/SDK/native clocks are
modeled. These tests do not claim the incomplete whole Worlds capability.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from copy import deepcopy
import unittest
import time
from unittest.mock import patch

from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import unpack
from ios.adapters.navigation_admission_owner import NavigationAdmissionOwner
from ios.adapters.navigation_feature import IOSNavigationFeature,NavigationFeaturePending
from ios.adapters.navigation_runtime import IOSNavigationRuntime
from ios.adapters.navigation_scene_inputs import NavigationSceneInputs
from ios.adapters.navigation_surface_actions import NavigationSurfaceActions
from ios.self_tests import test_ios_navigation_surface_actions as fixture


class NavigationFeatureTests(unittest.TestCase):
    def setUp(self):
        start=time.time()
        # Install the producer clock before any fixture response or original
        # exists. Later ordinary UI waits advance this same host timeline.
        def host_time():
            if not hasattr(self,'h'):return start
            return start+self.h.ms/1000+self.b.clock
        clock=patch('time.time',side_effect=host_time);clock.start();self.addCleanup(clock.stop)
        self.f=fixture.NavigationSurfaceActionsTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.h=self.f.h.h;self.root=self.h.root;self.b=self.f.b;self.fixture=self.f.fixture
        self.epoch=lambda:self.h.epoch()+self.b.clock*1000
        self.mono=lambda:self.h.mono()+self.b.clock;self.okay=True;test=self
        self.fixture.epoch_ms=lambda:int(self.epoch());self.fixture.monotonic=self.mono
        self.fixture.phase.epoch_ms=lambda:int(self.epoch());self.fixture.phase.monotonic=self.mono
        class Runtime(IOSNavigationRuntime):
            def __init__(runtime):runtime.inputs=0
            def state_path(runtime,selector):return test.root/'adapter-state.json'
            def _sources(runtime,selector):
                return dict(binding=deepcopy(test.f.admission.binding),check=lambda:test.okay)
            @contextmanager
            def existing_input_session(runtime,selector):runtime.inputs+=1;yield
            def _navigation_admission_owner(runtime,selector,client,run,lock):
                return NavigationAdmissionOwner(test.f.admission.store,test.f.admission.binding,run,lock,lambda:test.okay,
                    native=test.f.admission.native,sources=test.f.admission.sources,fixture=test.fixture,
                    epoch_ms=test.epoch,monotonic=test.mono)
            def _navigation_scene_inputs(runtime,selector,admission):
                return NavigationSceneInputs(PrivateFeatureState(test.root/'ios-navigation-scene-inputs.json'),
                    admission,test.b.ui,test.f.h.native,epoch_ms=test.epoch,monotonic=test.mono)
            def _navigation_surface_actions(runtime,selector,admission):
                return NavigationSurfaceActions(PrivateFeatureState(test.root/'ios-navigation-surface-actions.json'),
                    admission,test.b.ui,test.f.h.native,monotonic=lambda:test.b.clock)
        self.runtime=Runtime()

    def flow(self,role='primary'):
        return IOSNavigationFeature(self.runtime,'owned',self.h.fixture.harness.client,self.fixture.run,self.root,role=role,
            epoch_ms=self.epoch,monotonic=self.mono,sleep=self.b.sleep)

    def test_prepare_and_actual_open_close_keep_original_child_inputs_and_parent_duplicate_is_read_only(self):
        flow=self.flow();flow.prepare();self.assertEqual('ready',flow.state['phase'])
        self.assertEqual(1,self.b.inputs.count('PhoneAddressGoButton'))
        self.assertNotIn('state',flow.state)
        call=self.f.call('open');self.assertEqual({'performed':True},flow.act(call))
        self.assertEqual('places',self.b.screen);before=list(self.b.inputs);flow=self.flow()
        self.assertEqual({'performed':True},flow.act(call));self.assertEqual(before,self.b.inputs)
        self.assertEqual({'performed':True},flow.act(self.f.call('close')));self.assertIsNone(self.b.screen)
        original=PrivateFeatureState(self.root/'ios-navigation-scene-inputs.json').read()
        self.assertEqual('entered',unpack(original['payload'])[0]['phase'])
        self.assertIsNotNone(flow.store.read());self.assertIsNotNone(self.f.admission.store.read())

    def test_lost_parent_ack_adopts_existing_real_surface_ack_without_replaying_any_input(self):
        flow=self.flow();flow.prepare();call=self.f.call('open');write=flow.store.write
        def lost(value,previous):
            row=unpack(value['payload'])[0]['lastCall']
            if row is not None and row['phase']=='acknowledged':raise OSError('Lost parent ACK return')
            write(value,previous)
        with patch.object(flow.store,'write',side_effect=lost),self.assertRaises(OSError):flow.act(call)
        before=list(self.b.inputs);self.assertEqual({'performed':True},self.flow().act(call));self.assertEqual(before,self.b.inputs)

    def test_uncertain_child_input_stays_owned_across_parent_reconstruction_and_new_ticket(self):
        flow=self.flow();flow.prepare();self.f.ignore_places=True;call=self.f.call('open')
        with self.assertRaises(NativeUIError):flow.act(call)
        before=list(self.b.inputs);self.f.ignore_places=False
        with self.assertRaises(NativeUIError):self.flow().act(call)
        with self.assertRaises(NativeUIError):self.flow().act(self.f.call('close'))
        self.assertEqual(before,self.b.inputs)

    def test_actor_cannot_prepare_primary_input_or_adopt_a_missing_parent(self):
        with self.assertRaises(NavigationFeaturePending):self.flow('actor').prepare()
        self.assertEqual([],self.b.inputs);self.assertIsNone(self.flow().store.read())
        with self.assertRaises(NativeUIError):self.flow('actor').act(self.f.call('open'))
        self.assertEqual([],self.b.inputs)

    def test_changed_candidate_or_original_admission_cannot_authorize_the_next_input(self):
        flow=self.flow();flow.prepare();before=list(self.b.inputs);self.okay=False
        with self.assertRaises(NativeUIError):self.flow().act(self.f.call('open'))
        self.okay=True;raw=self.f.admission.store.read();changed=deepcopy(raw);changed['runId']='f'*32
        self.f.admission.store.write(changed,raw)
        with self.assertRaises(NativeUIError):self.flow().act(self.f.call('open'))
        self.assertEqual(before,self.b.inputs)

    def test_expired_original_scene_admission_cannot_be_reacquired_by_reopening_the_parent(self):
        self.h.ms+=2000
        with self.assertRaises(NativeUIError):self.flow().prepare()
        before=list(self.b.inputs);owner=self.flow()
        with self.assertRaises(NativeUIError):owner.prepare()
        self.assertEqual([],before);self.assertEqual(before,self.b.inputs)
        self.assertIsNotNone(owner.store.read())

    def test_original_public_action_budget_includes_preparation_and_cannot_restart_at_child_delivery(self):
        flow=self.flow();flow.prepare();call=self.f.call('open');write=flow.store.write
        def late(value,previous):
            write(value,previous)
            row=unpack(value['payload'])[0]['lastCall']
            if row is not None and row['phase']=='issued':self.b.clock+=31
        with patch.object(flow.store,'write',side_effect=late),self.assertRaises(NativeUIError):flow.act(call)
        self.assertFalse(PrivateFeatureState(self.root/'ios-navigation-surface-actions.json').path.exists())
        self.assertEqual(1,self.b.inputs.count('PhoneAddressGoButton'))
        before=list(self.b.inputs)
        with self.assertRaises(NativeUIError):self.flow().act(call)
        self.assertFalse(PrivateFeatureState(self.root/'ios-navigation-surface-actions.json').path.exists())
        self.assertEqual(before,self.b.inputs)


if __name__=='__main__':unittest.main()
