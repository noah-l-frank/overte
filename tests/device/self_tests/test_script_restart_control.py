"""Joined real input/handoff journals; only OS/native target boundaries simulated."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.restart_inputs import RestartInputs, RestartDeliveryUncertain, run_script_restart
from self_tests import test_script_restart_handoff as handoff_tests
from self_tests.test_native_feature_observation import Boundary


class ScriptRestartControlTests(unittest.TestCase):
    def setUp(self):
        self.fixture = handoff_tests.RestartHandoffTests()
        self.fixture.setUp(); self.addCleanup(self.fixture.doCleanups)
        f = self.fixture; self.manager = f.prepared()
        f.store.discard(f.store.read())  # Before the read-only prepare stage.
        self.handoff = f.handoff()
        self.store = PrivateFeatureState(f.path / 'restart-inputs.json')
        self.calls = []; self.running = True; self.restarted = False
        self.ignore_stop = self.ignore_launch = self.lost_stop = self.lost_launch = self.lost_adopt = False
        self.counter_delta = 1

    def flow(self):
        f = self.fixture
        return RestartInputs(self.store, [f.store, f.files.store, f.native.store], monotonic=lambda: f.clock)

    def source(self):
        f = self.fixture; source = Boundary()
        def observed(packet):
            packet.update(processId=32 if self.restarted else 31, instance=('a' if self.restarted else 'd') * 32,
                requestedEpochMs=f.epoch(), capturedEpochMs=f.epoch(),
                lifecycle=dict(backgrounds=0, activations=1 + (self.counter_delta if self.restarted else 0),
                               launches=1 + (self.counter_delta if self.restarted else 0)))
            packet['animationFence']['requestedEpochMs'] = packet['requestedEpochMs']
        source.mutate = observed
        reader = source.reader(); reader.pid = 32 if self.restarted else 31; reader.clock_ms = f.epoch
        reader.guard = lambda: self.running
        return (handoff_tests.NEW if self.restarted else handoff_tests.BINDING), reader

    def stop(self):
        self.calls.append('stop')
        if not self.ignore_stop: self.running = False
        if self.lost_stop: raise OSError('synthetic SDK receipt loss')
        return {'stopped': True}

    def launch(self):
        self.calls.append('launch')
        if not self.ignore_launch:
            self.fixture.new_process(); self.restarted = self.running = True
        if self.lost_launch: raise OSError('synthetic SDK receipt loss')
        return {'launched': True}

    def process(self): return dict(running=self.running, identity='31:original-start' if self.running else None)
    def prepare(self): return self.handoff.prepare(self.manager, self.fixture.old_execution)
    def adopt(self):
        result = self.fixture.adopt()
        if self.lost_adopt: self.lost_adopt = False; raise OSError('synthetic lost handoff return')
        return result
    def run_control(self):
        return run_script_restart(self.flow(), self.handoff, self.source, self.prepare,
            self.stop, self.process, self.launch, self.adopt)

    def test_one_normal_restart_joins_actual_lifecycle_original_files_and_three_second_absence(self):
        result = self.run_control()
        self.assertEqual(['stop', 'launch'], self.calls)
        self.assertEqual(2, result['native']['lifecycle']['launches'])
        self.assertEqual('ESRCH', result['handoff']['exit']['errorSymbol'])
        self.assertIsNone(self.handoff.store.read()); self.assertEqual('observed', self.store.read()['phase'])
        self.assertIsNotNone(self.store.read()['scriptHandoff'])
        self.assertEqual(handoff_tests.NEW, self.fixture.files.store.read()['binding'])
        self.assertEqual(1, sum(command['operation'] == 'stage' for command in self.fixture.storage.commands))

    def test_lost_sdk_receipts_resume_only_through_current_os_and_native_observations(self):
        self.lost_stop = self.lost_launch = True
        with self.assertRaises(RestartDeliveryUncertain): self.run_control()
        self.assertEqual(['stop'], self.calls)
        with self.assertRaises(RestartDeliveryUncertain): self.run_control()
        self.assertEqual(['stop', 'launch'], self.calls)
        self.run_control(); self.assertEqual(['stop', 'launch'], self.calls)
        self.assertEqual('observed', self.store.read()['phase'])

    def test_ignored_stop_ack_prevents_launch_and_is_never_replayed_on_reconstruction(self):
        self.ignore_stop = True
        for _ in range(2):
            with self.assertRaises(NativeUIError): self.run_control()
        self.assertEqual(['stop'], self.calls); self.assertEqual('stop-issued', self.store.read()['phase'])
        self.assertIsNotNone(self.handoff.store.read())

    def test_ignored_launch_or_missing_new_process_never_becomes_restart_success(self):
        self.ignore_launch = True
        for _ in range(2):
            with self.assertRaises(NativeUIError): self.run_control()
        self.assertEqual(['stop', 'launch'], self.calls)
        self.assertEqual('launch-issued', self.store.read()['phase'])

    def test_extra_actual_start_or_missing_activation_is_not_synthesized_into_expected_counts(self):
        self.counter_delta = 2
        with self.assertRaises(NativeUIError): self.run_control()
        self.assertEqual(['stop', 'launch'], self.calls); self.assertEqual('launch-issued', self.store.read()['phase'])
        self.assertEqual(handoff_tests.BINDING, self.fixture.files.store.read()['binding'])

    def test_unknown_kernel_exit_keeps_input_and_handoff_intent_and_recovers_without_replay(self):
        original = self.launch
        def launch():
            result = original(); self.fixture.presence.presence = 'unknown'; return result
        self.launch = launch
        with self.assertRaises(NativeUIError): self.run_control()
        self.assertEqual('observed', self.store.read()['phase'])
        self.assertIsNotNone(self.handoff.store.read()); self.fixture.presence.presence = 'absent'
        self.run_control(); self.assertEqual(['stop', 'launch'], self.calls)

    def test_lost_completed_handoff_return_restores_only_host_transaction_and_rechecks_current_native_state(self):
        self.lost_adopt = True
        with self.assertRaises(OSError): self.run_control()
        self.assertIsNone(self.handoff.store.read()); self.assertEqual('observed', self.store.read()['phase'])
        before = self.fixture.clock
        self.run_control()
        self.assertGreaterEqual(self.fixture.clock - before, 3)
        self.assertEqual(['stop', 'launch'], self.calls); self.assertIsNone(self.handoff.store.read())
        self.assertEqual(1, sum(command['operation'] == 'stage' for command in self.fixture.storage.commands))

    def test_changed_transferred_owner_cannot_be_adopted_after_lost_completion_receipt(self):
        self.lost_adopt = True
        with self.assertRaises(OSError): self.run_control()
        current = self.fixture.files.store.read(); changed = current | {'ownerToken': 'f' * 64}
        self.fixture.files.store.write(changed, current)
        with self.assertRaises(NativeUIError): self.run_control()
        self.assertIsNone(self.handoff.store.read()); self.assertEqual(['stop', 'launch'], self.calls)
        self.assertIsNotNone(self.store.read())

    def test_late_stop_is_a_deadline_failure_and_never_continues_to_launch_in_that_call(self):
        original = self.stop
        def slow(): result = original(); self.fixture.clock += 31; return result
        self.stop = slow
        with self.assertRaises(NativeUIError): self.run_control()
        self.assertEqual(['stop'], self.calls); self.assertEqual('stop-issued', self.store.read()['phase'])


if __name__ == '__main__': unittest.main()
