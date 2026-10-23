"""A planned original pathname cannot hide an actual dangling symlink."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from adapters.normal_ui import NativeUIError
from ios.adapters.avatar_source_recovery import IOSAvatarSourceRecovery
from ios.self_tests import test_ios_avatar_source_recovery as fixture


class AvatarSourcePlannedTests(unittest.TestCase):
    def test_actual_planned_original_symlink_prevents_abandonment_and_any_new_query(self):
        f=fixture.AvatarSourceRecoveryTests();f.setUp();self.addCleanup(f.doCleanups)
        with f.lock.held():
            owner=f.sources();intent=owner.originals.intent;paths=[]
            def interrupted(kind,value):
                intent(kind,value)
                if kind=='original' and value['phase']=='planned':
                    path=owner.originals.path(value);path.symlink_to('missing-original-bytes');paths.append(path)
                    raise OSError('Actual reserved original path was replaced before open')
            owner.originals.intent=interrupted
            with self.assertRaises(OSError):owner.read()
            before=deepcopy(f.fixture.sources);sequence=f.fixture.core.sequence
            failure=None
            try:IOSAvatarSourceRecovery(owner).recover()
            except NativeUIError as error:failure=error
        # Assert outside the source-lock context so an assertion failure keeps
        # its actual cause instead of becoming the lock's generic boundary.
        self.assertEqual(1,len(paths));self.assertTrue(paths[0].is_symlink());self.assertFalse(paths[0].exists())
        self.assertIsNotNone(failure,'An actual reserved-path symlink was accepted as absent')
        self.assertEqual(before,f.fixture.sources);self.assertEqual(sequence,f.fixture.core.sequence)
        self.assertEqual('reading',owner.state['phase']);self.assertEqual('planned',owner.state['pending']['original']['phase'])


if __name__=='__main__':unittest.main()
