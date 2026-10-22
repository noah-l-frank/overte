"""Real host lock inode, missing file and contended archive counterexamples."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import tempfile
import unittest
from adapters.normal_ui import NativeUIError
from adapters.script_feature.lock import ScriptSourceLock,ScriptSourceBusy
from ios.adapters.emote_archive_lock import ArchiveSourceLock


class ArchiveLockTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name);self.root.chmod(0o700);self.path=self.root/'script-feature-sources.lock'
    def test_existing_original_inode_is_shared_readonly_and_released(self):
        source=ScriptSourceLock(self.path)
        with source.held():pass
        before=self.path.stat();original=self.path.read_bytes();lock=ArchiveSourceLock(self.path)
        with lock.held():
            lock.assert_held()
            with ArchiveSourceLock(self.path).held():pass
        after=self.path.stat();self.assertIsNone(lock._owner)
        self.assertEqual((before.st_ino,before.st_mtime_ns,before.st_ctime_ns),(after.st_ino,after.st_mtime_ns,after.st_ctime_ns))
        self.assertEqual(original,self.path.read_bytes())
        with source.held():source.assert_held()
    def test_missing_lock_is_never_created(self):
        with self.assertRaises(FileNotFoundError):
            with ArchiveSourceLock(self.path).held():self.fail('Missing original was admitted')
        self.assertFalse(self.path.exists())
    def test_actual_exclusive_owner_blocks_historical_replay_without_changing_it(self):
        owner=ScriptSourceLock(self.path)
        with owner.held():
            before=self.path.stat()
            with self.assertRaises(ScriptSourceBusy):
                with ArchiveSourceLock(self.path).held():self.fail('Exclusive owner was bypassed')
            owner.assert_held();self.assertEqual(before.st_ino,self.path.stat().st_ino)
    def test_aliased_or_nonprivate_lock_is_refused(self):
        original=self.root/'actual.lock';original.write_bytes(b'');original.chmod(0o600);self.path.symlink_to(original)
        with self.assertRaises(OSError):
            with ArchiveSourceLock(self.path).held():self.fail('Aliased lock admitted')
        self.path.unlink();self.path.write_bytes(b'');self.path.chmod(0o644)
        with self.assertRaises(NativeUIError):
            with ArchiveSourceLock(self.path).held():self.fail('Public lock admitted')

    def test_exact_own_instance_can_nest_and_foreign_thread_cannot_borrow_its_descriptor(self):
        from concurrent.futures import ThreadPoolExecutor
        with ScriptSourceLock(self.path).held():pass
        lock=ArchiveSourceLock(self.path)
        def foreign():
            try:
                with lock.held():return 'borrowed'
            except NativeUIError:return 'rejected'
        with ThreadPoolExecutor(max_workers=1) as executor,lock.held():
            original=lock._owner
            with lock.held():
                lock.assert_held();self.assertIs(original,lock._owner)
                self.assertEqual('rejected',executor.submit(foreign).result(timeout=5))
            lock.assert_held();self.assertIs(original,lock._owner)
        self.assertIsNone(lock._owner)
