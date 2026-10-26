"""Real outer deadlines/locks; end readiness is an explicit scheduling model."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from ios.adapters.emote_observer import EmoteObservationPending
from ios.self_tests.test_ios_emote_terminal_controller import TerminalControllerTests


class RootedTerminalEntryTests(unittest.TestCase):
    def setUp(self):
        self.f=TerminalControllerTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.flow,self.actor,_settings=self.f.factory_pair();self.now=0.;self.polls=[];self.sleeps=[]
        self.flow.monotonic=lambda:self.now
        def sleep(seconds):
            self.assertIsNone(self.flow.lock._owner);self.assertIsNone(self.actor.lock._owner)
            self.sleeps.append(seconds);self.now+=seconds
        self.flow.sleep=sleep
        self.controller=SimpleNamespace(actor=self.actor,invoke=self.pending)
        self.patch=patch.object(self.flow.runtime,'_emote_rooted_terminal',return_value=self.controller)
        self.patch.start();self.addCleanup(self.patch.stop)
        self.call=self.f.call('finish',seal=self.f.f.proof['seal'])
    def pending(self,call):
        self.polls.append(self.flow.deadline);raise EmoteObservationPending('Declared OS-window readiness model')
    def test_one_outer_budget_spans_all_pending_reopens_and_polling_is_outside_both_locks(self):
        result=dict(declaredSchedulingModel=True)
        def ready(call):
            self.polls.append(self.flow.deadline)
            if len(self.polls)<3:raise EmoteObservationPending('Declared quiet window still pending')
            return result
        self.controller.invoke=ready
        self.assertEqual(result,self.flow.terminal(self.call))
        self.assertEqual([30.,30.,30.],self.polls);self.assertEqual([.05,.05],self.sleeps)
        self.assertIsNone(self.flow.deadline);self.assertEqual([],self.f.sdk_calls)
    def test_a_pending_result_cannot_renew_an_exhausted_outer_deadline(self):
        def expired(call):self.polls.append(self.flow.deadline);self.now=29.99;raise EmoteObservationPending('Late model')
        self.controller.invoke=expired
        with self.assertRaises(NativeUIError):self.flow.terminal(self.call)
        self.assertEqual([30.],self.polls);self.assertIsNone(self.flow.deadline)
    def test_non_finish_pending_is_not_consumed_by_the_end_poller(self):
        with self.assertRaises(EmoteObservationPending):self.flow.terminal(self.f.call('inspect'))
        self.assertEqual([30.],self.polls);self.assertEqual([],self.sleeps)
    def test_backward_clock_after_pending_cannot_poll_or_restart(self):
        def backwards(call):self.now=-1.;raise EmoteObservationPending('Declared changed host clock')
        self.controller.invoke=backwards
        with self.assertRaises(NativeUIError):self.flow.terminal(self.call)
        self.assertEqual([],self.sleeps);self.assertEqual([],self.f.sdk_calls)


if __name__=='__main__':unittest.main()
