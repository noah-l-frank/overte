"""Original private ownership store and binding logic; synthetic OS/native sources."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from adapters.normal_feature_state import PrivateFeatureState
from ios.adapters.installed_code import InstalledCodeBinding, SDK
from ios.self_tests.test_ios_bundle_observation import Boundary


class InstalledCodeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.store = PrivateFeatureState(Path(self.temp.name) / 'installed-code.json')
        self.scope = dict(sourceRevision='a'*40, artifactSha256='e'*64, sessionId='test-only',
                          generation=1, targetFingerprint='c'*64)
        self.native = Boundary(); self.reader = self.native.reader()
        self.process = dict(bundleId=self.native.bundle['bundleId'], pid=42, foreground=True)
        self.source = dict(processSourceVersion=1, source='dvt-bundle-pid-xcuitest-state',
                           instance='d'*32, available=True, cleanupPending=False, sdk=dict(SDK))
        self.binding = self.make()

    def make(self, scope=None):
        return InstalledCodeBinding(self.store, scope or self.scope, self.native.bundle,
            lambda: deepcopy(self.process), lambda: deepcopy(self.source), self.reader.read)

    def active(self):
        self.binding.begin()
        self.assertEqual('preparing', self.store.read()['phase'])
        result = self.binding.bind()
        self.assertEqual('bound', self.store.read()['phase'])
        return result

    def test_measured_bundle_after_journaled_launch_then_new_nonce_on_every_verification(self):
        claim = self.active(); original = self.store.read()
        self.assertEqual(dict(schemaVersion=1, sourceRevision='a'*40, artifactSha256='e'*64,
                              installedCandidateVerified=True), claim)
        self.assertNotEqual(claim['artifactSha256'], original['observation']['bundle']['bundleSha256'])
        self.assertEqual(claim, self.make().verify())
        actual = self.store.read()['observation']
        self.assertGreater(actual['sequence'], original['observation']['sequence'])
        self.assertNotEqual(actual['commandId'], original['observation']['commandId'])
        self.assertEqual({'schemaVersion','commandId','action'}, set(self.native.commands[-1]))

    def test_abandoned_launch_intent_cannot_be_adopted_by_new_cli_or_repeated_begin(self):
        self.binding.begin()
        for action in (self.make().bind, self.make().begin, self.make().verify):
            with self.assertRaises(ValueError): action()
        self.assertEqual('preparing', self.store.read()['phase'])

    def test_no_ack_or_missing_foreign_bundle_can_establish_identity(self):
        self.binding.begin()
        for value in (None, {'performed':True}, {'bundle':self.native.bundle}):
            self.binding.native_bundle = lambda:value
            with self.assertRaises((ValueError, RuntimeError)): self.binding.bind()
            self.assertEqual('preparing', self.store.read()['phase'])
        self.binding.native_bundle = self.reader.read
        self.native.mutate = lambda v:v.update(bundle=dict(v['bundle'], bundleSha256='f'*64))
        with self.assertRaises((ValueError, RuntimeError)): self.binding.bind()

    def test_pid_session_generation_source_artifact_or_target_switch_fails(self):
        self.active()
        for key, value in (('sessionId','foreign'), ('generation',2), ('sourceRevision','f'*40),
                           ('artifactSha256','f'*64), ('targetFingerprint','f'*64)):
            with self.subTest(key=key), self.assertRaises(ValueError): self.make(dict(self.scope, **{key:value})).verify()
        self.process['pid'] = 43
        with self.assertRaises(ValueError): self.binding.verify()
        self.process = None
        with self.assertRaises(ValueError): self.binding.verify()

    def test_plugin_replacement_missing_poisoned_pending_or_wrong_sdk_fails(self):
        self.active(); original = deepcopy(self.source)
        for edit in ({'instance':'e'*32}, {'available':False}, {'cleanupPending':True},
                     {'processSourceVersion':True}, {'sdk':dict(SDK, remoteXpc='5.15.4')}, {'extra':True}):
            self.source = original | edit
            with self.subTest(edit=edit), self.assertRaises(ValueError): self.binding.verify()
        self.source = None
        with self.assertRaises(ValueError): self.binding.verify()

    def test_foreign_instance_old_frame_nonce_prepare_time_and_changed_bytes_fail(self):
        self.active(); old = deepcopy(self.store.read()['observation'])
        for edit in ({'instance':'e'*32}, {'commandId':old['commandId']}, {'sequence':old['sequence']},
                     {'preparedEpochMs':18000}, {'bundle':dict(self.native.bundle, executableSha256='f'*64)}):
            self.binding.native_bundle = lambda:old | edit
            with self.subTest(edit=edit), self.assertRaises(ValueError): self.binding.verify()
        self.assertEqual(old, self.store.read()['observation'])

    def test_source_or_pid_changes_during_original_bundle_transfer_fail_without_new_claim(self):
        self.active(); old = self.store.read(); read = self.reader.read
        for fault in ('pid','source'):
            def altered():
                value = read()
                if fault == 'pid': self.process['pid'] += 1
                else:self.source['instance'] = 'e'*32
                return value
            self.binding.native_bundle = altered
            with self.assertRaises(ValueError): self.binding.verify()
            self.assertEqual(old, self.store.read())
            self.process['pid'] = 42; self.source['instance'] = 'd'*32

    def test_background_only_allows_continuity_and_never_returns_fresh_byte_identity(self):
        self.active(); self.process['foreground'] = False
        self.assertFalse(self.binding.continuity(allow_background=True)['foreground'])
        with self.assertRaises(ValueError): self.binding.verify()
        self.process['foreground'] = True
        self.assertTrue(self.binding.verify()['installedCandidateVerified'])

    def test_retirement_requires_actual_absence_before_new_launch_and_new_instance(self):
        self.active(); self.binding.begin_retirement()
        with self.assertRaises(ValueError): self.binding.finish_retirement()
        with self.assertRaises(ValueError): self.make().begin()
        self.process = None; self.binding.finish_retirement()
        self.assertEqual('retired', self.store.read()['phase'])
        new = self.make(); new.begin(); self.process = dict(bundleId=self.native.bundle['bundleId'],pid=42,foreground=True)
        # PID reuse is possible. The old original source instance still fails.
        with self.assertRaises(ValueError): new.bind()
        self.native.mutate = lambda v:v.update(instance='e'*32)
        new.native_bundle = self.native.reader().read
        self.assertTrue(new.bind()['installedCandidateVerified'])

    def test_private_store_rejects_symlink_world_readable_and_unknown_ownership(self):
        self.active(); old = self.store.read()
        self.store.path.chmod(0o644)
        with self.assertRaises(RuntimeError):self.make().verify()
        self.store.path.chmod(0o600)
        self.store.write(dict(old,unknown=True), old)
        with self.assertRaises(ValueError):self.make().verify()


if __name__ == '__main__':unittest.main()
