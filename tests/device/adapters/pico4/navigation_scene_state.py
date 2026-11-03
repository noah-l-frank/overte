"""Host-only ownership fence for the original Navigation scene preparation."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import hashlib
import os
from pathlib import Path
import stat

from adapters.native_feature_observation import need

NAMES=('navigation-scene-owner.json','navigation-scene-raw.json','normal-scene-setup.json')


def retained(adapter,target):
    """No Native/source/Input/BaseStop query, adoption or deletion.

    Rootless original chunks, raw ranges/indexes and pending namespaces retain
    their responsibility. This WIP has no qualified final retirement route;
    a retained family always blocks generic cleanup, even a claimed done flag.
    """
    configuration=adapter.pico_configuration
    if configuration is None:return False
    key=hashlib.sha256(('org.overte.pico\0'+target).encode()).hexdigest()[:32]
    directory=Path(configuration[1])/('feature-scripts-'+key)
    try:info=directory.lstat()
    except FileNotFoundError:return False
    need(stat.S_ISDIR(info.st_mode) and info.st_uid==os.getuid() and stat.S_IMODE(info.st_mode)==0o700
        and directory.resolve(strict=True)==directory)
    with os.scandir(directory) as entries:
        for index,entry in enumerate(entries):
            need(index<4096)
            if entry.name in NAMES or any(entry.name.startswith(name+'.') for name in NAMES):return True
    return False
