"""Pure host retention for explicit Lifecycle Background3 storage.

An orphan raw root/part/index/pending name retains responsibility. This module
does not acquire a product source, adopt a writer or retire any target object.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import hashlib
import os
from pathlib import Path
import stat

from adapters.native_feature_observation import need

NAME='lifecycle-background-raw.json'
UNRESOLVED=[]


def retained_path(directory):
    need(isinstance(directory,Path))
    if any(root==directory for root,_owner in UNRESOLVED):return True
    try:info=directory.lstat()
    except FileNotFoundError:return False
    need(stat.S_ISDIR(info.st_mode) and info.st_uid==os.geteuid()
        and stat.S_IMODE(info.st_mode)==0o700 and directory.resolve(strict=True)==directory)
    with os.scandir(directory) as entries:
        for index,entry in enumerate(entries):
            need(index<4096)
            if entry.name==NAME or entry.name.startswith(NAME+'.'):return True
    return False


def retained(adapter,target):
    configuration=adapter.pico_configuration
    if configuration is None:return False
    key=hashlib.sha256(('org.overte.pico\0'+target).encode()).hexdigest()[:32]
    return retained_path(Path(configuration[1])/('feature-scripts-'+key))


def close_or_retain(directory,*owners):
    """Constructor-error cleanup; preserve every uncertain original owner.

    Callers rethrow their original construction failure. A false/failed close
    cannot discard its remaining ownership or authorize a foreign FD close.
    """
    need(isinstance(directory,Path))
    complete=True
    for owner in owners:
        if owner is None:continue
        try:
            close=owner.close_host if callable(getattr(owner,'close_host',None)) else owner.close
            closed=close() is True
        except BaseException:closed=False
        if not closed:
            complete=False
            if not any(item is owner for _root,item in UNRESOLVED):UNRESOLVED.append((directory,owner))
    return complete
