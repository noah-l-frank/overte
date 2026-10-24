"""One twenty-second host budget across a narrow Assets owner call.

This host clock limits work only and supplies no product/native timestamp.
The full feature runtime and candidate entry point remain unimplemented.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
import math
from adapters.normal_ui import NativeUIError
from adapters.operation_transport_guard import scope as transport_scope

SECONDS=20
_CURRENT=ContextVar('overte_assets_budget',default=None)


class Budget:
    def __init__(self,monotonic):
        self.monotonic=monotonic;self.last=self.deadline=None;self.failed=False
        self.deadline=self.check()+SECONDS

    def check(self):
        value=self.monotonic()
        if (self.failed or type(value) not in (int,float) or not math.isfinite(value) or value<0
                or self.last is not None and value<self.last or self.deadline is not None and value>=self.deadline):
            self.failed=True;raise NativeUIError('Assets owner budget exhausted or host clock changed')
        self.last=value;return value


def check():
    budget=_CURRENT.get()
    if budget is not None:budget.check()


@contextmanager
def scope(monotonic):
    old=_CURRENT.get();budget=old if old is not None else Budget(monotonic);token=_CURRENT.set(budget)
    try:
        with transport_scope(budget.check):
            budget.check();yield;budget.check()
    finally:_CURRENT.reset(token)


def operation(function):
    @wraps(function)
    def bounded(self,*args,**kwargs):
        native=getattr(self,'native',self)
        monotonic=getattr(self,'monotonic',getattr(native,'monotonic',None))
        if monotonic is None:raise NativeUIError('Assets owner lacks its host budget clock')
        with scope(monotonic):return function(self,*args,**kwargs)
    return bounded
