"""Original parent/file descriptions; never close a same-file recycled FD."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import os
from pathlib import Path
import tempfile
import unittest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.pico4.lifecycle_process_file import LifecycleProcessFile
from adapters.script_journey.history import canonical


class LifecycleProcessFileTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='lifecycle-process-file-');self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.root.chmod(0o700)
        self.store=PrivateFeatureState(self.root/'lifecycle-process-owner.json')
        self.owner=LifecycleProcessFile(self.store);self.addCleanup(self.owner.close_host)
        self.value=dict(original='complete process writer bytes');self.owner.write(self.value,None)

    def test_own_atomic_save_keeps_exact_writer_bytes_and_retires_only_original_old_handles(self):
        old=self.owner.file;value=dict(original='next complete process writer bytes')
        self.owner.write(value,self.value);self.owner.guard()
        self.assertTrue(old.closed);self.assertIsNot(old,self.owner.file)
        self.assertEqual(canonical(value)+b'\n',self.store.path.read_bytes())
        self.assertEqual([],list(self.root.glob('lifecycle-process-owner.json.pending-*')))

    def test_same_file_recycled_descriptor_is_not_adopted_or_closed(self):
        descriptor=self.owner.file.fd
        replacement=os.open(self.store.path,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC)
        try:os.dup2(replacement,descriptor,inheritable=False)
        finally:os.close(replacement)
        try:
            with self.assertRaises(NativeUIError):self.owner.guard()
            self.assertFalse(self.owner.close_host())
            self.assertEqual(self.owner.file.node,(os.fstat(descriptor).st_dev,os.fstat(descriptor).st_ino))
        finally:os.close(descriptor) # Only the test's known replacement, not its lost original alias.

    def test_same_bytes_replaced_original_parent_refuses_new_directory(self):
        raw=self.store.path.read_bytes();original=self.root.with_name(self.root.name+'-original')
        self.root.rename(original);self.root.mkdir(mode=0o700)
        self.store.path.write_bytes(raw);self.store.path.chmod(0o600)
        with self.assertRaises(NativeUIError):self.owner.guard()
        self.assertEqual(raw,(original/self.store.path.name).read_bytes())


if __name__=='__main__':unittest.main()
