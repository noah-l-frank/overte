"""Whole canonical Emote API budget from entry through final verification."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from functools import wraps
import time
from adapters.native_feature_observation import number
from adapters.normal_ui import NativeUIError
from adapters.operation_transport_guard import scope

BUDGETS={'feature.emotes.act':25,'feature.emotes.observe':30,'feature.emotes.cleanup':60}


def installed_entry(function,*,monotonic=time.monotonic):
    @wraps(function)
    def invoke(self,selector,operation,values):
        if operation not in BUDGETS:return function(self,selector,operation,values)
        started=last=monotonic();failed=False
        if not number(started,0,1e15):raise NativeUIError('Emote API work clock is unavailable')
        def check():
            nonlocal last,failed
            now=monotonic()
            if failed or not number(now,last,started+BUDGETS[operation]) or now>=started+BUDGETS[operation]:
                failed=True;raise NativeUIError('Emote API deadline exhausted or host clock changed')
            last=now
        # This pure callback precedes candidate checks and remains registered
        # through the canonical final native binding/candidate verification.
        with scope(check):
            check();result=function(self,selector,operation,values);check();return result
    return invoke
