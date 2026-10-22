"""Original file inventory continuity after full byte-based proof validation.

No digest is inferred from metadata. The owning decoder verifies actual bytes
between the original inventory and its unchanged post-validation inventory.
Only explicitly listed CAS-owned runtime metadata may subsequently retire.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import os
from pathlib import Path
import stat
from adapters.native_feature_observation import need


class EmoteOriginalLease:
    def __init__(self,root,mutable):
        self.root=Path(root)
        need(self.root.is_absolute() and self.root.resolve(strict=True)==self.root
            and type(mutable) is list and len(mutable)<=2048)
        self.mutable={Path(path) for path in mutable}
        need(all(path.is_absolute() and path.resolve()==path and path!=self.root for path in self.mutable))
        self.rows=self.snapshot()

    @staticmethod
    def record(value):
        base=(value.st_dev,value.st_ino,value.st_mode,value.st_uid,value.st_gid)
        # Complete entry inventory detects directory changes. Its timestamps
        # legitimately change when the exact known metadata files retire.
        return base if stat.S_ISDIR(value.st_mode) else base+(value.st_nlink,value.st_size,value.st_mtime_ns,value.st_ctime_ns)

    @staticmethod
    def signature(value):
        return (value.st_dev,value.st_ino,value.st_mode,value.st_uid,value.st_gid,value.st_nlink,
            value.st_size,value.st_mtime_ns,value.st_ctime_ns)

    def snapshot(self):
        rows={}
        def visit(path,depth):
            need(depth<=64 and len(rows)<50000)
            if path in self.mutable:return
            before=path.lstat();directory=stat.S_ISDIR(before.st_mode)
            need(before.st_uid==os.geteuid() and (directory or stat.S_ISREG(before.st_mode) and before.st_nlink==1))
            key=str(path.relative_to(self.root));rows[key]=self.record(before)
            if directory:
                with os.scandir(path) as children:names=sorted(item.name for item in children)
                for name in names:visit(path/name,depth+1)
            need(self.signature(path.lstat())==self.signature(before))
        visit(self.root,0);return rows

    def guard(self):need(self.snapshot()==self.rows)
