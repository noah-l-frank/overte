"""Actual stop transport cannot restart a nested finalization's original budget."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from ios.adapters.emote_session_cleanup import session_entry
from ios.self_tests import test_ios_sdk_operation_guard as fixture


class SessionBudgetTests(unittest.TestCase):
    def setUp(self):
        self.sdk=fixture.SDKOperationGuardTests();self.sdk.setUp();self.addCleanup(self.sdk.doCleanups)
        self.clock=0.;self.adapter=object()
    def wrap(self,function):return session_entry(function,monotonic=lambda:self.clock)
    def test_nested_cleanup_cannot_restart_original_stop_budget(self):
        def inner(*_):self.clock=61.;return self.sdk.send()
        nested=self.wrap(inner)
        def outer(adapter,selector):self.clock=40.;return nested(adapter,selector)
        with patch('ios.adapters.emote_session_cleanup.owned',return_value=True),self.assertRaises(NativeUIError):
            self.wrap(outer)(self.adapter,'existing')
        self.assertEqual([],self.sdk.requests)
        self.sdk.send();self.assertEqual(1,len(self.sdk.requests))
    def test_caught_clock_reversal_cannot_authorize_the_later_ordinary_stop(self):
        rejected=[]
        def cleanup(*_):
            self.clock=10.;self.sdk.send()
            self.clock=9.
            try:self.sdk.send()
            except NativeUIError:rejected.append('reversal')
            self.clock=11.
            try:self.sdk.send()
            except NativeUIError:rejected.append('latched')
        with patch('ios.adapters.emote_session_cleanup.owned',return_value=True),self.assertRaises(NativeUIError):
            self.wrap(cleanup)(self.adapter,'existing')
        self.assertEqual(['reversal','latched'],rejected);self.assertEqual(1,len(self.sdk.requests))
