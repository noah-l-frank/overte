"""An actual dangling link is not an absent planned input/account original."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from adapters.normal_ui import NativeUIError
from ios.self_tests import test_ios_avatar_input_reads as inputs
from ios.self_tests import test_ios_avatar_account_reads as accounts


class AvatarPlannedOriginalTests(unittest.TestCase):
    def check_planned_link(self,owner,rebuild,commands):
        intent=owner.originals.intent
        def interrupted(kind,value):
            intent(kind,value)
            if value['phase']=='planned':raise OSError('Actual planned native file journal return lost')
        owner.originals.intent=interrupted
        with self.assertRaises(NativeUIError):owner.read()
        original=deepcopy(owner.state['pending']['original']);self.assertEqual('planned',original['phase'])
        path=owner.originals.path(original);self.assertFalse(path.exists());path.symlink_to(path.with_name('missing-native-original'))
        self.assertFalse(path.exists());self.assertTrue(path.is_symlink());before=deepcopy(commands);metadata=owner.store.path.read_bytes()
        for attempt in (lambda:owner.partial_file(original),owner.recover,lambda:rebuild().read()):
            with self.assertRaises(NativeUIError):attempt()
        self.assertEqual(before,commands);self.assertEqual(metadata,owner.store.path.read_bytes());self.assertTrue(path.is_symlink())

    def test_actual_planned_input_link_stays_owned_and_blocks_recovery_or_another_query(self):
        fixture=inputs.AvatarInputReadsTests();fixture.setUp();self.addCleanup(fixture.doCleanups)
        self.check_planned_link(fixture.owner(),fixture.owner,fixture.requests)

    def test_actual_planned_account_link_uses_the_same_strict_reader_without_native_query_replay(self):
        fixture=accounts.AvatarAccountReadsTests();fixture.setUp();self.addCleanup(fixture.doCleanups)
        with fixture.lock.held():self.check_planned_link(fixture.owner(),fixture.owner,fixture.commands)


if __name__=='__main__':unittest.main()
