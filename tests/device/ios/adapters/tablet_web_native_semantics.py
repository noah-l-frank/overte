"""Bounded, context-local reuse of exact pure native-validator arguments.

No bytes, files, query ownership, clocks, freshness or source history are
skipped. Only successful deterministic native DTO validation is memoized;
every file read/descriptor check and every surrounding history rule still runs.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from collections import OrderedDict
from contextlib import contextmanager
from contextvars import ContextVar
from adapters.native_feature_observation import need
from adapters.script_feature.history import canonical

_ACTIVE=ContextVar('tablet_native_semantics',default=None)
MAX_BYTES=32*1024*1024
MAX_ITEMS=512


class TabletNativeSemantics:
    def __init__(self):self.entries=OrderedDict();self.bytes=0
    def checked(self,module,kind,value,query,pid,previous):
        need(kind in ('original','validate'))
        try:parts=(canonical(pid),canonical(value),canonical(query),canonical(previous))
        except (ValueError,TypeError,UnicodeError):
            # Invalid/unserializable inputs keep the original validator's
            # exact failure behavior, and can never mint a memo entry.
            return invoke(module,kind,value,query,pid,previous)
        key=(module,module.original,module.validate,kind,*parts);size=sum(map(len,parts))
        if key in self.entries:self.entries.move_to_end(key);return
        invoke(module,kind,value,query,pid,previous)
        if size>MAX_BYTES:return
        while self.entries and (self.bytes+size>MAX_BYTES or len(self.entries)>=MAX_ITEMS):
            _key,old=self.entries.popitem(last=False);self.bytes-=old
        self.entries[key]=size;self.bytes+=size


def invoke(module,kind,value,query,pid,previous):
    if kind=='original':module.original(value)
    else:module.validate(value,query,pid,previous=previous)


def checked(module,kind,value,query=None,pid=None,previous=None):
    need(kind in ('original','validate'))
    active=_ACTIVE.get()
    if active is None:return invoke(module,kind,value,query,pid,previous)
    active.checked(module,kind,value,query,pid,previous)


@contextmanager
def scope(memo):
    need(type(memo) is TabletNativeSemantics);token=_ACTIVE.set(memo)
    try:yield
    finally:_ACTIVE.reset(token)
