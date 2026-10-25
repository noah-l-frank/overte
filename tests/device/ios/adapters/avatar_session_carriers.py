"""Conservative Avatar carrier admission for ordinary session teardown.

Names retain responsibility only. Successful immutable typed replay and actual
file-read membership are required to retire it; a filename is never a fact.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import os
from pathlib import Path
import stat
from adapters.native_feature_observation import need
from ios.adapters.emote_original_lease import EmoteOriginalLease

_AVATAR=('avatar-','ios-avatar-','phase-publication-avatar-people-','phase-retirement-avatar-people-')
_PREFIXES=_AVATAR+('graphics-world-frame-','vulkan-world-')


def configured_roots(config,*,target=None):
    if config is None or 'avatar-people' not in config['areas']:return set()
    from ios.adapters.avatar_configuration import settings
    chosen=settings(config['avatarPeople'],role='primary')
    if target==chosen['actorTarget']:return set()
    return {Path(chosen['artifactRoot'])}


def inventory(roots):
    need(type(roots) is set and 1<=len(roots)<=65);seen=set();found=set()
    def visit(path,depth):
        need(depth<=64 and len(seen)<50000)
        if path in seen:return
        seen.add(path);before=path.lstat()
        if stat.S_ISDIR(before.st_mode):
            need(before.st_uid==os.geteuid())
            with os.scandir(path) as entries:names=sorted(entry.name for entry in entries)
            for name in names:visit(path/name,depth+1)
        else:
            need(stat.S_ISREG(before.st_mode) and before.st_uid==os.geteuid() and before.st_nlink==1)
            if path.name.startswith(_PREFIXES):found.add(path)
        need(EmoteOriginalLease.signature(before)==EmoteOriginalLease.signature(path.lstat()))
    for root in sorted(roots):
        need(isinstance(root,Path) and root.is_absolute() and root.resolve()==root)
        if root.exists():visit(root,0)
    return found


def scoped(directory,roots,*,explicit=False):
    if not explicit:
        if not directory.exists():return set()
        with os.scandir(directory) as entries:names=[entry.name for entry in entries]
        need(len(names)<=50000)
        if not any(name.startswith(_AVATAR) for name in names):return set()
    candidates=inventory(roots)
    # Existing closed foreign GPU decoders recognize actual Graphics/Create
    # responsibility. Unknown or malformed GPU metadata is never excluded.
    from ios.adapters.emote_foreign_gpu import ignored
    return candidates-ignored(directory,candidates)


def covered(directory,roots,membership):
    need(type(membership) is set);need(scoped(directory,roots,explicit=True)<=membership)


def failure_report(value,flow):
    """Typed failed-worker reporting after separate full product retirement."""
    from adapters.native_feature_observation import exact
    from adapters.script_feature.history import same
    exact(value,{'iosAvatarWorkerFailureVersion','runId','fixtureUrl','target','primaryTarget','artifactRoot','imagePolicy'})
    need(flow.role=='actor' and type(value['iosAvatarWorkerFailureVersion']) is int and value['iosAvatarWorkerFailureVersion']==1
        and value['runId']==flow.run and value['fixtureUrl']==flow.phase.fixture_url and value['target']==flow.selectors['actor']
        and value['primaryTarget']==flow.selectors['primary'] and value['artifactRoot']==str(flow.root) and same(value['imagePolicy'],flow.policy))
    return True
