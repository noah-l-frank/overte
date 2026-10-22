"""Actual bound OS publication fenced by independent original fixture/clock."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import unittest
import uuid
from unittest.mock import patch
import test_lifecycle_transport_once as original
from self_tests import test_chat_phase_fence as phases
from self_tests.test_native_chat_observation import RUN


class ChatLifecyclePhaseTests(unittest.TestCase):
    def test_actual_last_installation_guard_phase_change_or_frozen_host_native_jump_prevents_os_write(self):
        for operation in ('lifecycle.background','app.launch'):
            for late_clock in (False,True):
                with self.subTest(operation=operation,late_clock=late_clock):
                    actual=original.LifecycleOnceTests();actual.setUp();self.addCleanup(actual.doCleanups)
                    actual.foreground=operation=='lifecycle.background'
                    h=phases.PhaseFenceTests();h.setUp();self.addCleanup(h.doCleanups)
                    install=actual.adapter._installation;count=0
                    def installed(target):
                        nonlocal count
                        value=install(target);count+=1
                        if count==2:
                            if late_clock:h.h.h.native.epoch+=2000
                            else:h.h.journal.activate(RUN,uuid.uuid4().hex,'open',{})
                        return value
                    with h.flow.session():
                        h.fence.mark()
                        with patch.object(actual.adapter,'_installation',side_effect=installed):
                            with self.assertRaises(ValueError):
                                actual.adapter._pico_lifecycle_input_once(actual.target,operation,actual.binding,before_input=h.fence.check)
                    self.assertEqual([],actual.inputs);self.assertTrue(h.fence.failed)
                    self.assertEqual([],actual.sdk.inputs);self.assertEqual([],actual.sdk.controllers)


if __name__=='__main__':unittest.main()
