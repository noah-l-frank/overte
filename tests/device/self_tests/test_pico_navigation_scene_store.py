"""Actual original directory moves/aliases/recycling; no device or service."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import fcntl
import os
from pathlib import Path
import sys
import tempfile
import unittest

from adapters.native_fd_owner import OriginalDescriptor,QUERY
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.observer_return import raw_file
from adapters.pico4.navigation_scene_store import NavigationSceneRootState


class NavigationSceneStoreTests(unittest.TestCase):
    def setUp(self):
        self.root=Path(tempfile.mkdtemp(prefix='pico-navigation-original-directory-'));self.root.chmod(0o700)
        self.ancestor=self.root/'ancestor';self.ancestor.mkdir(mode=0o700)
        self.parent=self.ancestor/'live';self.parent.mkdir(mode=0o700)
        path=self.parent/'owner.json';PrivateFeatureState(path)._parent()
        self.directory=OriginalDescriptor(self.parent,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)
        self.addCleanup(self.directory.close)
        self.store=NavigationSceneRootState(path,self.directory);self.store.write(dict(original='unchanged'),None)
        self.raw,self.physical=raw_file(self.store)
        print('Retained original Navigation directory fixture:',self.root,file=sys.stderr)
    def refused(self):
        with self.assertRaises(NativeUIError):raw_file(self.store)
        self.assertTrue(self.store.failed)
        with self.assertRaises(NativeUIError):self.store.read()
    def test_same_original_root_bytes_ofd_and_stamp_are_read_on_every_pass(self):
        self.assertIsInstance(self.store,PrivateFeatureState)
        for _index in range(3):self.assertEqual((self.raw,self.physical),raw_file(self.store))
        self.assertEqual(dict(original='unchanged'),self.store.read())
    def test_actual_ancestor_move_with_same_node_symlink_alias_is_sticky_refused(self):
        moved=self.root/'moved';self.ancestor.rename(moved);self.ancestor.symlink_to(moved,target_is_directory=True)
        self.refused();self.assertEqual(self.raw,(moved/'live'/'owner.json').read_bytes())
    def test_actual_ancestor_exchange_preserves_original_and_refuses_named_replacement(self):
        moved=self.root/'held-ancestor';self.ancestor.rename(moved)
        self.ancestor.mkdir(mode=0o700);self.parent.mkdir(mode=0o700)
        self.store.path.write_bytes(self.raw);self.store.path.chmod(0o600)
        self.refused();self.assertEqual(self.raw,(moved/'live'/'owner.json').read_bytes())
    def test_equal_byte_directory_swap_does_not_adopt_new_directory_or_file(self):
        moved=self.ancestor/'original-live';self.parent.rename(moved);self.parent.mkdir(mode=0o700)
        self.store.path.write_bytes(self.raw);self.store.path.chmod(0o600)
        self.refused();self.assertEqual(self.raw,(moved/'owner.json').read_bytes())
    def test_actual_same_inode_recycled_directory_fd_retains_both_original_halves(self):
        foreign=OriginalDescriptor(self.parent,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)
        self.foreign=foreign;descriptor=self.directory.fd;anchor=self.directory.anchor
        os.dup2(foreign.fd,descriptor,inheritable=False);self.refused()
        self.assertFalse(self.directory.close());foreign.require(foreign.fd)
        self.assertEqual(1,fcntl.fcntl(descriptor,QUERY,foreign.anchor))
        self.assertEqual(os.fstat(anchor).st_ino,self.parent.stat().st_ino)
        # Uncertain original anchor and recycled foreign FD remain retained
        # until this actual test host finalizes; no force-close or adoption.
    def test_replaced_held_directory_object_is_refused_without_closing_foreign_owner(self):
        foreign=OriginalDescriptor(self.parent,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)
        self.foreign=foreign;self.store.directory=foreign;self.refused();foreign.require(foreign.fd)


if __name__=='__main__':unittest.main()
