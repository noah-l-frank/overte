"""Existing lock inode and paired exclusive serialization without recreation."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import tempfile
import unittest
from adapters.normal_ui import NativeUIError
from adapters.script_feature.lock import ScriptSourceLock,ScriptSourceBusy
from ios.adapters.emote_rooted_end_lock import held_existing
from ios.adapters.emote_observer import EmoteObservationPending


class RootedEndLockTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name);self.root.chmod(0o700);self.lock=ScriptSourceLock(self.root/'script-feature-sources.lock')
    def test_missing_historical_lock_is_not_created(self):
        with self.assertRaises(NativeUIError),held_existing(self.lock):self.fail('Missing lock acquired')
        self.assertFalse(self.lock.path.exists());self.assertIsNone(self.lock._owner)
    def test_existing_exclusive_lock_nests_only_for_the_shared_owner(self):
        with self.lock.held():pass
        inode=self.lock.path.stat().st_ino
        with held_existing(self.lock):
            self.lock.assert_held()
            with held_existing(self.lock):self.lock.assert_held()
            with self.assertRaises(ScriptSourceBusy),held_existing(ScriptSourceLock(self.lock.path)):self.fail('Foreign owner acquired')
        self.assertEqual(inode,self.lock.path.stat().st_ino);self.assertIsNone(self.lock._owner)
    def test_replaced_lock_inode_cannot_continue_historical_ownership(self):
        with self.lock.held():pass
        with self.assertRaises(NativeUIError),held_existing(self.lock):
            replacement=self.root/'replacement.lock';replacement.touch(mode=0o600);replacement.replace(self.lock.path)
            self.lock.assert_held()
        self.assertIsNone(self.lock._owner)
    def test_nested_existing_owner_preserves_the_original_body_exception(self):
        sentinel=EmoteObservationPending('Original pending body')
        with self.lock.held():
            owner=self.lock._owner
            with self.assertRaises(EmoteObservationPending) as caught:
                with held_existing(self.lock):raise sentinel
            self.assertIs(sentinel,caught.exception);self.assertIs(owner,self.lock._owner);self.lock.assert_held()
    def test_body_exception_cannot_skip_the_exit_inode_check(self):
        with self.lock.held():pass
        with self.assertRaises(NativeUIError),held_existing(self.lock):
            replacement=self.root/'replacement.lock';replacement.touch(mode=0o600);replacement.replace(self.lock.path)
            raise EmoteObservationPending('Pending cannot excuse lost original lock ownership')
        self.assertIsNone(self.lock._owner)


if __name__=='__main__':unittest.main()
