"""Reconstructed owners reuse only guarded original bytes inside one API call."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import time
import unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from ios.adapters import avatar_api_entry as api
from ios.adapters.avatar_postlogout_parts import AvatarPostLogoutParts
from ios.self_tests.test_ios_avatar_postlogout_reads import AvatarPostLogoutReadsTests


class AvatarPostLogoutOperationCacheTests(AvatarPostLogoutReadsTests):
    def test_operation_reconstruction_still_guards_every_actual_source_file(self):
        with api.scope(time.monotonic):
            owner=self.owner();row=owner.capture();proof=owner.proof(row);calls=deepcopy(self.calls)
            with patch.object(AvatarPostLogoutParts,'row_partial_original',side_effect=AssertionError('Unexpected repeated immutable decode')):
                rebuilt=self.owner();self.assertIs(owner.part_cache,rebuilt.part_cache)
                self.assertIs(owner.account_cache,rebuilt.account_cache)
                self.assertEqual(proof,rebuilt.proof(rebuilt.state['rows'][0]));self.assertEqual(calls,self.calls)
                parent=rebuilt.row_partial(row)['parts']['model'];path=rebuilt.segments.store.path(parent['chunks'][0])
                raw=path.read_bytes();before=path.stat();path.write_bytes(raw)
                self.assertEqual(before.st_ino,path.stat().st_ino)
                with self.assertRaises(NativeUIError):self.owner()
            self.assertEqual(calls,self.calls)

    def test_operation_reconstruction_preserves_actual_planned_path_absence(self):
        with api.scope(time.monotonic):
            owner=self.owner();intent=owner.segments.intent;lost=[]
            def actual(parent):
                intent(parent)
                if parent['label']=='parts' and parent['chunks'] and parent['chunks'][-1]['phase']=='planned' and not lost:
                    lost.append(True);raise OSError('Lost actual planned carrier return')
            owner.segments.intent=actual
            with self.assertRaises(OSError):owner.capture()
            recovered=self.owner();row=recovered.recover();calls=deepcopy(self.calls)
            rebuilt=self.owner();self.assertEqual({},rebuilt.row_parts(row));self.assertEqual(calls,self.calls)
            parent=rebuilt.row_partial(row)['parts']['before'];path=rebuilt.segments.store.path(parent['chunks'][0])
            path.symlink_to(path.with_name('never-created-native-part'))
            with self.assertRaises(NativeUIError):self.owner()
            self.assertEqual(calls,self.calls)


def load_tests(loader,tests,pattern):
    return unittest.TestSuite(AvatarPostLogoutOperationCacheTests(name) for name in loader.getTestCaseNames(AvatarPostLogoutOperationCacheTests)
        if name.startswith('test_operation_'))


if __name__=='__main__':unittest.main()
