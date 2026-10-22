"""Actual ordinary entry/open and retained first HTTP/QML/PNG acquisition.

The physical product boundary is modeled; no device or build is used.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from unittest.mock import patch

from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import unpack
from feature_journeys.witness import Client
from ios.self_tests.navigation_feature_observer_fixture import Whole
from navigation_observation import viewpoint_urls


class NavigationFeatureObserverTests(unittest.TestCase):
    def setUp(self):self.h=Whole(self)

    def test_normal_open_admits_only_its_actual_http_qml_and_unchanged_observation_originals(self):
        h=self.h;h.flow.prepare();call=h.open_directory()
        with h.flow.held():
            observer=h.observer()
            with self.assertRaises(NativeUIError):
                observer.read(call['ticket'],viewpoint_urls(h.harness.inputs['sceneUrl'])['A'],'A',h.now(),
                    baseline=h.flow.admission().archive()['bookmarkBaseline'],provider_inputs=h.harness.inputs)
            row=observer.state['rows'][-1];owner=observer.live(row)
            before=deepcopy(owner.store.read());commands=deepcopy(h.gpu.commands)
            surface=h.flow_fixture.runtime._navigation_surface_actions('owned',h.flow.admission())
            proof=surface.directory(owner)
            self.assertEqual(before,owner.store.read());self.assertEqual(commands,h.gpu.commands)
            measured=observer.recover(directory=proof)
            self.assertTrue(measured['state']['panel'])
            self.assertEqual(proof['materialized']['record']['id'],measured['state']['searchResults'][0])
            old=unpack(before['payload'])[0]
            restored=observer.owners()[-1]
            self.assertEqual(old['originals'],restored.state['originals'])
            self.assertEqual(old['clockJoin'],restored.state['clockJoin'])
            self.assertEqual(commands,h.gpu.commands)

    def test_ignored_normal_places_open_cannot_start_http_or_acquire_a_frame(self):
        h=self.h;h.flow.prepare();h.flow_fixture.f.ignore_places=True
        with self.assertRaises(NativeUIError):h.open_directory()
        self.assertEqual([],h.http.events);self.assertEqual([],h.gpu.commands)
        before=list(h.flow_fixture.b.inputs)
        with self.assertRaises(NativeUIError):h.open_directory()
        self.assertEqual(before,h.flow_fixture.b.inputs)

    def test_active_coordinator_joins_baseline_to_first_open_and_returns_another_fresh_capture(self):
        h=self.h;h.flow.prepare();baseline=h.flow.observe_active(0)
        self.assertEqual('A',baseline['state']['location']);self.assertFalse(baseline['state']['panel'])
        h.open_directory();opened=h.flow.observe_active(baseline['sequence'])
        self.assertTrue(opened['state']['panel']);self.assertEqual(3,opened['sequence'])
        self.assertEqual(3,h.gpu.frames)
        with h.flow.held():
            observer=h.observer();first_open=observer.owners()[1];fresh=observer.owners()[2]
            self.assertNotEqual(first_open.request,fresh.request)
            self.assertEqual(first_open.state['options']['directory'],fresh.state['options']['directory'])

    def test_ignored_scene_entry_cannot_select_a_requested_viewpoint_or_capture(self):
        h=self.h;h.flow_fixture.b.mutation='goto-ignored';h.flow.prepare()
        with self.assertRaises(NativeUIError):h.flow.observe_active(0)
        self.assertEqual([],h.gpu.commands)
        self.assertEqual(1,h.flow_fixture.b.inputs.count('PhoneAddressGoButton'))

    def test_native_birth_replacement_before_first_observation_cannot_bypass_original_admission(self):
        h=self.h;h.flow.prepare();original=h.sdk.native_boundary.mutate
        def replaced(value):original(value);value['instance']='f'*32
        h.sdk.native_boundary.mutate=replaced
        with self.assertRaises(NativeUIError):h.flow.observe_active(0)
        with h.flow.held():
            self.assertEqual(1,h.observer().state['sequence'])
        # Its complete originals stay retained; they still cannot become an
        # admitted result just because the coordinator was reconstructed.
        with self.assertRaises(NativeUIError):h.flow_fixture.flow().observe_active(0)

    def test_slow_final_original_continuity_check_cannot_return_an_expired_acquisition(self):
        h=self.h;h.flow.prepare()
        from ios.adapters import navigation_source_prefix
        original=navigation_source_prefix.follow
        def slow(*args):original(*args);h.sdk.gpu.sleep(2.)
        with patch.object(navigation_source_prefix,'follow',side_effect=slow),self.assertRaises(NativeUIError):
            h.flow.observe_active(0)
        self.assertEqual(1,h.gpu.frames)
        with h.flow.held():self.assertEqual(1,h.observer().state['sequence'])

    def test_actor_reads_its_own_original_group_and_publishes_without_primary_input(self):
        h=self.h;h.flow.prepare();primary=h.flow.observe_active(0)
        before=list(h.flow_fixture.b.inputs);actor=h.flow_fixture.flow('actor')
        measured=actor.observe_active(0)
        with actor.held():
            owner=h.observer('actor',lock=actor.lock);receipt=owner.publish(Client(h.harness.client.url,h.harness.server.actor_token))
            original=owner.owners()[-1]
            self.assertEqual(measured['state'],receipt['facts'])
            self.assertNotEqual(primary['requestId'],original.request)
            self.assertNotEqual(primary['imageName'],measured['imageName'])
        self.assertEqual(before,h.flow_fixture.b.inputs)
        self.assertEqual(1,len(h.harness.client.observe()['entries']))

    def retained_open(self):
        h=self.h;call=h.open_directory();observer=h.observer()
        with self.assertRaises(NativeUIError):
            observer.read(call['ticket'],viewpoint_urls(h.harness.inputs['sceneUrl'])['A'],'A',h.now(),
                baseline=h.flow.admission().archive()['bookmarkBaseline'],provider_inputs=h.harness.inputs)
        return observer,observer.live(observer.state['rows'][-1])

    def test_real_cached_response_before_normal_open_cannot_borrow_the_new_admission_barrier(self):
        h=self.h;h.flow.prepare();h.materialize();h.fetch_directory=False
        with h.flow.held():
            _observer,owner=self.retained_open()
            surface=h.flow_fixture.runtime._navigation_surface_actions('owned',h.flow.admission())
            before=deepcopy(owner.store.read());commands=deepcopy(h.gpu.commands)
            with self.assertRaises(NativeUIError):surface.directory(owner)
            self.assertEqual(before,owner.store.read());self.assertEqual(commands,h.gpu.commands)

    def test_changed_in_memory_surface_original_cannot_supply_an_earlier_open_barrier(self):
        h=self.h;h.flow.prepare()
        with h.flow.held():
            _observer,owner=self.retained_open()
            surface=h.flow_fixture.runtime._navigation_surface_actions('owned',h.flow.admission())
            before=deepcopy(owner.store.read());commands=deepcopy(h.gpu.commands)
            surface.state['actions'][0]['before']['sampleEpochMs']-=1000
            with self.assertRaises(NativeUIError):surface.directory(owner)
            self.assertEqual(before,owner.store.read());self.assertEqual(commands,h.gpu.commands)


if __name__=='__main__':unittest.main()
