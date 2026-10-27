"""Round-local immutable Scope DTO decoding; no lease or quiet verdict cache."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
from types import SimpleNamespace,FunctionType,MethodType
from adapters.original_marker_scope import OriginalMarkerScope
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
            for _dto,pins,_membership,_parsers in entries.values():guard(pins)
        finally:_ROUND.reset(token)


def guard(pins):
    for path,signature in pins.items():need(EmoteOriginalLease.signature(path.lstat())==signature)



def _parser_epoch():
    # The actual classmethod/super/decode/frame-dispatch chain for this closed
    # Scope type. Unknown callable/default shapes keep the literal archive.
    rows=[]
    for method in (IOSWorldWebScope.archive,OriginalMarkerScope.archive,
            IOSWorldWebScope.decode,OriginalMarkerScope.decode,IOSWorldWebScope.validate_frame):
        function=method.__func__ if type(method) is MethodType else method
        if type(function) is not FunctionType:return None
        closure=function.__closure__
        if closure is not None:
            # The literal World subclass uses zero-argument super(). Its one
            # __class__ cell is required; arbitrary callback closures are not.
            if function.__code__.co_freevars!=('__class__',) or len(closure)!=1:return None
            try:owner=closure[0].cell_contents
            except ValueError:return None
            if owner is not IOSWorldWebScope and owner is not OriginalMarkerScope:return None
            closure=(id(closure[0]),closure[0],owner)
        defaults=function.__defaults__;keywords=function.__kwdefaults__
        if defaults is not None and (type(defaults) is not tuple or any(
                value is not None and type(value) is not bool for value in defaults)):return None
        if keywords is not None and (type(keywords) is not dict or any(
                type(key) is not str or value is not None and type(value) is not bool
                for key,value in keywords.items())):return None
        # Retain both strong code/function references. Code identity, including
        # in-place replacement on the same function, is distinct from equality.
        rows.append((function,id(function.__code__),function.__code__,defaults,
            None if keywords is None else tuple(sorted(keywords.items())),closure))
    return tuple(rows)


def archived(scope,source):
    need(type(scope) is IOSWorldWebScope and scope.PROFILE=='worldweb' and scope.lock is source.lock)
    source.lock.assert_held();need(same(scope.store.read(),scope.previous))
    header=[str(scope.root),str(scope.store.path),scope.binding,scope.run,scope.role,
        source.binding,source.run,source.role,source.pid,source.phase.fixture_url,
        None if not hasattr(source,'native') else source.native.instance]
    key=digest([header,scope.previous]);entries=_ROUND.get();parsers=_parser_epoch()
    memo=entries is not None and parsers is not None
    if memo and key in entries and entries[key][2].matches() and entries[key][3]==parsers:
        dto,pins,_membership,_parsers=entries[key]
        guard(pins);result=deepcopy(dto);guard(pins);need(same(scope.store.read(),scope.previous))
        if _parser_epoch()==parsers:return result
    continuity=EmoteOriginalLease(scope.root,[]);own=EmoteOriginalLease.signature(scope.store.path.lstat())
    def decode():
        original=IOSWorldWebScope.archive(scope.previous,root=scope.root,binding=source.binding,run=source.run,role='primary',lock=source.lock)
        return SimpleNamespace(state=deepcopy(original.state),frames=deepcopy(original.frames))
    parsers=_parser_epoch();memo=entries is not None and parsers is not None
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
        if _parser_epoch()==parsers:
            # A fresh read census must not retire the previous immutable
            # operands merely by replacing this same entry with new pins.
            if key in entries:guard(entries[key][1])
            need(key in entries or len(entries)<64);entries[key]=(deepcopy(dto),pins,OriginalMembership(),parsers)
    return dto
