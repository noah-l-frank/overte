"""Existing lifecycle responsibility is resumed before foreground-only factories."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from types import SimpleNamespace
import unittest
from adapters.normal_ui import NativeUIError
from ios.adapters.emote_feature import IOSEmoteFeature
from ios.self_tests import test_ios_emote_lifecycle as lifecycle_boundary
from ios.self_tests.test_ios_emote_sources import BINDING,RUN


class BackgroundRecoveryTests(unittest.TestCase):
    # Reuse the actual ordinary-input/native source boundary, not its tests.
    setUp=lifecycle_boundary.BackgroundTests.setUp
    tearDown=lifecycle_boundary.BackgroundTests.tearDown
    sleep=lifecycle_boundary.BackgroundTests.sleep
    owner=lifecycle_boundary.BackgroundTests.owner
    call=lifecycle_boundary.BackgroundTests.call
    status=lifecycle_boundary.BackgroundTests.status
    invoke=lifecycle_boundary.BackgroundTests.invoke
    sources=lifecycle_boundary.BackgroundTests.sources
    read=lifecycle_boundary.BackgroundTests.read
    def flow(self):
        flow=object.__new__(IOSEmoteFeature)
        flow.role='primary';flow.runtime=self.runtime;flow.selector='owned';flow.run=RUN;flow.state=dict(binding=BINDING)
        flow.phase=SimpleNamespace(fixture_url=self.call()['fixtureUrl']);flow.lock=self.lock
        flow.monotonic=lambda:self.clock;flow.sleep=self.sleep
        return flow

    def test_owned_lost_home_cleanup_resumes_before_any_foreground_source(self):
        self.fault='lost-home'
        with self.assertRaises(OSError):self.owner().act(self.call())
        self.runtime.adapter._operation='feature.emotes.cleanup';self.fault=''
        self.flow().recover_background()
        self.assertEqual(['lifecycle.background','app.launch'],self.inputs)
        self.assertTrue(self.foreground);self.assertEqual('observed',self.owner().state['phase'])
        self.assertEqual('feature.emotes.cleanup',self.runtime.adapter._operation)
        count=self.native_reads;self.flow().recover_background()
        self.assertEqual(count,self.native_reads);self.assertEqual(2,len(self.inputs))

    def test_missing_journal_does_not_create_lifecycle_or_read_product(self):
        self.runtime.adapter._operation='feature.emotes.cleanup';self.flow().recover_background()
        self.assertEqual([],self.inputs);self.assertEqual(0,self.native_reads)
        self.assertIsNone(self.owner().previous)

    def test_unknown_foreground_delivery_is_never_repeated_during_cleanup(self):
        self.fault='ignored-activation'
        with self.assertRaises(NativeUIError):self.owner().act(self.call())
        self.assertFalse(self.foreground);self.runtime.adapter._operation='feature.emotes.cleanup';before=list(self.inputs)
        for _ in range(2):
            with self.assertRaises(NativeUIError):self.flow().recover_background()
            self.assertEqual(before,self.inputs)
        self.assertEqual('foreground-issued',self.owner().state['phase'])

    def test_cleanup_cannot_start_new_background_input(self):
        self.runtime.adapter._operation='feature.emotes.cleanup'
        with self.assertRaises(NativeUIError):self.owner().act(self.call())
        self.assertEqual([],self.inputs);self.assertTrue(self.foreground)
