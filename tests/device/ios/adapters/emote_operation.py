"""Transient whole-call work deadlines; never a native observation clock."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
from adapters.native_feature_observation import need,number
from adapters.normal_ui import NativeUIError
from adapters.operation_transport_guard import scope as transport_scope

_ACTIVE=ContextVar('ios_emote_operation_guards',default=())


def clock(owner):
    now=owner.monotonic()
    if (getattr(owner,'_operation_failed',False) or not number(now,0,1e15) or owner.last_clock is not None and now<owner.last_clock
            or owner.deadline is not None and now>=owner.deadline):
        owner._operation_failed=True;raise NativeUIError('Emote operation deadline exhausted or host clock changed')
    owner.last_clock=now;return now


@contextmanager
def scope(runtime,guard):
    need(callable(guard));token=_ACTIVE.set(_ACTIVE.get()+((runtime,guard),))
    try:
        with transport_scope(guard):check(runtime);yield;check(runtime)
    finally:_ACTIVE.reset(token)


def active(runtime):return any(owner is runtime for owner,_guard in _ACTIVE.get())


def check(runtime):
    for owner,guard in _ACTIVE.get():
        if owner is runtime:need(guard() is not False)


def guarded(runtime,function):
    @wraps(function)
    def invoke(*args,**kwargs):
        check(runtime);result=function(*args,**kwargs);check(runtime);return result
    return invoke


class Client:
    def __init__(self,runtime,original):self.runtime,self.original=runtime,original
    def call(self,*args,**kwargs):return guarded(self.runtime,self.original.call)(*args,**kwargs)
    def __getattr__(self,name):return getattr(self.original,name)


def operation(seconds):
    def decorate(function):
        @wraps(function)
        def invoke(self,*args,**kwargs):
            outer=self.deadline;top=not getattr(self,'_operation_depth',0)
            if top:self._operation_failed=False
            now=self.clock();self.deadline=now+seconds if outer is None else min(outer,now+seconds)
            self._operation_depth=getattr(self,'_operation_depth',0)+1
            try:
                with self.runtime.operation_guard(self.clock):
                    self.clock();value=function(self,*args,**kwargs);self.clock();return value
            finally:self._operation_depth-=1;self.deadline=outer
        return invoke
    return decorate
