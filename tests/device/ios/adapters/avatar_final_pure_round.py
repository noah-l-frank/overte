"""Pure Final2 validation successes inside one unchanged original read scope.

Every frame and component read and each quiet/effect calculation still runs.
Only existing literal input/None-returning validators share their successes;
no parser output, packet, current clock, I/O or live guard is cached here.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from pathlib import Path
from adapters.native_clock_join import digest
from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.pure_original_validation import inherited_scope as pure_scope,AVATAR_FINAL_PROFILE as PROFILE
from ios.adapters.emote_original_lease import EmoteOriginalLease


def identity(owner):
    return (type(owner),id(owner.authority),type(owner.authority),id(owner.authority.client),type(owner.authority.client),
        owner.authority.client.url,owner.authority.run,owner.historical,
        tuple((role,id(owner.locks[role]),str(owner.locks[role].path)) for role in ('primary','actor')),
        digest(dict(root=str(owner.root),store=str(owner.store.path),runId=owner.run,role=owner.role,
            bindings=owner.bindings,inputs=owner.inputs,previous=owner.previous)),
        hasattr(owner,'state'),digest(owner.state) if hasattr(owner,'state') else None)


@contextmanager
def scope(owner,value,*,guard=None):
    from ios.adapters.avatar_held_final import IOSAvatarHeldFinal
    need(type(owner) is IOSAvatarHeldFinal and type(value) is dict and (guard is None or callable(guard)))
    if guard is not None:need(guard() is not False)
    for lock in owner.locks.values():lock.assert_held()
    original=identity(owner);argument=digest(value);roots={Path(owner.root),owner.store.path.parent}
    for subject in ('primary','actor'):
        item=owner.input(subject);roots.add(Path(item['root']))
        roots.update(Path(path).parent for path in item['paths'].values())
    selected=[]
    for root in sorted(roots,key=lambda path:(len(path.parts),str(path))):
        PrivateFeatureState(root/'avatar-final-pure-round-boundary')._parent()
        if not any(root.is_relative_to(parent) for parent in selected):selected.append(root)
    leases=[EmoteOriginalLease(root,[]) for root in selected]
    def unchanged():
        if guard is not None:need(guard() is not False)
        need(type(owner) is IOSAvatarHeldFinal and identity(owner)==original and digest(value)==argument)
        for lock in owner.locks.values():lock.assert_held()
        for lease in leases:lease.guard()
        return True
    with pure_scope(PROFILE,unchanged):yield
