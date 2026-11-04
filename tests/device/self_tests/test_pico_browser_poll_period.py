"""Actual Common wait grammar with declared source-work timing models.

The source/peer reducer is a host model. It does not qualify VR or a complete
browser coordinator, and all original sample/quiet/deadline checks still run.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest

from feature_journeys.engine import Journey
from feature_journeys.scenarios import SCENARIOS
from self_tests import test_feature_journeys as fixture


class BrowserPollPeriodTests(unittest.TestCase):
    def setup_wait(self,*,enabled=True,work=.3,fault='',area='tablet-web'):
        boundary=fixture.Boundary(area,fault);boundary.activate(fixture.TICKET)
        sleeps=[];reads=[]
        def invoke(operation,fields):
            if operation.endswith('.observe'):
                boundary.clock+=work;reads.append(boundary.clock)
            return boundary.invoke(operation,fields)
        def sleep(delay):sleeps.append(delay);boundary.sleep(delay)
        journey=Journey(area,fixture.RUN,f'http://controlled.test/feature-fixture/v1/runs/{fixture.RUN}/',
            invoke=invoke,witness=boundary.witness,activate=boundary.activate,
            read_artifact=boundary.files.__getitem__,image_policy=fixture.POLICY,
            continuity=boundary.continuity,monotonic=lambda:boundary.clock,epoch_ms=boundary.epoch,
            sleep=sleep,report=boundary.reports.append,poll_work_inclusive=enabled)
        self.boundary,self.journey,self.sleeps,self.reads=boundary,journey,sleeps,reads
        return journey

    def wait(self,*,duration=.5,kinds=()):
        return self.journey.wait('declared-poll-checkpoint',fixture.TICKET,2_000_000,
            deepcopy(SCENARIOS['tablet-web']['baseline']),kinds,duration=duration)

    def test_default_keeps_fixed_quarter_second_sleep_and_original_three_sample_rule(self):
        self.setup_wait(enabled=False);self.wait()
        self.assertEqual([.25,.25],self.sleeps);self.assertEqual(3,len(self.reads))
        self.assertAlmostEqual(1.4,self.boundary.clock)
        self.assertGreaterEqual(self.journey.phases[-1]['stableSeconds'],.5)

    def test_slow_actual_source_work_is_included_and_independent_peer_checks_remain_required(self):
        self.setup_wait();self.wait(kinds=('peer',))
        self.assertEqual([.01,.01],self.sleeps);self.assertEqual(3,len(self.reads))
        self.assertAlmostEqual(.92,self.boundary.clock)
        self.assertTrue(all(row['witness'] for row in self.journey.samples))
        self.assertGreaterEqual(self.journey.phases[-1]['stableSeconds'],.5)

    def test_fast_source_uses_remaining_period_instead_of_reducing_sample_spacing(self):
        self.setup_wait(work=.1);self.wait()
        self.assertTrue(self.sleeps);self.assertTrue(all(abs(delay-.15)<1e-9 for delay in self.sleeps))
        self.assertTrue(all(abs(b-a-.25)<1e-9 for a,b in zip(self.reads,self.reads[1:])))

    def test_three_second_quiet_window_is_measured_after_actual_evidence_work(self):
        self.setup_wait();self.wait(duration=3,kinds=('peer',))
        phase=self.journey.phases[-1]
        self.assertGreaterEqual(phase['stableSeconds'],3);self.assertGreaterEqual(phase['advancingSamples'],3)
        self.assertGreaterEqual(self.reads[-1]-self.reads[0],3)

    def test_original_checkpoint_expiry_during_source_work_has_no_sleep_or_second_query(self):
        self.setup_wait(work=21)
        with self.assertRaisesRegex(AssertionError,'checkpoint deadline'):self.wait()
        self.assertEqual(1,len(self.reads));self.assertEqual([],self.sleeps);self.assertEqual([],self.journey.phases)

    def test_stale_source_and_missing_fresh_peer_cannot_pass_faster_polling(self):
        self.setup_wait(fault='stale-sample')
        with self.assertRaises(ValueError):self.wait()
        self.assertEqual([],self.sleeps);self.assertEqual([],self.journey.phases)
        self.setup_wait(fault='missing-witness')
        with self.assertRaises(AssertionError):self.wait(kinds=('peer',))
        self.assertEqual([],self.journey.phases)

    def test_policy_is_explicit_exact_boolean_and_cannot_change_before_another_acquisition(self):
        for enabled,area in ((1,'tablet-web'),(True,'chat')):
            with self.subTest(enabled=enabled,area=area),self.assertRaises(ValueError):
                self.setup_wait(enabled=enabled,area=area)
        self.setup_wait();self.journey.poll_work_inclusive=False
        with self.assertRaises(ValueError):self.wait()
        self.assertEqual([],self.reads)


if __name__=='__main__':unittest.main()
