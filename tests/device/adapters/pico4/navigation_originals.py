"""Original generation-0 files, pinned before the explicit app restart.

Every verification reads the actual bytes and full physical identity. An equal
replacement inode, chmod/chown, link, rewrite or inventory change refuses.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import hashlib
import os
from pathlib import Path
import stat

from adapters.native_feature_observation import exact,integer,need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_journey.history import same
from adapters.world_render_evidence import LIMIT as PNG_LIMIT


FIELDS=('st_dev','st_ino','st_mode','st_uid','st_nlink','st_size','st_mtime_ns','st_ctime_ns')


def signature(info):return [getattr(info,key) for key in FIELDS]


def inventory(root,run,normal_ui_path):
    root=Path(root);normal_ui_path=Path(normal_ui_path)
    PrivateFeatureState(root/'navigation-original-boundary.json')._parent()
    need(normal_ui_path.is_absolute() and normal_ui_path.parent in (root,root.parent))
    files=[]
    for path in root.iterdir():
        name=path.name
        if name.startswith(('navigation-prefix-restart','navigation-prefix-generation-1-')):continue
        if not (name.startswith('navigation-prefix-') or name.startswith('navigation-'+run+'-environment-')):continue
        if name=='navigation-prefix-images':
            PrivateFeatureState(path/'boundary.json')._parent()
            files.extend(path.iterdir())
        else:files.append(path)
    need(root/'navigation-prefix-owner.json' in files and len({str(path) for path in files})==len(files))
    need(normal_ui_path not in files);files.append(normal_ui_path)
    return sorted(files,key=str)


def read_original(path):
    path=Path(path);PrivateFeatureState(path)._parent()
    try:before=path.lstat()
    except FileNotFoundError:return dict(path=str(path),present=False)
    limit=PNG_LIMIT if path.suffix=='.png' else 65536
    descriptor=os.open(path,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0)|getattr(os,'O_NONBLOCK',0))
    try:
        first=os.fstat(descriptor);current=path.lstat()
        need(signature(first)==signature(before)==signature(current) and stat.S_ISREG(first.st_mode)
            and first.st_nlink==1 and first.st_uid==os.geteuid() and stat.S_IMODE(first.st_mode)==0o600
            and integer(first.st_size,1,limit))
        digest=hashlib.sha256();count=0
        while True:
            raw=os.read(descriptor,min(65536,limit+1-count))
            if not raw:break
            digest.update(raw);count+=len(raw);need(count<=limit)
        need(count==first.st_size and signature(first)==signature(os.fstat(descriptor))==signature(path.lstat()))
        return dict(path=str(path),present=True,signature=signature(first),sha256=digest.hexdigest())
    finally:os.close(descriptor)


def capture(root,run,normal_ui_path,source_lock):
    source_lock.assert_held();need(source_lock.path==Path(root)/'script-sources.lock')
    paths=inventory(root,run,normal_ui_path);rows=[read_original(path) for path in paths]
    need(paths==inventory(root,run,normal_ui_path))
    for row in rows:need(same(read_original(row['path']),row))
    return rows


def verify(rows,root,run,normal_ui_path,source_lock):
    source_lock.assert_held();need(source_lock.path==Path(root)/'script-sources.lock' and type(rows) is list and rows)
    paths=inventory(root,run,normal_ui_path);need([str(path) for path in paths]==[row['path'] for row in rows])
    for row in rows:
        exact(row,{'path','present'}|({'signature','sha256'} if row.get('present') is True else set()))
        need(type(row['present']) is bool and same(read_original(row['path']),row))
    need(paths==inventory(root,run,normal_ui_path));return True
