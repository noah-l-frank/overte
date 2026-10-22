"""Original reader transactions with synthetic native sources and host clock."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import sys
from pathlib import Path
import unittest
import uuid
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from adapters.chat_journey.no_replay import ChatNoReplay
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from feature_journeys.fixtures import context
from self_tests import test_chat_journey_samples as source_seams
from self_tests.test_native_chat_observation import RUN, SELF


class NoReplayTests(unittest.TestCase):
    def setUp(self):
        self.h = source_seams.ChatSamplesTests(); self.h.setUp(); self.addCleanup(self.h.doCleanups)
        self.actor = self.h.sampler(role='actor', store=PrivateFeatureState(self.h.root / 'chat-actor.json'))
        self.roles = (self.h.samples, self.actor)
        self.store = PrivateFeatureState(self.h.root / 'no-replay.json')
        self.clock = 0.; self.fault = None
        self.both()
        self.h.primary.mixer = self.h.peer.mixer = False; self.both()
        self.h.primary.mixer = self.h.peer.mixer = True; self.h.peer_mixer = 'f' * 64
        self.h.primary.mutate = lambda value: value['source'].update(mixerSha256='f' * 64)
        self.both()
        for boundary in (self.h.primary, self.h.peer, self.h.view, self.h.native):
            old = boundary.mutate
            def mutate(value, old=old):
                if old: old(value)
                value['capturedEpochMs'] = 20000 + int(self.clock * 1000)
            boundary.mutate = mutate
        for role in self.roles:
            role.monotonic = lambda: self.clock
            for reader in (role.primary, role.peer, role.view, role.lifecycle):
                reader.clock_ms = lambda: 20000 + int(self.clock * 1000)
        self.quiet = ChatNoReplay(*self.roles, self.store, monotonic=lambda: self.clock, sleep=self.sleep)

    def both(self):
        for role in self.roles: role.read(uuid.uuid4().hex, 20000)

    def sleep(self, seconds):
        self.clock += seconds
        if self.fault: self.fault()

    def wait(self): return self.quiet.wait('9' * 32, 20000)

    def test_full_native_and_host_time_window_requires_new_queries_for_both_roles(self):
        # Exercise the real journey's retained multiple channel histories;
        # repeated raw copies must not exhaust the private 64-KiB journal.
        self.h.open('domain')
        for key in ('unicode','reply','hidden','retry'):
            self.h.accept(context(RUN)[key], sender=SELF)
        before = [len(role.frames) for role in self.roles]
        result = self.wait()
        self.assertEqual('complete', result['phase']); self.assertGreaterEqual(result['elapsedMs'], 3000)
        self.assertGreaterEqual(len(result['samples']), 31)
        for samples in result['samples']:
            self.assertEqual(8, len({nonce for role in samples for nonce in role['queries']}))
        for index, role in enumerate(self.roles):
            self.assertGreater(len(role.frames), before[index] + 30)
        self.assertEqual(result, self.store.read())
        with self.assertRaises(NativeUIError): self.wait()
        with self.assertRaises(NativeUIError): ChatNoReplay(*self.roles, self.store)

    def test_replay_after_earlier_empty_reads_fails_and_keeps_original_window(self):
        def replay():
            if self.clock >= 1:
                self.h.peer.event(text=context(RUN)['retry'], sender=SELF)
                self.fault = None
        self.fault = replay
        with self.assertRaises(NativeUIError): self.wait()
        self.assertEqual('reading', self.store.read()['phase'])
        self.assertLess(self.clock, 3); self.assertTrue(self.store.read()['samples'])
        self.assertTrue(all(role.store.path.exists() for role in self.roles))

    def test_cached_native_time_cannot_pass_a_real_host_wait(self):
        for boundary in (self.h.primary, self.h.peer, self.h.view, self.h.native):
            old = boundary.mutate
            def stale(value, old=old): old(value); value['capturedEpochMs'] = 20000
            boundary.mutate = stale
        with self.assertRaises(NativeUIError): self.wait()
        self.assertNotEqual('complete', self.store.read()['phase'])

    def test_long_unobserved_gap_and_regressing_host_clock_are_rejected(self):
        for fault in ('gap', 'regression'):
            if fault == 'regression': self.setUp()
            self.fault = lambda: setattr(self, 'clock', self.clock + 2 if fault == 'gap' else -1)
            with self.subTest(fault=fault), self.assertRaises(NativeUIError): self.wait()
            self.assertNotEqual('complete', self.store.read()['phase'])

    def test_model_storage_or_mixer_change_cannot_be_replaced_by_an_empty_peer_ledger(self):
        self.fault = lambda: self.h.accept(context(RUN)['retry'], sender=SELF, local=True)
        with self.assertRaises(NativeUIError): self.wait()
        self.assertEqual('reading', self.store.read()['phase'])

    def test_no_original_outage_and_recovery_cannot_start_the_window(self):
        for role in self.roles: role.frames = [deepcopy(role.frames[-1])]
        with self.assertRaises(NativeUIError): self.wait()
        self.assertEqual('reading', self.store.read()['phase'])

    def test_same_role_or_shared_transcript_is_not_an_independent_publisher(self):
        with self.assertRaises(NativeUIError): ChatNoReplay(self.h.samples, self.h.samples, self.store)
        self.actor.role = 'primary'
        with self.assertRaises(NativeUIError): ChatNoReplay(*self.roles, self.store)


if __name__ == '__main__': unittest.main()
