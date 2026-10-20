"""One-send restart/lifecycle logic with synthetic OS and native boundaries."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.restart_inputs import RestartInputs, RestartDeliveryUncertain, validate_native_restart
from self_tests.test_native_feature_observation import Boundary

OLD = dict(sourceRevision='a' * 40, artifactSha256='b' * 64, targetFingerprint='c' * 64,
           processIdentity='123:old-start', sessionId='old-session', generation=1)
NEW = OLD | dict(processIdentity='124:new-start', sessionId='new-session', generation=2)


class RestartInputTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name); os.chmod(self.path, 0o700)
        self.store = PrivateFeatureState(self.path / 'restart-inputs.json')
        self.clock = 0.; self.calls = []; self.running = True
        self.before = Boundary(); self.after = Boundary()
        self.after.mutate = lambda packet: packet.update(processId=124, instance='d' * 32,
            lifecycle=dict(backgrounds=0, activations=2, launches=2))
        self.old_source, self.new_source = self.before.reader(), self.after.reader()
        self.new_source.pid = 124
        self.owners = [PrivateFeatureState(self.path / (name + '.json')) for name in ('handoff', 'files', 'manager')]

    def flow(self): return RestartInputs(self.store, self.owners, monotonic=lambda: self.clock)
    def stop(self): self.calls.append('stop'); self.running = False; return {'stopped': True}
    def launch(self): self.calls.append('launch'); self.running = True; return {'launched': True}
    def process(self): return dict(running=self.running, identity='123:old-start' if self.running else None)
    def inputs(self):
        self.flow().capture(OLD, self.old_source); self.flow().stop(self.stop)
        self.flow().launch(self.process, self.launch)

    def test_original_native_counters_and_one_normal_stop_launch_survive_reconstruction(self):
        self.inputs(); raw = self.flow().observe(NEW, self.new_source)
        self.assertEqual(['stop', 'launch'], self.calls)
        self.assertEqual(self.after.sample, raw)
        self.assertEqual(dict(backgrounds=0, activations=2, launches=2), self.store.read()['newNative']['lifecycle'])
        self.flow().retire(NEW, self.new_source); self.assertIsNone(self.store.read())

    def test_before_binding_native_comparison_is_read_only_and_refuses_old_birth_pid_or_counts(self):
        def measured(reader):
            value = reader.read(0)
            return dict(pid=value['processId'], instance=value['instance'], lifecycle=deepcopy(value['lifecycle']))
        old, new = measured(self.old_source), measured(self.new_source)
        original = deepcopy((old, new))
        self.assertIsNone(validate_native_restart(old, new))
        for change in (dict(pid=old['pid']), dict(instance=old['instance']),
                       dict(lifecycle=new['lifecycle'] | {'launches': old['lifecycle']['launches']}),
                       dict(lifecycle=new['lifecycle'] | {'launches': new['lifecycle']['launches'] + 1}),
                       dict(lifecycle=new['lifecycle'] | {'activations': old['lifecycle']['activations']}),
                       dict(lifecycle=new['lifecycle'] | {'backgrounds': -1}), dict(pid=True)):
            with self.subTest(change=change), self.assertRaises(NativeUIError): validate_native_restart(old, new | change)
        self.assertEqual(original, (old, new)); self.assertEqual([], self.calls)
        self.assertIsNone(self.store.read())

    def test_uncertain_stop_and_launch_receipts_are_never_replayed_and_actual_state_can_resume(self):
        self.flow().capture(OLD, self.old_source)
        def uncertain_stop(): self.stop(); raise OSError('synthetic lost stop receipt')
        with self.assertRaises(RestartDeliveryUncertain): self.flow().stop(uncertain_stop)
        with self.assertRaises(NativeUIError): self.flow().stop(self.stop)
        def uncertain_launch(): self.launch(); raise OSError('synthetic lost launch receipt')
        with self.assertRaises(RestartDeliveryUncertain): self.flow().launch(self.process, uncertain_launch)
        with self.assertRaises(NativeUIError): self.flow().launch(self.process, self.launch)
        self.flow().observe(NEW, self.new_source); self.assertEqual(['stop', 'launch'], self.calls)

    def test_stop_ack_without_current_os_absence_prevents_any_launch(self):
        self.flow().capture(OLD, self.old_source)
        self.flow().stop(lambda: {'stopped': True})
        with self.assertRaises(NativeUIError): self.flow().launch(self.process, self.launch)
        self.assertEqual([], self.calls); self.assertEqual('stop-issued', self.store.read()['phase'])

    def test_missing_or_wrong_os_observation_cannot_be_empty_success(self):
        self.flow().capture(OLD, self.old_source); self.flow().stop(self.stop)
        for value in (None, {}, {'stopped': True}, {'running': 0, 'identity': None},
                      {'running': False, 'identity': '123:old-start'}):
            with self.subTest(value=value), self.assertRaises(NativeUIError):
                self.flow().launch(lambda: value, self.launch)
        self.assertEqual(['stop'], self.calls)

    def test_old_native_birth_pid_or_unchanged_actual_counters_cannot_prove_restart(self):
        self.inputs(); original = self.after.mutate
        for change in ({'instance': 'a' * 32}, {'processId': 123},
                       {'lifecycle': dict(backgrounds=0, activations=1, launches=2)},
                       {'lifecycle': dict(backgrounds=0, activations=2, launches=1)},
                       {'lifecycle': dict(backgrounds=0, activations=3, launches=3)}):
            def edit(packet): original(packet); packet.update(change)
            self.after.mutate = edit; self.new_source = self.after.reader(); self.new_source.pid = 124
            with self.subTest(change=change), self.assertRaises(NativeUIError): self.flow().observe(NEW, self.new_source)
            self.assertEqual('launch-issued', self.store.read()['phase'])

    def test_changed_candidate_target_or_source_fails_before_read_and_cannot_upgrade_component_scope(self):
        self.inputs()
        for change in ({'artifactSha256': 'f' * 64}, {'sourceRevision': 'f' * 40}, {'targetFingerprint': 'f' * 64},
                       {'scope': 'NATIVE_UI_COMPONENT_ONLY'}):
            with self.subTest(change=change), self.assertRaises(NativeUIError): self.flow().observe(NEW | change, self.new_source)
        self.assertEqual([], self.after.commands)

    def test_observed_restart_rejects_third_process_birth_and_regressing_counter(self):
        self.inputs(); self.flow().observe(NEW, self.new_source)
        original = self.after.mutate
        for change in ({'instance': 'e' * 32}, {'lifecycle': dict(backgrounds=0, activations=1, launches=2)}):
            def edit(packet): original(packet); packet.update(change)
            self.after.mutate = edit; self.new_source = self.after.reader(); self.new_source.pid = 124
            with self.subTest(change=change), self.assertRaises(NativeUIError): self.flow().observe(NEW, self.new_source)
        self.assertEqual('d' * 32, self.store.read()['newNative']['instance'])

    def test_retirement_requires_separate_owner_absence_and_current_native_guard(self):
        self.inputs(); self.flow().observe(NEW, self.new_source)
        for owner in self.owners:
            owner.write({'unresolved': True}, None)
            with self.assertRaises(NativeUIError): self.flow().retire(NEW, self.new_source)
            self.assertIsNotNone(self.store.read()); owner.discard(owner.read())
        self.after.guard_okay = False
        with self.assertRaises(NativeUIError): self.flow().retire(NEW, self.new_source)
        self.assertIsNotNone(self.store.read())

    def test_late_native_input_cannot_return_green_or_be_retried(self):
        self.flow().capture(OLD, self.old_source)
        def slow_stop(): self.stop(); self.clock = 31; return {'stopped': True}
        with self.assertRaises(NativeUIError): self.flow().stop(slow_stop)
        with self.assertRaises(NativeUIError): self.flow().stop(self.stop)
        self.assertEqual(['stop'], self.calls); self.assertEqual('stop-issued', self.store.read()['phase'])

    def test_journal_corruption_and_boolean_counters_cannot_authorize_more_input(self):
        self.flow().capture(OLD, self.old_source); frozen = self.store.read()
        for changed in (frozen | {'restartInputVersion': True}, frozen | {'phase': 'done'},
                        frozen | {'newNative': {'pid': 124}}, frozen | {'oldBinding': OLD | {'generation': True}}):
            self.store.write(changed, frozen)
            with self.assertRaises(NativeUIError): self.flow().stop(self.stop)
            self.store.write(frozen, changed)
        self.assertEqual([], self.calls)

    def test_reconstruction_cannot_substitute_empty_owner_paths_to_retire_input_intent(self):
        self.inputs(); self.flow().observe(NEW, self.new_source)
        substituted = [PrivateFeatureState(self.path / ('foreign-' + str(index) + '.json')) for index in range(3)]
        other = RestartInputs(self.store, substituted)
        with self.assertRaises(NativeUIError): other.retire(NEW, self.new_source)
        self.assertIsNotNone(self.store.read())
        with self.assertRaises(NativeUIError): RestartInputs(self.store, [self.store] * 3)

    def test_component_only_scope_survives_restart_and_cannot_upgrade_to_candidate_qualification(self):
        old = {key: OLD[key] for key in ('processIdentity', 'sessionId', 'generation', 'targetFingerprint')}
        old['scope'] = 'NATIVE_UI_COMPONENT_ONLY'
        new = {key: NEW[key] for key in ('processIdentity', 'sessionId', 'generation', 'targetFingerprint')}
        new['scope'] = 'NATIVE_UI_COMPONENT_ONLY'
        flow = RestartInputs(self.store, self.owners, component_only=True)
        flow.capture(old, self.old_source); flow.stop(self.stop); flow.launch(self.process, self.launch)
        with self.assertRaises(NativeUIError): flow.observe(NEW, self.new_source)
        self.assertEqual([], self.after.commands)
        flow.observe(new, self.new_source); self.assertNotIn('artifactSha256', self.store.read()['newBinding'])
        flow.retire(new, self.new_source); self.assertIsNone(self.store.read())

    def test_missing_stale_foreign_or_failed_native_getter_cannot_create_initial_input_intent(self):
        for fault in ('missing', 'stale', 'foreign', 'guard'):
            if fault == 'missing': self.before.ignored = True
            elif fault == 'stale': self.before.mutate = lambda packet: packet.update(capturedEpochMs=10000)
            elif fault == 'foreign': self.before.mutate = lambda packet: packet.update(processId=125)
            else: self.before.guard_okay = False
            with self.subTest(fault=fault), self.assertRaises(NativeUIError): self.flow().capture(OLD, self.old_source)
            self.assertIsNone(self.store.read()); self.assertEqual([], self.calls)
            self.before.ignored = False; self.before.mutate = None; self.before.guard_okay = True

    def test_late_os_absence_or_launch_keeps_exact_issued_phase_without_replay(self):
        self.flow().capture(OLD, self.old_source); self.flow().stop(self.stop)
        def late_process(): self.clock = 31; return self.process()
        with self.assertRaises(NativeUIError): self.flow().launch(late_process, self.launch)
        self.assertEqual('stop-issued', self.store.read()['phase']); self.assertEqual(['stop'], self.calls)
        self.clock = 0
        def late_launch(): result = self.launch(); self.clock = 31; return result
        with self.assertRaises(NativeUIError): self.flow().launch(self.process, late_launch)
        self.assertEqual('launch-issued', self.store.read()['phase'])
        with self.assertRaises(NativeUIError): self.flow().launch(self.process, self.launch)
        self.assertEqual(['stop', 'launch'], self.calls)


if __name__ == '__main__': unittest.main()
