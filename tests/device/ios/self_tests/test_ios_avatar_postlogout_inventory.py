"""Deduplicated ancestry work remains local to one actual file inventory."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.adapters.avatar_postlogout_incremental import AvatarPendingRound


class AvatarPostLogoutInventoryTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name);self.root.chmod(0o700);self.paths=set()
        for number in range(3):
            store=PrivateFeatureState(self.root/('actual-original-'+str(number)+'.json'));store.write(dict(actual=number),None)
            self.paths.add(store.path)

    def test_full_actual_file_signatures_are_still_checked_after_one_inventory(self):
        before=AvatarPendingRound.sign(self.paths);path=next(iter(self.paths));data=path.read_bytes();path.write_bytes(data)
        after=AvatarPendingRound.sign(self.paths);self.assertEqual(before[path][1],after[path][1]);self.assertNotEqual(before[path],after[path])

    def test_parent_mode_change_during_file_inventory_is_rejected(self):
        original=Path.lstat;changed=[]
        def actual(path,*args,**kwargs):
            value=original(path,*args,**kwargs)
            if path in self.paths and not changed:self.root.chmod(0o755);changed.append(True)
            return value
        try:
            with patch.object(Path,'lstat',actual),self.assertRaises(NativeUIError):AvatarPendingRound.sign(self.paths)
        finally:self.root.chmod(0o700)
        self.assertEqual([True],changed)

    def test_parent_replaced_by_symlink_during_file_inventory_is_rejected(self):
        original=Path.lstat;changed=[];moved=self.root.with_name(self.root.name+'-actual-moved')
        def actual(path,*args,**kwargs):
            value=original(path,*args,**kwargs)
            if path in self.paths and not changed:
                self.root.rename(moved);self.root.symlink_to(moved,target_is_directory=True);changed.append(True)
            return value
        try:
            with patch.object(Path,'lstat',actual),self.assertRaises(NativeUIError):AvatarPendingRound.sign(self.paths)
        finally:
            if self.root.is_symlink():self.root.unlink()
            if moved.exists():moved.rename(self.root)
        self.assertEqual([True],changed)


if __name__=='__main__':unittest.main()
