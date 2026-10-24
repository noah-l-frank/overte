"""Real filesystem mutations must not borrow an earlier original inventory."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
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


class OriginalLeaseMutationTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.root=Path(temp.name);self.root.chmod(0o700)
        self.folder=self.root/'nested';self.folder.mkdir(mode=0o700)
        self.original=self.folder/'original.json';self.original.write_bytes(b'original');self.original.chmod(0o600)

    def test_rewritten_bytes_with_restored_mtime_still_invalidate_the_original(self):
        lease=EmoteOriginalLease(self.root,[]);before=self.original.stat()
        self.original.write_bytes(b'changed!')
        os.utime(self.original,ns=(before.st_atime_ns,before.st_mtime_ns))
        with self.assertRaises(NativeUIError):lease.guard()

    def test_namespace_changes_and_replacement_are_not_hidden_by_directory_timestamp_policy(self):
        for fault in ('added','removed','replacement','mode'):
            with self.subTest(fault=fault):
                lease=EmoteOriginalLease(self.root,[])
                if fault=='added':
                    added=self.folder/'unaccounted';added.mkdir()
                elif fault=='removed':self.original.rename(self.root/'moved')
                elif fault=='replacement':
                    replacement=self.folder/'replacement';replacement.write_bytes(self.original.read_bytes())
                    replacement.chmod(0o600);replacement.replace(self.original)
                else:self.original.chmod(0o400)
                with self.assertRaises(NativeUIError):lease.guard()
                if fault=='added':added.rmdir()
                elif fault=='removed':(self.root/'moved').rename(self.original)
                elif fault=='mode':self.original.chmod(0o600)

    def test_symlinks_and_multiply_linked_originals_are_rejected(self):
        alias=self.root/'alias';alias.symlink_to(self.original)
        with self.assertRaises(NativeUIError):EmoteOriginalLease(self.root,[])
        alias.unlink();os.link(self.original,alias)
        with self.assertRaises(NativeUIError):EmoteOriginalLease(self.root,[])

    def test_only_the_exact_declared_mutable_file_may_disappear(self):
        metadata=self.root/'metadata.json';metadata.write_bytes(b'owned metadata')
        lease=EmoteOriginalLease(self.root,[metadata]);metadata.unlink();lease.guard()
        self.assertEqual({'.','nested','nested/original.json'},set(lease.rows))
        unexpected=self.root/'other.json';unexpected.write_bytes(b'unowned')
        with self.assertRaises(NativeUIError):lease.guard()

    def test_in_census_mutation_uses_a_second_uncached_stat(self):
        real=os.lstat;calls=[]
        def mutate(path,*args,**kwargs):
            value=real(path,*args,**kwargs)
            if os.fspath(path)==os.fspath(self.original):
                calls.append(path)
                if len(calls)==1:self.original.write_bytes(b'mutated during actual census')
            return value
        with patch.object(os,'lstat',side_effect=mutate),self.assertRaises(NativeUIError):
            EmoteOriginalLease(self.root,[])
        self.assertEqual(2,len(calls))


if __name__=='__main__':unittest.main()
