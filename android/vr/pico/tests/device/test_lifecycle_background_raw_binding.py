"""Actual early cleanup and kernel ownership for opt-in Background3 storage."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import hashlib
import os
from pathlib import Path
import unittest

from test_create_operation_binding import CreateOperationBindingTests
from adapters.native_fd_owner import OriginalDescriptor
from adapters.pico4 import lifecycle_background_raw_state as state


class BackgroundRawBindingTests(CreateOperationBindingTests):
    def directory(self):
        key=hashlib.sha256(('org.overte.pico\0'+self.native.target).encode()).hexdigest()[:32]
        directory=Path(self.adapter.pico_configuration[1])/('feature-scripts-'+key)
        directory.mkdir(mode=0o700,exist_ok=True);return directory

    def test_root_and_rootless_raw_names_block_before_source_input_or_base_stop(self):
        names=(state.NAME,state.NAME+'.part-000.bin',state.NAME+'.index-00.json',
            state.NAME+'.pending-unknown',state.NAME+'.unexpected')
        for index,name in enumerate(names):
            with self.subTest(name=name):
                if index:self.setUp()
                path=self.directory()/name
                with os.fdopen(os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600),'wb') as stream:
                    stream.write(b'unknown original responsibility\n')
                self.refused_before_io()

    def test_dangling_raw_part_is_retained_without_opening_or_adopting_it(self):
        path=self.directory()/(state.NAME+'.part-unknown');path.symlink_to('missing-original')
        self.refused_before_io()
        self.assertTrue(path.is_symlink());self.assertEqual('missing-original',os.readlink(path))

    def test_known_original_host_pair_closes_without_creating_a_retention_record(self):
        directory=self.directory();owner=OriginalDescriptor(directory,os.O_RDONLY|os.O_DIRECTORY|os.O_CLOEXEC)
        before=list(state.UNRESOLVED)
        self.assertTrue(state.close_or_retain(directory,owner));self.assertTrue(owner.closed)
        self.assertEqual(before,state.UNRESOLVED)

    def test_actual_same_inode_recycled_half_remains_open_and_blocks_rootless_namespace(self):
        directory=self.directory();owner=OriginalDescriptor(directory,os.O_RDONLY|os.O_DIRECTORY|os.O_CLOEXEC)
        os.close(owner.fd);foreign=os.open(directory,os.O_RDONLY|os.O_DIRECTORY|os.O_CLOEXEC)
        self.assertEqual(owner.fd,foreign)
        try:
            self.assertFalse(state.close_or_retain(directory,owner))
            self.assertIn((directory,owner),state.UNRESOLVED)
            self.assertEqual(directory.lstat().st_ino,os.fstat(foreign).st_ino)
            self.assertTrue(state.retained_path(directory));self.refused_before_io()
            self.assertEqual(directory.lstat().st_ino,os.fstat(foreign).st_ino)
        finally:
            # Only the fixture that created the replacement can finalize it.
            os.close(foreign);os.close(owner.anchor)
            state.UNRESOLVED[:]=[(root,held) for root,held in state.UNRESOLVED if held is not owner]

    def test_raising_close_retains_actual_owner_and_preserves_original_failure_context(self):
        directory=self.directory()
        class FailedClose:
            def close(self):raise OSError('Explicit unavailable original close')
        owner=FailedClose()
        try:
            self.assertFalse(state.close_or_retain(directory,owner))
            self.assertIn((directory,owner),state.UNRESOLVED);self.refused_before_io()
        finally:state.UNRESOLVED[:]=[(root,held) for root,held in state.UNRESOLVED if held is not owner]


def load_tests(loader,tests,pattern):
    return unittest.TestSuite(BackgroundRawBindingTests(name)
        for name in sorted(BackgroundRawBindingTests.__dict__) if name.startswith('test_'))

if __name__=='__main__':unittest.main()
