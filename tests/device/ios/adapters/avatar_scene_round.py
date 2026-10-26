"""One pure held-Scene validation round over unchanged actual originals.

Only literal input/None-returning validator successes may be reused. Every
frame is independently read, hashed and parsed; no packet, clock, freshness,
effect, resource lifetime or derived Scene result enters this scope's cache.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from pathlib import Path
from adapters.native_clock_join import digest
from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.pure_original_validation import scope as pure_scope,AVATAR_PROFILE as PROFILE
from ios.adapters.emote_original_lease import EmoteOriginalLease

@contextmanager
def scope(scene):
    from ios.adapters.avatar_held_scene import IOSAvatarHeldScene
    need(type(scene) is IOSAvatarHeldScene);scene.lock.assert_held()
    original=digest(scene.envelope(scene.state));lock=scene.lock;path=scene.store.path;root=scene.root
    selected=[]
    for directory in sorted({Path(root),path.parent,lock.path.parent},key=lambda value:(len(value.parts),str(value))):
        PrivateFeatureState(directory/'avatar-scene-round-boundary')._parent()
        if not any(directory.is_relative_to(parent) for parent in selected):selected.append(directory)
    leases=[EmoteOriginalLease(directory,[]) for directory in selected]
    def unchanged():
        need(scene.lock is lock and scene.store.path==path and scene.root==root and type(scene) is IOSAvatarHeldScene)
        lock.assert_held();need(digest(scene.envelope(scene.state))==original)
        for lease in leases:lease.guard()
        return True
    with pure_scope(PROFILE,unchanged):yield
