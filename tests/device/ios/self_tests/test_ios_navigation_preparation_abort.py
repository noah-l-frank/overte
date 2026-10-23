"""Actual failed preparation/Stop/HTTP/CAS owners; SDK/OS producers are models.

No baseline image, scene entry, terminal seal or successful feature is supplied.
The genuine whole factory fails before its first capture. No device is accessed.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from unittest.mock import patch

from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import unpack,pack
from feature_journeys.witness import Client
from ios.adapters import appium_adapter as backend
from ios.adapters.navigation_feature import IOSNavigationFeature
from ios.adapters.navigation_whole_feature import NavigationWholeFeature
from ios.adapters.navigation_preparation_abort import NavigationPreparationAbort
from ios.self_tests.navigation_end_fixture import EndBoundary


class NavigationPreparationAbortTests(unittest.TestCase):
    def setUp(self):
        self.b=EndBoundary(self);b=self.b
        self.client=Client(b.controller.url,b.controller.token);run,_=self.client.register('world-navigation');self.addCleanup(self.client.close)
        def sleep(delay):b.os.clock+=delay
        self.flow=IOSNavigationFeature(b.runtime,'owned',self.client,run,b.root,epoch_ms=b.os.epoch,monotonic=lambda:b.os.clock,sleep=sleep)
        b.runtime._sources=lambda _selector:dict(binding=deepcopy(b.binding),check=lambda:True)
        def failed(*_args,**_kwargs):raise OSError('Actual pre-capture factory failure')
        b.runtime._navigation_baseline_image=failed
        self.whole=NavigationWholeFeature(self.flow)
        with self.assertRaisesRegex(OSError,'pre-capture'):self.whole.prepare()
        self.parents={name:(self.flow.store.path.with_name(name).stat().st_ino,self.flow.store.path.with_name(name).read_bytes())
            for name in ('ios-navigation-whole-feature.json','ios-navigation-whole-preparation.json')}
        self.assertIsNone(self.flow.store.read())

    def owner(self):return NavigationPreparationAbort(self.flow)

    def same_parents(self):
        self.assertEqual(self.parents,{name:(self.flow.store.path.with_name(name).stat().st_ino,self.flow.store.path.with_name(name).read_bytes()) for name in self.parents})
        self.assertIsNone(self.flow.store.read())

    def test_original_failed_preparation_ends_once_and_reopens_without_any_transport(self):
        b=self.b
        with self.flow.held():
            owner=self.owner();result=owner.finish();self.assertEqual('failed',result['status']);self.assertTrue(result['originalsRetained'])
            self.assertEqual(1,b.stops);self.assertEqual(1,sum(method=='DELETE' for method,_ in b.requests))
            self.assertIsNone(b.sdk.read());self.assertIsNone(b.installed.store.read());self.same_parents()
            requests=deepcopy(b.requests)
            def forbidden(*_args,**_kwargs):self.fail('Historical failed-preparation reader attempted transport')
            with patch.object(b.runtime,'_sources',side_effect=forbidden),patch.object(self.client,'request',side_effect=forbidden),patch.object(backend.WebDriver,'call',side_effect=forbidden):
                historical=self.owner();self.assertEqual(result,historical.result())
                forged=deepcopy(historical.previous);state=unpack(forged['payload'])[0];state['os']['actor']=state['os']['primary'];forged['payload']=pack([state])
                with self.assertRaises(NativeUIError):historical.decode(forged)
            self.assertEqual(requests,b.requests);self.same_parents()

    def test_lost_stop_return_resolves_only_through_original_os_windows_without_another_stop(self):
        b=self.b;b.stop_lost=True
        with self.flow.held():
            owner=self.owner()
            with self.assertRaises((OSError,RuntimeError,ValueError)):owner.finish()
            self.assertEqual('stop-issued',self.owner().state['phase']);self.assertEqual(1,b.stops)
            b.stop_lost=False;result=self.owner().finish();self.assertEqual('failed',result['status']);self.assertEqual(1,b.stops);self.same_parents()

    def test_lost_delete_return_gets_original_404_and_never_resends_delete(self):
        b=self.b;b.delete_lost=True
        with self.flow.held():
            owner=self.owner()
            with self.assertRaises((OSError,RuntimeError,ValueError)):owner.finish()
            self.assertEqual('delete-issued',self.owner().state['phase']);b.delete_lost=False
            self.assertEqual('failed',self.owner().finish()['status'])
            self.assertEqual(1,sum(method=='DELETE' for method,_ in b.requests));self.same_parents()

    def test_ignored_delete_keeps_responsibility_until_separate_actual_absence(self):
        b=self.b;b.delete_ignored=True
        with self.flow.held():
            with self.assertRaises(NativeUIError):self.owner().finish()
            with self.assertRaises(NativeUIError):self.owner().finish()
            self.assertEqual(1,sum(method=='DELETE' for method,_ in b.requests));self.assertIsNotNone(b.sdk.read())
            b.exists=False;self.assertEqual('failed',self.owner().finish()['status']);self.assertEqual(1,b.stops)
            self.assertEqual(1,sum(method=='DELETE' for method,_ in b.requests));self.same_parents()

    def test_any_retained_ordinary_input_blocks_abort_stop(self):
        with self.flow.held():
            owner=self.owner();path=self.flow.store.path.with_name('ios-navigation-address-42-inputs.json')
            store=PrivateFeatureState(path);store.write(dict(uncertain=True),None)
            with self.assertRaises(NativeUIError):owner.stop()
            self.assertEqual(0,self.b.stops);self.assertEqual(dict(uncertain=True),store.read());self.same_parents()

    def test_slow_stop_intent_exhausts_original_budget_and_never_delivers_or_resends_stop(self):
        with self.flow.lock.held():
            owner=self.owner();write=owner.store.write
            def slow(value,previous):
                write(value,previous)
                if unpack(value['payload'])[0]['phase']=='stop-issued':self.flow.sleep(31)
            with patch.object(owner.store,'write',side_effect=slow),self.assertRaises(NativeUIError):owner.stop()
            self.assertEqual(0,self.b.stops);self.assertEqual('stop-issued',self.owner().state['phase'])
            with self.assertRaises(NativeUIError):self.owner().stop()
            self.assertEqual(0,self.b.stops);self.same_parents()

    def test_changed_preparation_candidate_cannot_borrow_the_original_stop_authority(self):
        with self.flow.held():
            owner=self.owner();store=PrivateFeatureState(self.flow.store.path.with_name('ios-navigation-whole-preparation.json'))
            previous=store.read();changed=deepcopy(previous);state=unpack(changed['payload'])[0]
            state['binding']['artifactSha256']='0'*64;changed['payload']=pack([state]);store.write(changed,previous)
            with self.assertRaises(NativeUIError):owner.stop()
            self.assertEqual(0,self.b.stops);self.assertEqual(changed,store.read())

    def test_incomplete_original_os_window_cannot_authorize_sdk_deletion(self):
        with self.flow.held():
            owner=self.owner();owner.stop();self.assertFalse(owner.process_round())
            with self.assertRaises(NativeUIError):owner.delete()
            self.assertEqual(0,sum(method=='DELETE' for method,_ in self.b.requests));self.assertIsNotNone(self.b.sdk.read())
            self.assertEqual('stop-issued',owner.state['phase']);self.same_parents()

    def test_issued_capture_intent_retains_native_file_responsibility_and_cannot_borrow_early_abort(self):
        with self.flow.held():
            store=PrivateFeatureState(self.flow.store.path.with_name('ios-navigation-whole-preparation.json'))
            previous=store.read();changed=deepcopy(previous);state=unpack(changed['payload'])[0]
            state['baselines']['primary']['phase']='issued';changed['payload']=pack([state]);store.write(changed,previous)
            with self.assertRaises(NativeUIError):self.owner()
            self.assertEqual(0,self.b.stops);self.assertEqual(changed,store.read());self.assertIsNotNone(self.b.sdk.read())


if __name__=='__main__':unittest.main()
