"""Original independent fixture/clock admission; no Qt or product inputs."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import unittest
import uuid

from adapters.chat_journey.phase_fence import ChatPhaseFence,bind_phase_fence
from adapters.normal_ui import NativeUIError
from self_tests import test_chat_witness as witness_seams
from self_tests.test_native_chat_observation import RUN


class PhaseFenceTests(unittest.TestCase):
    def setUp(self):
        self.h=witness_seams.WitnessTests();self.h.setUp();self.addCleanup(self.h.doCleanups)
        self.flow=self.h.flow;self.fence=ChatPhaseFence(self.flow)
        with self.flow.session():self.flow.begin(self.flow.source.read())
    def queries(self):return [len(source.commands) for source in (self.h.h.h.primary,self.h.h.h.peer,self.h.h.h.view,self.h.h.h.native)]
    def test_transport_fence_owner_cannot_be_silently_replaced(self):
        from types import SimpleNamespace
        owner=SimpleNamespace();bind_phase_fence(owner,self.fence);bind_phase_fence(owner,self.fence)
        with self.assertRaises((ValueError,NativeUIError)):bind_phase_fence(owner,ChatPhaseFence(self.flow))
        self.assertIs(self.fence,owner.phase_fence);self.assertEqual([],self.fence.frames)

    def test_each_admission_has_new_original_request_and_exact_same_ticket_prefix_without_qt(self):
        before=self.queries()
        with self.flow.session():
            self.fence.mark();first=self.fence.check();second=self.fence.check()
        self.assertNotEqual(first['requestId'],second['requestId']);self.assertGreater(second['sequence'],first['sequence'])
        self.assertIsNot(self.flow.source,self.fence.source);self.assertEqual(before,self.queries())
        self.assertEqual(self.flow.rows[-1]['before']['activations'],second['activations'])
    def test_actual_phase_change_and_retirement_prevent_transport_without_rearming(self):
        for retired in (False,True):
            with self.subTest(retired=retired):
                self.setUp()
                with self.flow.session():
                    self.fence.mark()
                    if retired:
                        value=self.h.journal.runs.pop(RUN);value['retiredEpochMs']=self.h.h.native.epoch
                        self.h.journal.retired_phases[RUN]=value
                    else:self.h.journal.activate(RUN,uuid.uuid4().hex,'open',{})
                    with self.assertRaises((ValueError,NativeUIError)):self.fence.check()
                    with self.assertRaises((ValueError,NativeUIError)):self.fence.mark()
    def test_slow_cas_native_jump_under_frozen_host_and_actual_host_gap_do_not_refresh_anchor(self):
        for native in (False,True):
            with self.subTest(native=native):
                self.setUp()
                with self.flow.session():
                    self.fence.mark()
                    if native:self.h.h.native.epoch+=2000
                    else:self.h.h.native.host+=2
                    with self.assertRaises((ValueError,NativeUIError)):self.fence.check()
                self.assertTrue(self.fence.failed)
    def test_phase_response_and_final_copy_cannot_age_after_the_last_clock_check(self):
        original=self.fence.source.read
        def late(previous):
            value=original(previous);self.h.h.native.epoch+=2000;return value
        with self.flow.session():
            self.fence.mark();self.fence.source.read=late
            with self.assertRaises((ValueError,NativeUIError)):self.fence.check()
        self.assertTrue(self.fence.failed)

    def test_final_host_guard_cannot_hide_a_native_jump_after_the_current_phase_response(self):
        with self.flow.session():
            self.fence.mark();guard=self.fence.host_fresh
            def late():guard();self.h.h.native.epoch+=2000
            self.fence.host_fresh=late
            with self.assertRaises((ValueError,NativeUIError)):self.fence.check()
        self.assertTrue(self.fence.failed)


if __name__=='__main__':unittest.main()
