"""Actual ordinary entry/open and retained first HTTP/QML/PNG acquisition.

The physical product boundary is modeled; no device or build is used.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest

from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import unpack
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
