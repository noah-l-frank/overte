"""Actual inode/inventory changes cannot reuse a prior byte decoder verdict."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import os
from pathlib import Path
import tempfile
import unittest
from adapters.normal_ui import NativeUIError
from ios.adapters.emote_original_lease import EmoteOriginalLease


class OriginalLeaseTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory();self.addCleanup(self.temporary.cleanup)
        self.root=Path(self.temporary.name);self.root.chmod(0o700)
        self.original=self.root/'original.json';self.original.write_bytes(b'{"actual":true}');self.original.chmod(0o600)
        self.owned=self.root/'owned.json';self.owned.write_bytes(b'{"pending":true}');self.owned.chmod(0o600)
    def lease(self):return EmoteOriginalLease(self.root,[self.owned])
    def test_exact_owned_metadata_update_and_removal_do_not_rewrite_immutable_original_inventory(self):
        lease=self.lease();self.owned.write_bytes(b'{"pending":false}');lease.guard()
        self.owned.unlink();lease.guard();self.assertEqual(b'{"actual":true}',self.original.read_bytes())
    def test_same_bytes_rewrite_even_with_original_mtime_restored_is_refused(self):
        lease=self.lease();before=self.original.stat();raw=self.original.read_bytes()
        self.original.write_bytes(raw);os.utime(self.original,ns=(before.st_atime_ns,before.st_mtime_ns))
        with self.assertRaises(NativeUIError):lease.guard()
    def test_foreign_inventory_change_and_same_name_new_inode_are_refused(self):
        lease=self.lease();extra=self.root/'foreign';extra.mkdir()
        with self.assertRaises(NativeUIError):lease.guard()
        extra.rmdir();lease.guard();old=self.root/'removed-original';self.original.rename(old)
        self.original.write_bytes(old.read_bytes());self.original.chmod(0o600);old.unlink()
        with self.assertRaises(NativeUIError):lease.guard()
    def test_symlink_hardlink_mode_and_root_exemption_are_refused(self):
        with self.assertRaises(NativeUIError):EmoteOriginalLease(self.root,[self.root])
        lease=self.lease();self.original.chmod(0o640)
        with self.assertRaises(NativeUIError):lease.guard()
        self.original.chmod(0o600);alias=self.root/'alias';alias.symlink_to(self.original)
        with self.assertRaises(NativeUIError):self.lease()
        alias.unlink();os.link(self.original,alias)
        with self.assertRaises(NativeUIError):self.lease()
