"""Real SDK HTTP sends stay bounded from canonical entry through final verify."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import unittest
from adapters.normal_ui import NativeUIError
from ios.adapters.emote_api_entry import installed_entry
from ios.self_tests import test_ios_sdk_operation_guard as sdk_boundary


class APIEntryTests(unittest.TestCase):
    def setUp(self):
        self.sdk=sdk_boundary.SDKOperationGuardTests();self.sdk.setUp();self.addCleanup(self.sdk.doCleanups)
        self.time=0.
    def wrap(self,function):return installed_entry(function,monotonic=lambda:self.time)

    def test_slow_initial_candidate_check_cannot_send_before_flow_factory_or_after_return(self):
        checkpoints=[]
        def invoke(_adapter,_selector,_operation,_values):
            checkpoints.append('candidate-start');self.time=25.
            self.sdk.send();checkpoints.append('factory')
        with self.assertRaises(NativeUIError):self.wrap(invoke)(object(),'owned','feature.emotes.act',{})
        self.assertEqual(['candidate-start'],checkpoints);self.assertEqual([],self.sdk.requests)
        self.sdk.send();self.assertEqual(1,len(self.sdk.requests))

    def test_final_binding_verification_has_the_original_entry_deadline(self):
        def invoke(_adapter,_selector,_operation,_values):
            self.time=1.;self.sdk.send() # Ordinary feature input.
            self.time=26.;self.sdk.send() # Canonical final verification.
        with self.assertRaises(NativeUIError):self.wrap(invoke)(object(),'owned','feature.emotes.act',{})
        self.assertEqual(1,len(self.sdk.requests))

    def test_nested_invocation_cannot_restart_budget_or_clear_expiration(self):
        failures=[]
        def inner(_adapter,_selector,_operation,_values):self.time=26.;self.sdk.send()
        nested=self.wrap(inner)
        def outer(adapter,selector,_operation,values):
            self.time=10.
            try:nested(adapter,selector,'feature.emotes.act',values)
            except NativeUIError:failures.append('nested-expired')
            self.time=20.
            try:self.sdk.send()
            except NativeUIError:failures.append('still-expired')
            return {}
        with self.assertRaises(NativeUIError):self.wrap(outer)(object(),'owned','feature.emotes.act',{})
        self.assertEqual(['nested-expired','still-expired'],failures);self.assertEqual([],self.sdk.requests)

    def test_non_emote_default_and_owned_nested_ordinary_lifecycle_transport(self):
        def normal(_adapter,_selector,_operation,_values):return self.sdk.send()
        guarded=self.wrap(normal)
        self.assertEqual(dict(received=True),guarded(object(),'owned','app.launch',{}))
        def outer(adapter,selector,_operation,values):
            self.time=61.;return guarded(adapter,selector,'app.launch',values)
        with self.assertRaises(NativeUIError):self.wrap(outer)(object(),'owned','feature.emotes.cleanup',{})
        self.assertEqual(1,len(self.sdk.requests))
