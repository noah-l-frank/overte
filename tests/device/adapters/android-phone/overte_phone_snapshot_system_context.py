"""Explicit owner-authorized Snapshot SDK scope across the OS share handoff.

Reuse the existing original OS/kernel/session observer. This scope sends no
native in-client command and changes no foreground-only command protection.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import time
from adapters.native_feature_observation import exact,need,number
from adapters.normal_feature_state import context
from adapters.normal_ui import NativeUIError
from overte_phone_snapshot_resolution import original as resolution
from overte_phone_snapshot_system_ui import component,PRIMARY,RECEIVER_COMPONENT


class SnapshotSystemContext:
    def __init__(self,binding,chooser,observe_binding,current_component,authority,*,monotonic=time.monotonic):
        context(binding);resolution(chooser)
        need(all(callable(fn) for fn in (observe_binding,current_component,authority,monotonic)))
        self.binding,self.chooser=deepcopy(binding),deepcopy(chooser)
        self.observe_binding,self.current_component,self.authority,self.monotonic=observe_binding,current_component,authority,monotonic
        self.last_clock=None

    def _status(self):
        value=self.observe_binding();exact(value,{'binding','foreground','running','appState'})
        context(value['binding'])
        need(value['binding']==self.binding and value['running'] is True and type(value['foreground']) is bool
            and type(value['appState']) is int and value['appState'] in (2,3,4) and value['foreground']==(value['appState']==4))
        return value

    def _allowed_component(self,actual):
        return actual in (self.chooser['component'],RECEIVER_COMPONENT)

    def guard(self):
        try:
            need(self.authority() is True)
            start=self.monotonic();need(number(start,0,1e15) and (self.last_clock is None or start>=self.last_clock))
            before=self._status();actual=self.current_component()
            need(type(actual) is str and actual.count('/')==1)
            package,activity=actual.split('/');need(actual==component(package,activity))
            if package==PRIMARY:need(before['foreground'])
            else:need(self._allowed_component(actual))
            after=self._status();now=self.monotonic()
            need(after==before and self.authority() is True and number(now,start,1e15) and now-start<=1.5)
            self.last_clock=now;return True
        except Exception:raise NativeUIError('Original Snapshot system handoff authority or process continuity was lost') from None
