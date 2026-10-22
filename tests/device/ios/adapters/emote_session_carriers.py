"""Unknown Emote/ambiguous GPU carriers retain teardown responsibility.

Names are admission cues only. A full typed original decoder and unchanged
inventory lease must independently supply exact actual-read membership.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import os
from pathlib import Path
import stat
from adapters.native_feature_observation import need
from ios.adapters.emote_original_lease import EmoteOriginalLease

_EMOTE=('emote-','ios-emote-','phase-publication-emotes-','phase-retirement-emotes-')
_PREFIXES=_EMOTE+('graphics-world-frame-','vulkan-world-')


def inventory(roots):
    need(type(roots) is set and 1<=len(roots)<=65)
    found=set();seen=set()
    def visit(path,depth):
        need(depth<=64 and len(seen)<50000)
        if path in seen:return
        seen.add(path);before=path.lstat()
        if stat.S_ISDIR(before.st_mode):
            need(before.st_uid==os.geteuid())
            with os.scandir(path) as rows:names=sorted(row.name for row in rows)
            for name in names:visit(path/name,depth+1)
        else:
            need(stat.S_ISREG(before.st_mode) and before.st_nlink==1 and before.st_uid==os.geteuid())
            if path.name.startswith(_PREFIXES):found.add(path)
        need(EmoteOriginalLease.signature(before)==EmoteOriginalLease.signature(path.lstat()))
    for root in sorted(roots):
        need(isinstance(root,Path) and root.is_absolute() and root.resolve()==root)
        if root.exists():visit(root,0)
    return found


def covered(roots,actual_reads):
    need(type(actual_reads) in (set,frozenset));need(inventory(roots)<=actual_reads)


def configured_roots(config,*,target=None):
    if config is None or 'emotes' not in config['areas']:return set()
    if target==config['emotes']['actorTarget']:return set()
    # The current feature-configuration reader has already applied its exact
    # version/profile/policy grammar. This adds no fixture client or target.
    return {Path(config['emotes']['artifactRoot'])}


def failure_report(value,*,root,run,role,fixture_url,policy,target):
    """Recognize reporting metadata after separate full product retirement.

    A durable failed worker remains failed. This never qualifies a source,
    generic GPU owner, cleanup fact, input, or independent peer identity.
    """
    from adapters.native_feature_observation import exact
    from adapters.script_feature.history import same
    from ios.adapters.emote_configuration import selector
    exact(value,{'iosEmoteWorkerFailureVersion','runId','fixtureUrl','target','primaryTarget','artifactRoot','imagePolicy'})
    need(role=='actor' and type(value['iosEmoteWorkerFailureVersion']) is int and value['iosEmoteWorkerFailureVersion']==1
        and value['runId']==run and value['fixtureUrl']==fixture_url and value['target']==target
        and value['artifactRoot']==str(root) and same(value['imagePolicy'],policy))
    selector(value['target']);selector(value['primaryTarget']);need(value['target']!=value['primaryTarget'])
    return True


def scoped(directory,roots,*,explicit=False):
    # Generic namespaces alone cannot create Emote ownership on an unrelated
    # default SDK. Explicit Emote roots or actual Emote carriers are required.
    if not explicit:
        if not directory.exists():return set()
        with os.scandir(directory) as rows:names=[row.name for row in rows]
        need(len(names)<=50000)
        if not any(name.startswith(_EMOTE) for name in names):return set()
    values=inventory(roots)
    from ios.adapters.emote_foreign_gpu import ignored
    return values-ignored(directory,values)


def scoped_covered(directory,roots,actual_reads):
    need(scoped(directory,roots,explicit=True)<=actual_reads)
