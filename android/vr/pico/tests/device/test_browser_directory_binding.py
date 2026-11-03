"""Pending namespace moves refuse actual generic cleanup before any SDK IO."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import unittest
from test_create_operation_binding import CreateOperationBindingTests
from adapters.pico4.tablet_web_binding import archive_sentry_prefix


class BrowserDirectoryBindingTests(CreateOperationBindingTests):
    def test_rootless_file_directory_and_symlink_preserve_pending_move_before_base_stop(self):
        for index,kind in enumerate(('file','directory','symlink')):
            with self.subTest(kind=kind):
                if index:self.setUp()
                parent=Path(self.adapter.pico_configuration[1])
                path=parent/(archive_sentry_prefix(self.native.target)+'a'*32+'.json.pending')
                if kind=='file':path.write_bytes(b'original unresolved directory move\n')
                elif kind=='directory':path.mkdir(mode=0o700)
                else:path.symlink_to('missing-original')
                self.refused_before_io()


def load_tests(_loader,_tests,_pattern):
    return unittest.TestSuite([BrowserDirectoryBindingTests(
        'test_rootless_file_directory_and_symlink_preserve_pending_move_before_base_stop')])


if __name__=='__main__':unittest.main()
