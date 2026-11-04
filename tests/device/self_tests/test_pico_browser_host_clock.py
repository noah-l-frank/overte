"""Actual host time/identity for declared Browser model producers only."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import time
import unittest
from unittest.mock import patch
from adapters.host_process_identity import host_identity
from adapters.normal_ui import NativeUIError
from self_tests.pico_browser_host_clock import BrowserHostClock


class BrowserHostClockTests(unittest.TestCase):
    def test_unrequested_real_work_advances_original_host_and_epoch_clocks(self):
        clock=BrowserHostClock();first=clock.now();epoch=clock.epoch()
        time.sleep(.025)
        self.assertGreaterEqual(clock.now()-first,.025)
        self.assertGreaterEqual(clock.epoch()-epoch,20)
        self.assertEqual(host_identity(),clock.host)

    def test_explicit_sleep_is_one_real_sleep_without_artificial_clock_offset(self):
        clock=BrowserHostClock();original=time.sleep
        with patch.object(time,'sleep',wraps=original) as sleep:
            first=clock.now();clock.sleep(.025);elapsed=clock.now()-first
        sleep.assert_called_once_with(.025)
        self.assertGreaterEqual(elapsed,.025)
        self.assertLessEqual(abs(clock.epoch()-time.time_ns()//1000000),10)

    def test_ticks_advance_on_actual_host_milliseconds_and_never_manufacture_future_epoch(self):
        clock=BrowserHostClock();before=time.monotonic()
        epochs=[clock.tick() for _ in range(5)]
        self.assertTrue(all(b>a for a,b in zip(epochs,epochs[1:])))
        self.assertGreaterEqual(time.monotonic()-before,.002)
        self.assertLessEqual(epochs[-1],time.time_ns()//1000000)

    def test_mutated_birth_identity_refuses_before_further_sleep_or_tick(self):
        clock=BrowserHostClock();clock.host='foreign'
        with patch.object(time,'sleep',side_effect=AssertionError('No sleep after foreign identity')):
            with self.assertRaises(NativeUIError):clock.sleep(.01)
            with self.assertRaises(NativeUIError):clock.tick()

    def test_future_prior_tick_refuses_instead_of_waiting_or_adjusting_epoch(self):
        clock=BrowserHostClock();clock.last_tick=clock.epoch()+2000
        with patch.object(time,'sleep',side_effect=AssertionError('No wait for a fabricated tick')):
            with self.assertRaises(NativeUIError):clock.tick()

    def test_existing_primary_and_actor_stereo_component_is_constructed_with_actual_host_clock(self):
        from self_tests import test_pico_tablet_web_flow as flow
        from self_tests import test_pico_tablet_web_stereo_flow as stereo
        case=stereo.PicoTabletWebStereoFlowTests()
        try:
            with patch.object(flow,'Clock',BrowserHostClock):case.setUp()
            self.assertIs(type(case.fixture.clock),BrowserHostClock)
            case.test_actual_parent_and_independent_actor_publish_separate_original_stereo_journals()
        finally:case.doCleanups()


if __name__=='__main__':unittest.main()
