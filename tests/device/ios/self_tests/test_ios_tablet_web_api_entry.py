"""Real loopback WebDriver final sends under the original whole-call clock."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import unittest
from adapters.normal_ui import NativeUIError
from ios.adapters.tablet_web_api_entry import installed_entry
from ios.adapters.tablet_web_feature import IOSTabletWebFeature
from ios.self_tests import test_ios_sdk_operation_guard as sdk_tests


class TabletAPIEntryTests(unittest.TestCase):
    def setUp(self):
        self.sdk=sdk_tests.SDKOperationGuardTests();self.sdk.setUp();self.addCleanup(self.sdk.doCleanups);self.clock=0.
    def wrap(self,function):return installed_entry(function,monotonic=lambda:self.clock)
    def test_candidate_preparation_cannot_move_the_original_entry_deadline(self):
        def actual(_self,_selector,_operation,_values):self.clock=60.;return self.sdk.send()
        with self.assertRaises(NativeUIError):self.wrap(actual)(self,'test-selector','feature.tablet-web.act',{})
        self.assertEqual([],self.sdk.requests)
    def test_final_native_verification_stays_inside_same_actual_transport_guard(self):
        def actual(_self,_selector,_operation,_values):
            self.sdk.send();self.clock=60.;return self.sdk.send()
        with self.assertRaises(NativeUIError):self.wrap(actual)(self,'test-selector','feature.tablet-web.observe',{})
        self.assertEqual(1,len(self.sdk.requests));self.sdk.send();self.assertEqual(2,len(self.sdk.requests))
    def test_unrelated_default_operation_and_nested_whole_scope_preserve_transport(self):
        def actual(_self,_selector,_operation,_values):self.clock=90.;return self.sdk.send()
        self.assertEqual(dict(received=True),self.wrap(actual)(self,'test-selector','app.foreground',{}))
        owner=object.__new__(IOSTabletWebFeature);owner.monotonic=lambda:self.clock;owner.deadline=None;owner.last=None;owner.failed=False
        self.clock=100.
        with self.assertRaises(NativeUIError),owner.operation():
            self.clock=140.
            with owner.operation():self.clock=160.;self.sdk.send()
        self.assertEqual(1,len(self.sdk.requests));self.sdk.send();self.assertEqual(2,len(self.sdk.requests))
    def test_clock_rollback_remains_rejected_through_later_clock_recovery(self):
        def actual(_self,_selector,_operation,_values):
            self.clock=2.;self.sdk.send();self.clock=1.
            with self.assertRaises(NativeUIError):self.sdk.send()
            self.clock=3.;return self.sdk.send()
        with self.assertRaises(NativeUIError):self.wrap(actual)(self,'test-selector','feature.tablet-web.cleanup',{})
        self.assertEqual(1,len(self.sdk.requests))


if __name__=='__main__':unittest.main()
