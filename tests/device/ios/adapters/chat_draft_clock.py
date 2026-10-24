"""One unchanged twenty-second Chat checkpoint budget through final sends."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextvars import ContextVar
from functools import wraps
import math
from adapters.normal_ui import NativeUIError
from adapters.operation_transport_guard import scope

_CURRENT=ContextVar('ios_chat_draft_budget',default=None)


class Budget:
    def __init__(self,monotonic):
        self.monotonic=monotonic;self.last=self.deadline=None;self.failed=False
        self.deadline=self.check()+20
    def check(self):
        value=self.monotonic()
        if (self.failed or type(value) not in (int,float) or not math.isfinite(value) or value<0
                or self.last is not None and value<self.last or self.deadline is not None and value>=self.deadline):
            self.failed=True;raise NativeUIError('Chat checkpoint budget exhausted or host clock changed')
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
