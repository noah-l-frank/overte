"""Closed logical metadata views; immutable originals always keep real readers.

The frozen view supplies interpretation only. It does not claim a copied WAL
is physically present/read or authorize Stop/deletion. Actual current metadata
and a typed end CAS index are separately mandatory for those authorities.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
from adapters.native_clock_join import digest
from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_feature.history import same
from ios.adapters.emote_retirement import Frozen


def signature(path):
    try:value=Path(path).lstat()
    except FileNotFoundError:return None
    return tuple(getattr(value,key) for key in ('st_dev','st_ino','st_mode','st_nlink','st_uid','st_size','st_mtime_ns','st_ctime_ns'))


class RecordingAssetsMetadata:
    def __init__(self,*,owned=(),selection=None):
        self.copies={};self.pins={};self.used=set();self.owned={Path(path) for path in owned};self.selection=selection
    def store(self,path):
        view=self;path=Path(path)
        class ActualRead(PrivateFeatureState):
            def read(self):
                before=signature(path);value=super().read();need(signature(path)==before);key=str(path)
                if key in view.copies:need(same(view.copies[key],value) and view.pins[key]==before)
                else:view.copies[key]=deepcopy(value);view.pins[key]=before
                view.used.add(key);return value
            def write(self,*_args,**_kwargs):need(False)
            def discard(self,*_args,**_kwargs):need(False)
        return ActualRead(path)
    def guard(self):
        for path,value in self.copies.items():need(signature(path)==self.pins[path] and same(PrivateFeatureState(path).read(),value))
        return True


class FrozenAssetsMetadata:
    def __init__(self,copies,*,owned=(),selection=None):
        need(type(copies) is dict and 1<=len(copies)<=256)
        self.copies=deepcopy(copies);self.selection=selection;self.used=set();self.owned={Path(path) for path in owned}
        for name,value in self.copies.items():
            path=Path(name);need(type(name) is str and path.is_absolute() and path.resolve()==path
                and (value is None or type(value) is dict))
        need(not self.owned & {Path(path) for path in self.copies})
    def store(self,path):
        view=self;path=Path(path);key=str(path);need(key in self.copies)
        class LogicalCopy(Frozen):
            def read(self):view.used.add(key);return super().read()
        return LogicalCopy(path,self.copies[key])


def checked(view):need(view is None or type(view) in (RecordingAssetsMetadata,FrozenAssetsMetadata))

def store(path,view=None):
    checked(view);return PrivateFeatureState(path) if view is None else view.store(path)


def entries(directory,view=None):
    checked(view);directory=Path(directory);actual=list(directory.iterdir());need(len(actual)<=4096)
    if view is not None:
        actual=[path for path in actual if path not in view.owned]
    if type(view) is FrozenAssetsMetadata:
        # Only explicit copied mutable metadata receives a historical logical
        # path. Unknown originals/current files remain visible to the census.
        actual=sorted(set(actual)|{Path(path) for path,value in view.copies.items() if Path(path).parent==directory and value is not None},key=lambda p:p.name)
    return actual


def pin(path,view=None):
    checked(view);key=str(path)
    if type(view) is FrozenAssetsMetadata and key in view.copies:return ('logical-metadata-copy',digest(view.copies[key]))
    return signature(path)


def coverage(paths,reads,view=None):
    checked(view);paths=set(paths)
    if type(view) is FrozenAssetsMetadata:
        logical={Path(path) for path in view.copies};need({str(p) for p in paths&logical}<=view.used)
        paths-=logical
    need(paths<=reads);return True
