"""Round-local immutable Scope DTO decoding; no lease or quiet verdict cache."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
from types import SimpleNamespace
from adapters.native_clock_join import digest
from adapters.native_feature_observation import need
from adapters.original_file_reads import active,scope as read_scope
from adapters.script_feature.history import same
from ios.adapters.emote_original_lease import EmoteOriginalLease
from ios.adapters.world_web_scope import IOSWorldWebScope
from ios.adapters.world_web_original_membership import OriginalMembership

_ROUND=ContextVar('world_web_original_scope_dtos',default=None)


@contextmanager
def original_round():
    if _ROUND.get() is not None:yield;return
    entries={};token=_ROUND.set(entries)
    try:yield
    finally:
        try:
            for _dto,pins,_membership in entries.values():guard(pins)
        finally:_ROUND.reset(token)


def guard(pins):
    for path,signature in pins.items():need(EmoteOriginalLease.signature(path.lstat())==signature)


def archived(scope,source):
    need(type(scope) is IOSWorldWebScope and scope.PROFILE=='worldweb' and scope.lock is source.lock)
    source.lock.assert_held();need(same(scope.store.read(),scope.previous))
    header=[str(scope.root),str(scope.store.path),scope.binding,scope.run,scope.role,
        source.binding,source.run,source.role,source.pid,source.phase.fixture_url,
        None if not hasattr(source,'native') else source.native.instance]
    key=digest([header,scope.previous]);entries=_ROUND.get();memo=entries is not None
    if memo and key in entries and entries[key][2].matches():
        dto,pins,_membership=entries[key];guard(pins);result=deepcopy(dto);guard(pins);need(same(scope.store.read(),scope.previous));return result
    continuity=EmoteOriginalLease(scope.root,[]);own=EmoteOriginalLease.signature(scope.store.path.lstat())
    def decode():
        original=IOSWorldWebScope.archive(scope.previous,root=scope.root,binding=source.binding,run=source.run,role='primary',lock=source.lock)
        return SimpleNamespace(state=deepcopy(original.state),frames=deepcopy(original.frames))
    if memo:
        # Pin exactly the Scope decoder's actual reads. An enclosing operation
        # can also have read mutable Source/publisher heads; those unrelated
        # files are not immutable Scope operands and must not enter its pins.
        with read_scope(fresh=True) as scope_reads:dto=decode()
        pins={path:EmoteOriginalLease.signature(path.lstat()) for path in scope_reads|{scope.store.path}}
    else:
        dto=decode();pins={scope.store.path:own}
    continuity.guard();need(EmoteOriginalLease.signature(scope.store.path.lstat())==own and same(scope.store.read(),scope.previous));guard(pins)
    if memo:
        if active():
            # These paths were really read by the completed typed decoder in
            # its child census. Preserve those reads in the current caller;
            # cache hits never invent/restore membership in a new census.
            with read_scope() as reads:reads.update(scope_reads)
        need(key in entries or len(entries)<64);entries[key]=(deepcopy(dto),pins,OriginalMembership())
    return dto
