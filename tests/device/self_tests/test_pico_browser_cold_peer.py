"""Actual Common startup with a declared lazy browser/independent peer model."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import unittest
from feature_journeys.engine import Journey
from self_tests import test_feature_journeys as fixture


class BrowserColdPeerTests(unittest.TestCase):
    def setup_journey(self,*,unknown=False):
        boundary=fixture.Boundary('tablet-web');self.boundary=boundary;self.attempts=[];self.before_peer=[]
        def invoke(operation,fields):
            if operation.endswith('.observe'):
                self.attempts.append(operation)
                if unknown:raise OSError('Declared lost first original observation')
            return boundary.invoke(operation,fields)
        def peer():
            self.before_peer.append(boundary.sequence)
            if not boundary.sequence:return boundary.journal.snapshot(fixture.RUN)
            return boundary.witness()
        self.journey=Journey('tablet-web',fixture.RUN,f'http://controlled.test/feature-fixture/v1/runs/{fixture.RUN}/',
            invoke=invoke,witness=peer,activate=boundary.activate,read_artifact=boundary.files.__getitem__,
            image_policy=fixture.POLICY,continuity=boundary.continuity,monotonic=lambda:boundary.clock,
            epoch_ms=boundary.epoch,sleep=boundary.sleep,report=boundary.reports.append,poll_work_inclusive=True)

    def test_actual_lazy_owner_observation_precedes_peer_but_cannot_count_as_qualified_baseline(self):
        self.setup_journey();self.journey.execute()
        self.assertTrue(self.before_peer);self.assertEqual(1,self.before_peer[0])
        candidate=self.journey.samples[0]
        self.assertEqual('original-baseline-candidate',candidate['phase']);self.assertIsNone(candidate['witness'])
        self.assertEqual(1,candidate['sequence']);self.assertEqual(28,len(self.journey.phases))
        baseline=[sample for sample in self.journey.samples if sample['phase']=='owned-clean-baseline']
        self.assertGreaterEqual(len(baseline),3)
        self.assertTrue(all(sample['sequence']>1 and sample['witness'] for sample in baseline))
        self.assertTrue(self.boundary.reports[-1]['sequenceCompleted'])

    def test_unknown_first_observation_is_not_retried_and_cannot_start_peer_or_normal_actions(self):
        self.setup_journey(unknown=True)
        with self.assertRaises(OSError):self.journey.execute()
        self.assertEqual(1,len(self.attempts));self.assertEqual([],self.before_peer)
        self.assertEqual([],self.boundary.actions);self.assertEqual([],self.journey.phases)

    def test_changed_poll_policy_refuses_before_cold_source_or_peer_acquisition(self):
        self.setup_journey();self.journey.poll_work_inclusive=False
        with self.assertRaises(ValueError):self.journey.execute()
        self.assertEqual([],self.attempts);self.assertEqual([],self.before_peer);self.assertEqual([],self.boundary.actions)


if __name__=='__main__':unittest.main()
