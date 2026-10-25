"""Closed new finish budget, unchanged old intents and final send guards.

These are operation-clock checks only, never terminal/product evidence.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from unittest.mock import patch

from adapters.normal_ui import NativeUIError
from ios.adapters import avatar_api_entry as api,avatar_operation_clock as old
from ios.adapters import appium_adapter as backend
from ios.adapters.avatar_terminal import terminal_clock_begin,terminal_clock_validate,terminal_clock_check


class AvatarTerminalClockTests(unittest.TestCase):
    def test_new_finish_clock_has_original_thirty_seconds_and_never_extends_a_legacy_intent(self):
        value=terminal_clock_begin(10000,1.);original=deepcopy(value)
        self.assertEqual(30.999,terminal_clock_check(value,39999,30.999))
        with self.assertRaises(NativeUIError):terminal_clock_check(value,40000,31.)
        self.assertEqual(original,value)
        legacy=old.begin(10000,1.);before=deepcopy(legacy)
        self.assertEqual(legacy,terminal_clock_validate(legacy))
        with self.assertRaises(NativeUIError):terminal_clock_check(legacy,35000,26.)
        self.assertEqual(before,legacy)
        bad=deepcopy(value);bad['avatarTerminalClockVersion']=True
        with self.assertRaises(NativeUIError):terminal_clock_validate(bad)

    def test_only_typed_finish_selects_thirty_and_nested_earlier_budget_still_expires(self):
        clock=[0.]
        class Flow:
            monotonic=staticmethod(lambda:clock[0])
            @api.operation
            def terminal(self,call):clock[0]=26.;api.check();return 'budget-only'
            @api.operation
            def act(self,call):clock[0]=26.;api.check();return 'budget-only'
        self.assertEqual('budget-only',Flow().terminal(dict(stage='finish')))
        clock[0]=0.;self.assertEqual('budget-only',Flow().terminal(call=dict(stage='finish')))
        for method,call in (('terminal',dict(stage='seal')),('terminal',dict(stage='inspect')),('act',{})):
            clock[0]=0.
            with self.assertRaises(NativeUIError):getattr(Flow(),method)(call)
        clock[0]=0.
        with self.assertRaises(NativeUIError),api.scope(lambda:clock[0]):Flow().terminal(dict(stage='finish'))

    def test_installed_final_candidate_verification_remains_inside_original_finish_budget(self):
        clock=[0.];checks=[]
        def invoke(_self,_selector,_operation,_values):checks.append('actual-final-candidate');clock[0]=30.;return 'budget-only'
        entry=api.installed_entry(invoke,monotonic=lambda:clock[0])
        with self.assertRaises(NativeUIError):entry(None,'primary','feature.avatar-people.terminal',dict(stage='finish'))
        self.assertEqual(['actual-final-candidate'],checks)

    def test_real_last_sdk_guard_refuses_expired_finish_after_serialization_without_any_opener(self):
        clock=[0.];sent=[];dumps=backend.json.dumps
        def slow(*args,**kwargs):result=dumps(*args,**kwargs);clock[0]=30.;return result
        def invoke(_self,_selector,_operation,_values):return backend.WebDriver('http://127.0.0.1:1').call('POST','/session',{})
        entry=api.installed_entry(invoke,monotonic=lambda:clock[0])
        with patch.object(backend.json,'dumps',side_effect=slow),patch.object(backend,'urlopen',side_effect=lambda *_a,**_k:sent.append(True)):
            with self.assertRaises(NativeUIError):entry(None,'primary','feature.avatar-people.terminal',dict(stage='finish'))
        self.assertEqual([],sent)


if __name__=='__main__':unittest.main()
