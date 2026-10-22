"""One host API budget across nested Avatar calls and final transport guards.

This clock limits work only. It supplies no product/native capture timestamp,
frame provenance, observed success or ownership retirement.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
import math
import time
from adapters.normal_ui import NativeUIError
from adapters.operation_transport_guard import scope as transport_scope

SECONDS=25
_CURRENT=ContextVar('overte_avatar_api_budget',default=None)


class Budget:
    def __init__(self,monotonic):
        self.monotonic=monotonic;self.last=None;self.deadline=None;self.failed=False;self.original_caches={}
        self.deadline=self.check()+SECONDS
    def check(self):
        value=self.monotonic()
        if (self.failed or type(value) not in (int,float) or not math.isfinite(value) or value<0
                or self.last is not None and value<self.last
                or self.deadline is not None and value>=self.deadline):
            self.failed=True
            raise NativeUIError('Avatar API budget exhausted or host clock changed')
        self.last=value;return value


def check():
    current=_CURRENT.get()
    if current is not None:current.check()


def original_cache(kind):
    """Share only guarded original-byte decoders within this existing API call."""
    from adapters.native_feature_observation import need
    need(type(kind) is str and kind in ('postlogout-account','postlogout-parts'))
    current=_CURRENT.get()
    if current is None:return None
    current.check()
    if kind not in current.original_caches:
        from ios.adapters.avatar_record_cache import AvatarRecordCache
        current.original_caches[kind]=AvatarRecordCache()
    return current.original_caches[kind]


@contextmanager
def scope(monotonic):
    old=_CURRENT.get();budget=old if old is not None else Budget(monotonic)
    token=_CURRENT.set(budget)
    try:
        with transport_scope(budget.check):
            budget.check();yield;budget.check()
    finally:_CURRENT.reset(token)


def operation(function):
    @wraps(function)
    def bounded(self,*args,**kwargs):
        with scope(self.monotonic):return function(self,*args,**kwargs)
    return bounded


def guarded(function):
    @wraps(function)
    def bounded(*args,**kwargs):
        check();value=function(*args,**kwargs);check();return value
    return bounded


def installed_entry(function,*,monotonic=time.monotonic):
    """Include candidate preflight and final binding checks in the same call."""
    @wraps(function)
    def bounded(self,selector,operation,values):
        if type(operation) is str and operation.startswith('feature.avatar-people.'):
            with scope(monotonic):return function(self,selector,operation,values)
        return function(self,selector,operation,values)
    return bounded
