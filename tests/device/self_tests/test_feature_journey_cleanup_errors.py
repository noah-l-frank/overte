"""Failure diagnostics preserve the primary error and private cleanup cause.

The existing device-free boundary exercises normal common journey execution;
transport failures are injected without device, build or compiler access.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import json
import unittest
from feature_journeys.engine import Journey
from self_tests.test_feature_journeys import Boundary,POLICY,RUN


class FeatureJourneyCleanupErrorTests(unittest.TestCase):
    def journey(self,boundary,invoke):
        return Journey(boundary.area,RUN,'http://controlled.test/feature-fixture/v1/runs/'+RUN+'/',
            invoke=invoke,witness=boundary.witness,activate=boundary.activate,
            read_artifact=boundary.files.__getitem__,image_policy=POLICY,continuity=boundary.continuity,
            monotonic=lambda:boundary.clock,epoch_ms=boundary.epoch,sleep=boundary.sleep,report=boundary.reports.append)

    def test_primary_identity_cause_and_existing_notes_survive_secondary_cleanup_failure(self):
        boundary=Boundary('authentication');primary=RuntimeError('controlled primary failure')
        cause=ValueError('original primary cause');primary.__cause__=cause;primary.add_note('existing note')
        private='private-provider-secret@example.invalid';cleanup=OSError(private)
        def invoke(operation,values):
            if operation.endswith('.act'):raise primary
            if operation.endswith('.cleanup'):raise cleanup
            return boundary.invoke(operation,values)
        journey=self.journey(boundary,invoke)
        with self.assertRaises(RuntimeError) as raised:journey.execute()
        self.assertIs(primary,raised.exception);self.assertIs(cause,raised.exception.__cause__)
        self.assertEqual('existing note',raised.exception.__notes__[0])
        self.assertIn('Journey.cleanup_errors',raised.exception.__notes__[-1])
        self.assertEqual((cleanup,),journey.cleanup_errors)
        self.assertIsNotNone(cleanup.__traceback__)
        self.assertEqual(private,str(journey.cleanup_errors[0]))
        self.assertNotIn(private,' '.join(raised.exception.__notes__))
        self.assertNotIn(private,json.dumps(boundary.reports))
        self.assertFalse(boundary.reports[0]['cleanupSucceeded'])
        self.assertFalse(boundary.reports[0]['sequenceCompleted'])

    def test_cleanup_failure_without_primary_is_still_raised_as_the_original_error(self):
        boundary=Boundary('authentication');cleanup=OSError('controlled cleanup failure')
        def invoke(operation,values):
            if operation.endswith('.cleanup'):raise cleanup
            return boundary.invoke(operation,values)
        journey=self.journey(boundary,invoke)
        with self.assertRaises(OSError) as raised:journey.execute()
        self.assertIs(cleanup,raised.exception);self.assertEqual((cleanup,),journey.cleanup_errors)
        self.assertFalse(boundary.reports[0]['cleanupSucceeded'])

    def test_successful_cleanup_keeps_primary_failure_without_a_secondary_note(self):
        boundary=Boundary('authentication');primary=RuntimeError('controlled primary failure')
        def invoke(operation,values):
            if operation.endswith('.act'):raise primary
            return boundary.invoke(operation,values)
        journey=self.journey(boundary,invoke)
        with self.assertRaises(RuntimeError) as raised:journey.execute()
        self.assertIs(primary,raised.exception);self.assertEqual((),journey.cleanup_errors)
        self.assertFalse(getattr(primary,'__notes__',[]))
        self.assertTrue(boundary.reports[0]['cleanupSucceeded'])
        self.assertFalse(boundary.reports[0]['sequenceCompleted'])


if __name__=='__main__':unittest.main()
