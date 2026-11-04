"""Original Lifecycle pair close proof; a reused numeric FD is foreign.

Host-only: no file adoption, source verdict, input or product cleanup.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import os
from types import FunctionType,MethodType
from adapters.native_fd_owner import OriginalDescriptor
from adapters.native_feature_observation import need

_CLASS=OriginalDescriptor
_RAW=type.__getattribute__(_CLASS,'__dict__')
_CLOSE=_RAW['close'];_REQUIRE=_RAW['require']
need(type(_CLOSE) is FunctionType and type(_REQUIRE) is FunctionType)
IMPLEMENTATION=(_CLOSE,_CLOSE.__code__,_REQUIRE,_REQUIRE.__code__,os.close,
    type.__getattribute__(_CLASS,'__mro__'))
_ORIGINAL_IMPLEMENTATION=IMPLEMENTATION


def pin():
    need(IMPLEMENTATION is _ORIGINAL_IMPLEMENTATION)
    return IMPLEMENTATION


def guard(owner,proof):
    need(proof is IMPLEMENTATION is _ORIGINAL_IMPLEMENTATION and OriginalDescriptor is _CLASS
        and type(owner) is _CLASS and type.__getattribute__(_CLASS,'__mro__') is proof[5])
    raw=type.__getattribute__(_CLASS,'__dict__')
    close=raw.get('close');require=raw.get('require')
    # Raw class entries are inspected BEFORE descriptor binding/attribute
    # access. An injected descriptor/getter can never manufacture a method.
    need(type(close) is type(require) is FunctionType and close is proof[0] and require is proof[2]
        and close.__code__ is proof[1] and require.__code__ is proof[3]
        and '__getattribute__' not in raw and '__getattr__' not in raw
        and all(name not in raw for name in ('closed','lost','fd','anchor','node'))
        and os.close is proof[4])
    bound_close=object.__getattribute__(owner,'close')
    bound_require=object.__getattribute__(owner,'require')
    need(type(bound_close) is MethodType and type(bound_require) is MethodType)
    need(bound_close.__self__ is owner and bound_close.__func__ is close
        and bound_require.__self__ is owner and bound_require.__func__ is require)


def close_original(owner,proof):
    guard(owner,proof)
    need(owner.closed is False and owner.lost is False
        and type(owner.fd) is type(owner.anchor) is int and owner.fd>=0 and owner.anchor>=0
        and owner.fd!=owner.anchor and type(owner.node) is tuple and len(owner.node)==2
        and all(type(value) is int for value in owner.node))
    # The original live pair is validated through the original implementation,
    # including the actual current kernel alias relation. No dynamic require or
    # an already-closed fast path can substitute a terminal observation.
    proof[2](owner,owner.fd);descriptor,anchor,node=owner.fd,owner.anchor,owner.node
    need(proof[0](owner) is True)
    guard(owner,proof)
    need(owner.closed is True and owner.lost is False
        and type(owner.fd) is type(owner.anchor) is int and owner.fd==owner.anchor==-1)
    # Both successful close syscalls happened in the exact pinned code above.
    # Another thread can immediately reuse either integer. Do not inspect,
    # close, adopt or claim absence for a later foreign numeric descriptor.
    return owner,descriptor,anchor,node
