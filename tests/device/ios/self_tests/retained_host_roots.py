"""Retain an explicitly owned test root even during interpreter unwinding.

This controls only host fixture lifetime. It supplies no native, SDK, product
or original-evidence fact, and changes no production ownership/cleanup path.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import os
from pathlib import Path
import stat
import tempfile


def retain_owned_root(directory,*,expected_root):
    if not isinstance(directory,tempfile.TemporaryDirectory):
        raise ValueError('Only an explicitly owned TemporaryDirectory can be retained')
    root=Path(directory.name);expected=Path(expected_root)
    if not root.is_absolute() or root!=expected or root.resolve()!=root:
        raise ValueError('The exact original host root is required')
    info=root.lstat();identity=(info.st_dev,info.st_ino)
    if not stat.S_ISDIR(info.st_mode) or stat.S_IMODE(info.st_mode)!=0o700 or info.st_uid!=os.getuid():
        raise ValueError('The original host root must remain private and locally owned')
    marked=getattr(directory,'_overte_retained_identity',None)
    if marked is not None:
        if marked!=(root,identity) or directory._finalizer.alive:
            raise ValueError('The retained original host root changed')
        return root
    original=directory._finalizer.peek()
    if original is None or not original[2] or Path(original[2][0])!=root:
        raise ValueError('The original temporary-root finalizer must still match')
    if directory._finalizer.detach() is None:
        raise ValueError('The owned temporary-root finalizer was already lost')

    def preserve():
        current=root.lstat()
        if ((current.st_dev,current.st_ino)!=identity or not stat.S_ISDIR(current.st_mode)
                or stat.S_IMODE(current.st_mode)!=0o700 or current.st_uid!=os.getuid()):
            raise ValueError('The retained original host root changed')
    directory.cleanup=preserve
    directory._overte_retained_identity=(root,identity)
    return root
