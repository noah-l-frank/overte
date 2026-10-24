"""One bounded Web API call through final native and W3C transport sends."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
import math
from adapters.normal_ui import NativeUIError
from adapters.operation_transport_guard import scope as transport_scope

SECONDS=25
_CURRENT=ContextVar('overte_world_web_api_budget',default=None)


class Budget:
    def __init__(self,monotonic):
        self.monotonic=monotonic;self.last=None;self.deadline=None;self.failed=False;self.deadline=self.check()+SECONDS
    def check(self):
        value=self.monotonic()
        if (self.failed or type(value) not in (int,float) or not math.isfinite(value) or value<0
            or self.last is not None and value<self.last or self.deadline is not None and value>=self.deadline):
            self.failed=True;raise NativeUIError('World Web API budget exhausted or host clock changed')
        self.last=value;return value


def check():
    budget=_CURRENT.get()
    if budget is not None:budget.check()


@contextmanager
def scope(monotonic):
    old=_CURRENT.get();budget=old if old is not None else Budget(monotonic);token=_CURRENT.set(budget)
    try:
        from ios.adapters import world_web_snapshot,world_web_whole_snapshot,world_web_source
        from ios.adapters.world_web_clock_validation import scope as clock_validation
        # These existing memos retain immutable original decoding only. Their
        # current file/context guards and every transport deadline still run.
        with clock_validation(),world_web_snapshot.validation_round(),world_web_whole_snapshot.validation_round(),world_web_source.validation_round(),transport_scope(budget.check):
            budget.check();yield;budget.check()
    finally:_CURRENT.reset(token)


def operation(function):
    @wraps(function)
    def wrapped(self,*args,**kwargs):
        with scope(self.monotonic):return function(self,*args,**kwargs)
    return wrapped


def guarded(function):
    @wraps(function)
    def wrapped(*args,**kwargs):
        check();value=function(*args,**kwargs);check();return value
    return wrapped


def installed_entry(function,*,monotonic=None):
    """Include actual candidate preflight before construction of the runtime."""
    import time
    monotonic=time.monotonic if monotonic is None else monotonic
    @wraps(function)
    def wrapped(adapter,selector,name,values):
        if not name.startswith('feature.world-web.'):return function(adapter,selector,name,values)
        with scope(monotonic):return function(adapter,selector,name,values)
    return wrapped
