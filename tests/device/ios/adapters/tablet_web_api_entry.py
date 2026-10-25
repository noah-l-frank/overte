"""Original whole Tablet API work budget through final canonical verification."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from functools import wraps
import time
from adapters.native_feature_observation import number
from adapters.normal_ui import NativeUIError
from adapters.operation_transport_guard import scope

BUDGETS={name:60 for name in ('feature.tablet-web.act','feature.tablet-web.observe','feature.tablet-web.cleanup','feature.tablet-web.terminal')}


def installed_entry(function,*,monotonic=time.monotonic):
    @wraps(function)
    def invoke(self,selector,operation,values):
        if operation not in BUDGETS:return function(self,selector,operation,values)
        started=last=monotonic();failed=False
        if not number(started,0,1e15):raise NativeUIError('Tablet API work clock is unavailable')
        def check():
            nonlocal last,failed
            now=monotonic()
            if failed or not number(now,last,started+BUDGETS[operation]) or now>=started+BUDGETS[operation]:
                failed=True;raise NativeUIError('Tablet API deadline exhausted or host clock changed')
            last=now
        with scope(check):
            check();value=function(self,selector,operation,values);check();return value
    return invoke
