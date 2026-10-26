"""Actual private-file continuity and membership, never a new product proof."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import os
import tempfile
import unittest
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.original_file_reads import scope
from ios.adapters.avatar_record_cache import AvatarRecordCache


class AvatarRecordCacheTests(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup);self.root=Path(t.name);self.root.chmod(0o700)
        self.file=PrivateFeatureState(self.root/'actual-original.json');self.file.write(dict(actual=[1,2]),None);self.cache=AvatarRecordCache();self.calls=[]
    def read(self):self.calls.append(True);return self.file.read()
    def test_reuse_requires_double_original_validation_and_preserves_exact_read_membership(self):
        with scope(fresh=True) as first:value=self.cache.read(dict(index=1),self.read)
        self.assertEqual(2,len(self.calls));self.assertEqual({self.file.path},first);value['actual'].append(9)
        with scope(fresh=True) as second:value=self.cache.read(dict(index=1),self.read)
        self.assertEqual(dict(actual=[1,2]),value);self.assertEqual(2,len(self.calls));self.assertEqual(first,second)
    def test_same_inode_same_length_overwrite_with_restored_mtime_refuses_cached_old_bytes(self):
        self.cache.read(dict(index=1),self.read);old=self.file.path.stat();raw=self.file.path.read_bytes()
        self.file.path.write_bytes(raw.replace(b'1,2',b'2,1'));os.utime(self.file.path,ns=(old.st_atime_ns,old.st_mtime_ns))
        self.assertEqual(old.st_ino,self.file.path.stat().st_ino)
        with self.assertRaises(NativeUIError):self.cache.read(dict(index=1),self.read)
        self.assertEqual(2,len(self.calls))
    def test_check_keeps_original_membership_and_mutation_refusal_without_exposing_cached_tree(self):
        with scope(fresh=True) as first:
            self.assertIsNone(self.cache.check(dict(index=1),self.read))
        self.assertEqual(2,len(self.calls))
        self.assertEqual({self.file.path},first)
        with scope(fresh=True) as second:
            self.assertIsNone(self.cache.check(dict(index=1),self.read))
        self.assertEqual(first,second)
        value=self.cache.read(dict(index=1),self.read);value['actual'].append(9)
        self.assertIsNone(self.cache.check(dict(index=1),self.read))
        self.assertEqual(dict(actual=[1,2]),self.cache.read(dict(index=1),self.read))
        raw=self.file.path.read_bytes();self.file.path.write_bytes(raw)
        with self.assertRaises(NativeUIError):self.cache.check(dict(index=1),self.read)
        self.assertEqual(2,len(self.calls))

    def test_check_keeps_planned_absence_and_both_independent_signature_boundaries(self):
        missing=self.root/'planned-original.json'
        self.cache.read(dict(index=1),self.read,absent=lambda:{missing})
        original=self.cache.signatures;calls=[]
        def race(paths):
            result=original(paths);calls.append(True)
            if len(calls)==1:self.file.path.write_bytes(self.file.path.read_bytes())
            return result
        with patch.object(self.cache,'signatures',side_effect=race),self.assertRaises(NativeUIError):
            self.cache.check(dict(index=1),self.read,absent=lambda:{missing})
        self.assertEqual(2,len(calls))
        cache=AvatarRecordCache();cache.check(dict(index=1),self.read,absent=lambda:{missing})
        missing.symlink_to('not-created')
        with self.assertRaises(NativeUIError):cache.check(dict(index=1),self.read,absent=lambda:{missing})
    def test_hardlink_and_change_between_discovery_and_validation_are_not_cached(self):
        self.cache.read(dict(index=1),self.read);os.link(self.file.path,self.root/'alias.json')
        with self.assertRaises(NativeUIError):self.cache.read(dict(index=1),self.read)
        (self.root/'alias.json').unlink();cache=AvatarRecordCache();calls=[]
        def racing():
            calls.append(True);value=self.file.read()
            if len(calls)==2:self.file.path.write_bytes(self.file.path.read_bytes())
            return value
        with self.assertRaises(NativeUIError):cache.read(dict(index=1),racing)
        self.assertEqual({},cache.rows)


    def test_planned_absence_is_separate_from_actual_read_membership_on_every_reuse(self):
        missing=self.root/'planned-actual-original.json'
        with scope(fresh=True) as actual:
            self.cache.read(dict(index=1),self.read,absent=lambda:{missing})
        self.assertEqual({self.file.path},actual);self.assertNotIn(missing,actual)
        os.symlink(self.root/'not-created',missing);self.assertFalse(missing.exists())
        with self.assertRaises(NativeUIError):self.cache.read(dict(index=1),self.read,absent=lambda:{missing})
        self.assertEqual(2,len(self.calls))

    def test_parent_privacy_cannot_change_between_byte_validation_and_cached_reuse(self):
        self.cache.read(dict(index=1),self.read);self.root.chmod(0o755)
        try:
            with self.assertRaises(NativeUIError):self.cache.read(dict(index=1),self.read)
        finally:self.root.chmod(0o700)

    def test_canonical_parent_and_regular_leaf_are_both_mandatory(self):
        folder=self.root/'private';folder.mkdir(mode=0o700)
        path=folder/'original.json';path.write_bytes(b'actual original');path.chmod(0o600)
        alias=self.root/'aliased-parent';alias.symlink_to(folder,target_is_directory=True)
        with self.assertRaises(NativeUIError):self.cache.signatures({alias/path.name})
        leaf=self.root/'aliased-leaf';leaf.symlink_to(path)
        with self.assertRaises(NativeUIError):self.cache.signatures({leaf})

    def test_parent_change_during_signature_collection_cannot_escape_the_exit_check(self):
        original=Path.lstat;changed=[]
        def racing(path,*args,**kwargs):
            value=original(path,*args,**kwargs)
            if path==self.file.path and not changed:
                changed.append(True);self.root.chmod(0o755);self.root.chmod(0o700)
            return value
        with patch.object(Path,'lstat',new=racing),self.assertRaises(NativeUIError):
            self.cache.signatures({self.file.path})
        self.assertEqual([True],changed)


if __name__=='__main__':unittest.main()
