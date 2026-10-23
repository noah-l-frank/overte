"""Real loopback WebDriver sends under the original canonical Worlds budget."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import unittest

from adapters.normal_ui import NativeUIError
from ios.adapters.navigation_api_entry import installed_entry
from ios.self_tests import test_ios_sdk_operation_guard as sdk_tests


class NavigationAPIEntryTests(unittest.TestCase):
    def setUp(self):
        self.sdk=sdk_tests.SDKOperationGuardTests();self.sdk.setUp();self.addCleanup(self.sdk.doCleanups);self.clock=0.

    def wrap(self,function):return installed_entry(function,monotonic=lambda:self.clock)

    def test_slow_candidate_preparation_cannot_send_after_original_entry_deadline(self):
        def actual(_self,_selector,_operation,_values):self.clock=30.;return self.sdk.send()
        with self.assertRaises(NativeUIError):self.wrap(actual)(self,'owned','feature.world-navigation.act',{})
        self.assertEqual([],self.sdk.requests)

    def test_final_verification_is_guarded_and_unrelated_operation_remains_unchanged(self):
        def actual(_self,_selector,_operation,_values):
            self.sdk.send();self.clock=30.;return self.sdk.send()
        with self.assertRaises(NativeUIError):self.wrap(actual)(self,'owned','feature.world-navigation.observe',{})
        self.assertEqual(1,len(self.sdk.requests))
        def unrelated(_self,_selector,_operation,_values):self.clock=90.;return self.sdk.send()
        self.assertEqual(dict(received=True),self.wrap(unrelated)(self,'owned','app.foreground',{}))
        self.assertEqual(2,len(self.sdk.requests))

    def test_nested_entry_cannot_renew_the_original_transport_deadline(self):
        def inner(_self,_selector,_operation,_values):self.clock=31.;return self.sdk.send()
        def outer(_self,_selector,_operation,_values):
            self.clock=29.;return self.wrap(inner)(self,'owned','feature.world-navigation.terminal',{})
        with self.assertRaises(NativeUIError):self.wrap(outer)(self,'owned','feature.world-navigation.cleanup',{})
        self.assertEqual([],self.sdk.requests)

    def test_clock_rollback_stays_failed_after_clock_recovery(self):
        def actual(_self,_selector,_operation,_values):
            self.clock=2.;self.sdk.send();self.clock=1.
            with self.assertRaises(NativeUIError):self.sdk.send()
            self.clock=3.;return self.sdk.send()
        with self.assertRaises(NativeUIError):self.wrap(actual)(self,'owned','feature.world-navigation.cleanup',{})
        self.assertEqual(1,len(self.sdk.requests));self.sdk.send();self.assertEqual(2,len(self.sdk.requests))


if __name__=='__main__':unittest.main()
