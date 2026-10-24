"""Real host lock ownership and original protected-operation failures."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import os
from pathlib import Path
import tempfile
import unittest

from adapters.normal_ui import NativeUIError
from adapters.script_feature.lock import ScriptSourceLock,ScriptSourceBusy


class ScriptSourceLockTests(unittest.TestCase):
    def setUp(self):
        directory=tempfile.TemporaryDirectory();self.addCleanup(directory.cleanup)
        self.path=Path(directory.name)/'source.lock';self.lock=ScriptSourceLock(self.path,timeout=.03)

    def test_exact_pending_object_survives_and_descriptor_is_released(self):
        class Pending(NativeUIError):pass
        error=Pending('Private pending operation');entered=[]
        with self.assertRaises(Pending) as caught:
            with self.lock.held():
                entered.append(True);self.lock.assert_held();raise error
        self.assertIs(error,caught.exception);self.assertEqual([True],entered)
        self.assertIsNone(self.lock._owner)
        with ScriptSourceLock(self.path).held():pass

    def test_nested_failure_keeps_the_outer_owner_and_real_exclusion(self):
        error=ValueError('Private body failure')
        with self.lock.held():
            owner=self.lock._owner
            with self.assertRaises(ValueError) as caught:
                with self.lock.held():raise error
            self.assertIs(error,caught.exception);self.assertIs(owner,self.lock._owner)
            self.lock.assert_held()
            with self.assertRaises(ScriptSourceBusy):
                with ScriptSourceLock(self.path,timeout=.01).held():self.fail('Second owner acquired')
        self.assertIsNone(self.lock._owner)

    def test_busy_raised_by_the_body_is_not_replaced_or_retried(self):
        error=ScriptSourceBusy('Actual inner contention');calls=[]
        with self.assertRaises(ScriptSourceBusy) as caught:
            with self.lock.held():calls.append(True);raise error
        self.assertIs(error,caught.exception);self.assertEqual([True],calls)
        with self.lock.held():self.lock.assert_held()

    def test_changed_original_lock_still_overrides_a_body_failure(self):
        error=ValueError('Do not expose this after a corrupt lock')
        with self.assertRaisesRegex(NativeUIError,'^Script source serialization is unavailable$') as caught:
            with self.lock.held():
                self.path.write_bytes(b'changed');raise error
        self.assertIsNot(error,caught.exception);self.assertIsNone(self.lock._owner)
        with self.assertRaises(NativeUIError):
            with self.lock.held():self.fail('Changed lock admitted')

    def test_nested_bad_exit_is_checked_even_when_the_body_raises(self):
        with self.assertRaisesRegex(NativeUIError,'^Script source serialization is unavailable$'):
            with self.lock.held():
                with self.assertRaises(NativeUIError):
                    with self.lock.held():
                        os.chmod(self.path,0o644);raise ValueError('Private failure')
        self.assertIsNone(self.lock._owner)

    def test_same_empty_bytes_in_a_replacement_inode_cannot_release_as_valid(self):
        with self.assertRaisesRegex(NativeUIError,'^Script source serialization is unavailable$'):
            with self.lock.held():
                original=self.path.stat();replacement=self.path.with_suffix('.replacement')
                descriptor=os.open(replacement,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600);os.close(descriptor)
                os.replace(replacement,self.path)
                self.assertNotEqual(original.st_ino,self.path.stat().st_ino)
        self.assertIsNone(self.lock._owner)


if __name__=='__main__':unittest.main()
