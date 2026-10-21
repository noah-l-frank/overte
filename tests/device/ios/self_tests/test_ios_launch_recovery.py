"""Original journal/read paths with synthetic OS/native sources; no SDK/device IO."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from adapters.normal_feature_state import PrivateFeatureState
from adapters.restart_inputs import RestartInputs
from ios.self_tests import test_ios_installed_code as original
from self_tests.test_native_feature_observation import Boundary as NativeBoundary
from self_tests.test_native_process_presence import Boundary as PresenceBoundary


class LaunchRecoveryTests(unittest.TestCase):
    make = original.InstalledCodeTests.make

    def setUp(self):
        original.InstalledCodeTests.setUp(self)
        self.binding.begin(); self.binding.bind()
        self.inputs = RestartInputs(PrivateFeatureState(Path(self.temp.name) / 'restart-inputs.json'),
            [PrivateFeatureState(Path(self.temp.name) / name) for name in ('handoff.json', 'files.json', 'manager.json')],
            component_only=True)
        self.old = NativeBoundary(); self.old.mutate = lambda v: v.update(processId=42)
        old = self.old.reader(ios=True); old.pid = 42
        component = dict(scope='NATIVE_UI_COMPONENT_ONLY', processIdentity='42', sessionId='original-component',
                         generation=1, targetFingerprint='c'*64)
        self.inputs.capture(component, old)
        def stop():
            self.binding.begin_retirement(); self.process = None; self.binding.finish_retirement()
        self.inputs.stop(stop)
        def launch():
            self.make().begin()  # Persisted before the synthetic lost launch receipt.
            self.process = dict(bundleId=self.native.bundle['bundleId'], pid=43, foreground=True)
        self.inputs.launch(lambda: dict(running=False, identity=None), launch)
        self.native.mutate = lambda v: v.update(processId=43, instance='e'*32)
        self.native.clock_source = dict(processId=43, capturedEpochMs=20000)
        self.reader = self.native.reader(); self.reader.pid = 43
        self.binding = self.make()
        self.current = NativeBoundary()
        self.current.mutate = lambda v: v.update(processId=43, instance='f'*32,
            lifecycle=dict(backgrounds=0, activations=2, launches=2))
        self.native_reader = self.current.reader(ios=True); self.native_reader.pid = 43
        self.presence = PresenceBoundary(pid=43); self.presence.presence = 'absent'
        self.presence.edit = lambda v: v.update(instance='f'*32)
        self.presence_reader = self.presence.reader(ios=True)
        self.ready_calls = []

    def ready(self, process, after):
        self.ready_calls.append(deepcopy((process, after)))

    def recover(self, **kwargs):
        return self.binding.recover_prepared(self.inputs, self.native_reader, self.presence_reader,
            kwargs.pop('ready', self.ready), monotonic=kwargs.pop('monotonic', lambda: 0), **kwargs)

    def assert_rejected(self, **kwargs):
        before = self.store.read(); intent = self.inputs.store.read()
        with self.assertRaisesRegex(ValueError, '^OVT_IOS_INSTALLED_CODE_BINDING_REJECTED$'):
            self.recover(**kwargs)
        self.assertEqual(before, self.store.read()); self.assertEqual(intent, self.inputs.store.read())

    def test_explicit_readonly_recovery_retains_original_proof_and_allows_fresh_later_verification(self):
        intent = self.inputs.read(); before = self.store.read()
        self.assertTrue(self.recover()['installedCandidateVerified'])
        actual = self.store.read(); proof = actual['recovery']
        self.assertEqual(3, actual['bindingVersion']); self.assertEqual('bound', actual['phase'])
        self.assertEqual(before['source'], actual['source']); self.assertEqual(intent, self.inputs.read())
        self.assertEqual(42, proof['oldNative']['pid']); self.assertEqual('absent', proof['oldProcessAbsent']['presence'])
        self.assertEqual(self.native.value, proof['bundleObservation'])
        self.assertEqual(self.presence.value, proof['oldProcessAbsent'])
        self.assertEqual(self.current.sample, proof['finalNative']); self.assertEqual(1, len(self.ready_calls))
        self.assertEqual([(self.process, 20000)], self.ready_calls)
        self.native.clock_source['capturedEpochMs'] = 20100
        self.native.mutate = lambda v: v.update(processId=43, instance='e'*32, capturedEpochMs=20100)
        self.assertTrue(self.make().verify()['installedCandidateVerified'])
        self.assertEqual(proof, self.store.read()['recovery'])
        self.binding.begin_retirement(); self.process = None; self.binding.finish_retirement()
        self.assertEqual(proof, self.store.read()['recovery'])
        self.assertEqual({'feature-native-observe'}, {v['action'] for v in self.current.commands})
        self.assertEqual({'feature-process-presence'}, {v['action'] for v in self.presence.commands})

    def test_ordinary_reconstruction_does_not_adopt_or_repeat_a_prepared_launch(self):
        for action in (self.make().begin, self.make().bind, self.make().verify):
            with self.assertRaises(ValueError): action()
        self.assertEqual('preparing', self.store.read()['phase'])
        self.assertEqual([], self.current.commands)

    def test_first_launch_or_legacy_missing_prelaunch_source_cannot_be_recovered(self):
        current = self.store.read()
        self.store.write(dict(current, previousInstance=None), current)
        self.assert_rejected()
        self.store.write({k: v for k, v in dict(current, bindingVersion=1, source=None).items() if k != 'recovery'}, self.store.read())
        self.assert_rejected()
        self.assertEqual([], self.current.commands)

    def test_nonlaunch_restart_phase_cannot_recover_or_query_native_sources(self):
        value = self.inputs.read(); self.inputs.store.write(dict(value, phase='stop-issued'), value)
        self.assert_rejected(); self.assertEqual([], self.current.commands)

    def test_wrong_target_generation_or_old_pid_cannot_adopt_foreign_intent(self):
        original = self.inputs.read()
        for key, value in (('targetFingerprint', 'e'*64), ('generation', 2), ('processIdentity', '43')):
            changed = dict(original, oldBinding=dict(original['oldBinding'], **{key: value}))
            if key == 'processIdentity': changed['oldNative'] = dict(original['oldNative'], pid=43)
            self.inputs.store.write(changed, self.inputs.store.read())
            self.assert_rejected()
        self.inputs.store.write(original, self.inputs.store.read())

    def test_nonios_readers_cannot_be_substituted(self):
        self.native_reader.ios = False; self.assert_rejected()
        self.native_reader.ios = True; self.presence_reader.ios = False; self.assert_rejected()
        self.assertEqual([], self.current.commands)

    def test_source_replacement_background_missing_or_foreign_pid_remains_owned(self):
        self.source['instance'] = 'e'*32; self.assert_rejected(); self.source['instance'] = 'd'*32
        for value in (None, dict(self.process, foreground=False), dict(self.process, pid=44)):
            self.process = value; self.assert_rejected()

    def test_unknown_or_still_live_old_process_is_not_absence(self):
        for state in ('unknown', 'present'):
            self.presence.presence = state; self.assert_rejected()
        self.assertEqual([], self.ready_calls)

    def test_foreign_absence_instance_or_old_native_capture_cannot_join(self):
        for edit in ({'instance': 'b'*32}, {'capturedEpochMs': 19999, 'requestedEpochMs': 19999}):
            self.presence.edit = lambda v: v.update(edit)
            self.assert_rejected()
        self.assertEqual([], self.ready_calls)

    def test_wrong_native_birth_or_lifecycle_counts_cannot_be_retimed_into_restart(self):
        for edit in ({'instance': 'a'*32}, {'lifecycle': dict(backgrounds=0, activations=2, launches=1)},
                     {'lifecycle': dict(backgrounds=0, activations=1, launches=2)}):
            self.current.mutate = lambda v: v.update(dict(processId=43, instance='f'*32,
                lifecycle=dict(backgrounds=0, activations=2, launches=2)) | edit)
            self.assert_rejected()

    def test_readiness_failure_or_source_switch_cannot_promote_preparing_binding(self):
        def failed(*_): raise RuntimeError('Synthetic readiness failure')
        self.assert_rejected(ready=failed)
        def switched(*_): self.source['instance'] = 'e'*32
        self.assert_rejected(ready=switched)

    def test_original_bundle_bytes_or_previous_bundle_birth_are_not_new_identity(self):
        for edit in ({'instance': 'c'*32}, {'bundle': dict(self.native.bundle, bundleSha256='f'*64)}):
            self.native.mutate = lambda v: v.update(dict(processId=43, instance='e'*32) | edit)
            self.assert_rejected()

    def test_deadline_invalid_and_regressing_monotonic_clocks_fail_without_commit(self):
        for value in (float('nan'), float('inf'), True, -1):
            self.assert_rejected(monotonic=lambda: value)
        for clock in ((0, 30), (1, 0)):
            values = iter(clock)
            self.assert_rejected(monotonic=lambda: next(values))

    def test_deadline_includes_readiness_and_preserves_both_journals(self):
        current = [0]
        def ready(*_): current[0] = 30
        self.assert_rejected(ready=ready, monotonic=lambda: current[0])

    def test_postreadiness_process_switch_cannot_escape_final_fence(self):
        def ready(*_): self.process['pid'] = 44
        self.assert_rejected(ready=ready)

    def test_tampered_original_proof_and_boolean_versions_fail_on_reconstruction(self):
        self.recover(); original = self.store.read()
        for field, value in (('launchRecoveryVersion', True), ('oldNative', dict(original['recovery']['oldNative'], pid=43)),
                             ('finalNative', original['recovery']['firstNative'])):
            self.store.write(dict(original, recovery=dict(original['recovery'], **{field: value})), self.store.read())
            with self.assertRaises((ValueError, RuntimeError)): self.make().record()
        self.store.write(original, self.store.read())

    def test_legacy_v2_preparing_can_recover_only_with_original_source_and_explicit_intent(self):
        current = self.store.read()
        self.store.write({k: v for k, v in dict(current, bindingVersion=2).items() if k != 'recovery'}, current)
        self.assertTrue(self.recover()['installedCandidateVerified'])
        self.assertEqual(3, self.store.read()['bindingVersion'])


if __name__ == '__main__': unittest.main()
