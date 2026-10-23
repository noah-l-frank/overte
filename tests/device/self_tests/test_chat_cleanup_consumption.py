"""Strict actual cleanup-source join; full external journey/cursors remain absent.

The positive uses the actual shared wait and same hook emitter as execute,
not a complete external execute. Native/input/clock producers are seams.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest

from adapters.chat_journey.cleanup_consumption import ChatCleanupConsumption
from adapters.normal_ui import NativeUIError
from feature_journeys.engine import Journey
from feature_journeys.scenarios import SCENARIOS
from self_tests import test_chat_cleanup_baseline as seams


class ChatCleanupConsumptionTests(unittest.TestCase):
    def setUp(self):
        self.h=seams.ChatCleanupBaselineTests();self.h.setUp();self.addCleanup(self.h.doCleanups)
        self.owner=self.h.owner;self.consumer=ChatCleanupConsumption(self.owner)
        def no_input(*_args,**_kwargs):raise AssertionError('No actual input is authorized')
        self.journey=Journey('chat',self.owner.scope['runId'],self.owner.scope['fixtureUrl'],
            invoke=self.owner.invoke,witness=self.owner.received,activate=no_input,read_artifact=no_input,
            image_policy={},continuity=lambda *_args:self.owner.control(),monotonic=self.owner.primary.monotonic,
            epoch_ms=self.owner.primary.source.epoch_ms,sleep=self.owner.sleep,report=no_input,
            after_cleanup_baseline=self.consumer.callback)
        self.consumer.attach(self.journey);self.consumer.begin()
        self.journey.required_lifecycle=deepcopy(self.owner.actor.active_original['lifecycle']['lifecycle'])
        self.ticket=self.h.h.ticket;self.barrier=self.h.h.native.epoch

    def wait(self):
        self.journey.wait('cleanup-restored-baseline',self.ticket,self.barrier,
            deepcopy(SCENARIOS['chat']['baseline']),['peer'],duration=3)

    def test_same_original_wait_hook_consumes_sources_once_then_seals_without_duplicate_baseline(self):
        self.wait();queries=self.h.h.queries();posts=len(self.h.h.posts)
        self.journey.consumed_cleanup(self.ticket,self.barrier,0)
        self.assertTrue(self.consumer.completed);self.assertFalse(self.consumer.failed)
        value=self.consumer.receipt();self.assertEqual('complete',value['stage'])
        self.assertEqual(value,self.owner.receipt(value))
        self.assertEqual(queries,self.h.h.queries());self.assertEqual(posts,len(self.h.h.posts))
        self.assertEqual(len(self.journey.samples),len(self.owner.rows))
        self.assertEqual(1,value['externalConsumptionVersion'])
        self.assertEqual(self.journey.sequence,value['externalConsumption']['header']['finalSequence'])
        self.assertFalse(value['externalConsumption']['header']['sequenceSucceeded'])
        self.assertTrue(all(seal.completed for seal in self.owner.seals))
        with self.assertRaises(NativeUIError):self.consumer.consume(self.consumer.raw)
        with self.assertRaises(NativeUIError):self.owner.run(self.barrier)
        self.assertEqual(queries,self.h.h.queries());self.assertEqual(posts,len(self.h.h.posts))

    def test_caller_bytes_cannot_start_seals_or_adopt_engine_consumption(self):
        before=self.h.h.queries();posts=len(self.h.h.posts)
        with self.assertRaises(NativeUIError):self.consumer.consume(b'{}')
        self.assertTrue(self.consumer.failed);self.assertTrue(all(seal.failed for seal in self.owner.seals))
        self.assertFalse(any(seal.completed for seal in self.owner.seals))
        self.assertEqual(before,self.h.h.queries());self.assertEqual(posts,len(self.h.h.posts))
        self.assertEqual('external-observing',self.owner.store.read()['stage'])
        with self.assertRaises(NativeUIError):self.owner.actor.publish()

    def test_prior_external_cursor_is_never_translated_to_private_phase_or_source_count(self):
        # Explicit cursor-boundary seam; no claim that this fixture executed
        # earlier public phases. It must fail before any source acquisition.
        self.journey.sequence=100;before=self.h.h.queries();posts=len(self.h.h.posts)
        with self.assertRaises(NativeUIError):self.wait()
        self.assertEqual(before,self.h.h.queries());self.assertEqual(posts,len(self.h.h.posts))
        self.assertFalse(self.consumer.issued);self.assertFalse(self.consumer.completed)
        self.assertFalse(any(seal.completed for seal in self.owner.seals))
        self.assertIsNone(self.journey.cleanup_consumption)

    def test_frozen_host_native_jump_after_last_baseline_cas_quarantines_consumed_sources(self):
        self.wait();write=self.owner.store.write;queries=self.h.h.queries();posts=len(self.h.h.posts)
        def late(value,previous):
            write(value,previous)
            if value['stage']=='complete':self.h.h.native.epoch+=2000
        self.owner.store.write=late
        with self.assertRaises(NativeUIError):self.journey.consumed_cleanup(self.ticket,self.barrier,0)
        self.assertTrue(self.consumer.failed);self.assertFalse(self.consumer.completed)
        self.assertTrue(self.owner.failed);self.assertFalse(self.owner.completed)
        self.assertTrue(all(seal.failed for seal in self.owner.seals))
        self.assertEqual(queries,self.h.h.queries());self.assertEqual(posts,len(self.h.h.posts))
        self.assertEqual('complete',self.owner.store.read()['stage'])
        with self.assertRaises(NativeUIError):self.consumer.receipt()


if __name__=='__main__':unittest.main()
