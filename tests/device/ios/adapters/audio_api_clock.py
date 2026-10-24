"""A shared 25-second host work limit for the partial Audio owner APIs."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextvars import ContextVar
from functools import wraps
import math
from adapters.normal_ui import NativeUIError
from adapters.operation_transport_guard import scope

_CURRENT=ContextVar('overte_ios_audio_owner_budget',default=None)


class Budget:
    def __init__(self,monotonic):
        self.monotonic=monotonic;self.last=None;self.deadline=None;self.failed=False;self.deadline=self.check()+25
    def check(self):
        value=self.monotonic()
        if (self.failed or type(value) not in (int,float) or not math.isfinite(value) or value<0
                or self.last is not None and value<self.last or self.deadline is not None and value>=self.deadline):
            self.failed=True;raise NativeUIError('Audio owner API budget exhausted or host clock changed')
        self.last=value;return value


def operation(function):
    @wraps(function)
    def wrapped(self,*args,**kwargs):
        budget=_CURRENT.get()
        if budget is None:budget=Budget(self.monotonic)
        token=_CURRENT.set(budget)
        try:
            with scope(budget.check):
                budget.check();result=function(self,*args,**kwargs);budget.check();return result
        finally:_CURRENT.reset(token)
    return wrapped
