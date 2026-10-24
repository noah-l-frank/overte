"""A pure original read round preserves actual bytes and current typed headers."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import os
import unittest
from adapters.normal_ui import NativeUIError
from ios.adapters.world_web_identity import WorldWebLease
from ios.self_tests.world_web_whole_fixture import ComposedWorldWeb


class WorldWebIdentityRoundTests(unittest.TestCase):
    def test_actual_inode_content_change_even_restored_bytes_and_mtime_rejects_round_then_fresh_full_read_succeeds(self):
        whole=ComposedWorldWeb();self.addCleanup(whole.close);source,scope=whole.source,whole.scope
        before=source.capture('before-owned-load');scope.prepare();scope.admit_rendered();after=source.capture('after-owned-load');lease=WorldWebLease(scope,source,before,after)
        path=next(scope.root.glob('world-web-frame-inputs-*.json'));raw=path.read_bytes();initial=path.stat()
        with self.assertRaises(NativeUIError):
            with source.validation_round(),lease.validation_round():
                packet=lease.packet();packet['admission']['marker']['id']='forged-returned-id'
                self.assertNotEqual(packet,lease.packet())
                path.write_bytes(raw+b' ');path.write_bytes(raw);os.utime(path,ns=(initial.st_atime_ns,initial.st_mtime_ns))
        self.assertIsNone(lease._round);self.assertEqual(lease.packet()['returned']['returned']['entityId'],whole.domain.marker['id'])
        binding=deepcopy(source.binding)
        with self.assertRaises(NativeUIError):
            with source.validation_round(),lease.validation_round():
                source.binding['targetFingerprint']='foreign-candidate';lease.packet()
        source.binding=binding


if __name__=='__main__':unittest.main()
