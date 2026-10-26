"""Actual installed-candidate gate and existing-session Pending factory."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import unittest
from feature_journeys.witness import Client
from ios.adapters.snapshot_pending_runtime import IOSSnapshotPendingRuntime
from ios.self_tests.test_ios_script_runtime import IOSScriptRuntimeTests


class SnapshotPendingFactoryTests(unittest.TestCase):
    def setUp(self):
        self.fixture=IOSScriptRuntimeTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.runtime=IOSSnapshotPendingRuntime(self.fixture.f.adapter)
        self.phase=Client('https://controlled.invalid/feature-fixture/v1','r'*64)

    def test_real_installed_bytes_scope_lock_and_existing_session_are_retained_without_any_UI_command(self):
        f=self.fixture.f;before=(f.sessions,f.launches);commands=len(f.commands)
        with self.runtime.pending_owner('test-only','a'*32,self.phase) as owner:
            owner.lock.assert_held();owner.bound();self.assertTrue(f.adapter._session_recreation_forbidden)
            self.assertEqual('42',owner.binding['processIdentity']);self.assertEqual('test-only',owner.binding['sessionId'])
            self.assertEqual(f.adapter.fingerprint(),owner.binding['targetFingerprint']);self.assertEqual('pending-snapshot-owner.json',owner.store.path.name)
            self.assertIsNone(owner.previous);self.assertFalse(any(query.get('operation')=='edit' for _operation,query in f.commands[commands:]))
        self.assertFalse(f.adapter._session_recreation_forbidden);self.assertEqual(before,(f.sessions,f.launches))

    def test_replaced_actual_candidate_blocks_before_any_fixture_or_native_input_and_never_recreates(self):
        f=self.fixture.f;before=(f.sessions,f.launches)
        with self.assertRaises((ValueError,RuntimeError)):
            with self.runtime.pending_owner('test-only','a'*32,self.phase) as owner:
                commands=len(f.commands);f.artifact.write_bytes(b'Changed actual selected artifact')
                with self.assertRaises((ValueError,RuntimeError)):owner.cancel('f'*32)
                self.assertEqual(commands,len(f.commands));self.assertIsNone(owner.store.read())
        self.assertEqual(before,(f.sessions,f.launches));self.assertFalse(f.adapter._session_recreation_forbidden)


if __name__=='__main__':unittest.main()
