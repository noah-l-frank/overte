"""Actual shared cleanup ordering; product/native sources remain boundary models."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import json
import unittest

from feature_journeys.engine import Journey
from self_tests.test_feature_journeys import Boundary,POLICY,RUN


class FeatureCleanupConsumptionTests(unittest.TestCase):
    def journey(self,boundary,callback):
        return Journey(boundary.area,RUN,f'http://controlled.test/feature-fixture/v1/runs/{RUN}/',
            invoke=boundary.invoke,witness=boundary.witness,activate=boundary.activate,
            read_artifact=boundary.files.__getitem__,image_policy=POLICY,continuity=boundary.continuity,
            monotonic=lambda:boundary.clock,epoch_ms=boundary.epoch,sleep=boundary.sleep,
            report=boundary.reports.append,after_cleanup_baseline=callback)

    def test_finalizer_gets_only_immutable_actual_consumption_after_both_cleanup_calls_and_full_baseline(self):
        boundary=Boundary('chat');received=[]
        def finalize(raw):
            self.assertIs(type(raw),bytes);self.assertEqual([],boundary.reports)
            self.assertEqual(2,sum(op.endswith('.cleanup') for op,_ in boundary.actions))
            value=json.loads(raw);received.append(raw)
            self.assertEqual('cleanup-restored-baseline',value['phase']['phase'])
            self.assertGreaterEqual(value['phase']['stableSeconds'],3)
            self.assertGreaterEqual(len(value['samples']),13)
            self.assertTrue(value['sequenceSucceeded'])
            self.assertTrue(all(row['ticket']==boundary.ticket and row['witness'] is not None for row in value['samples']))
            # The callback receives an independently decoded historical value.
            value['samples'][-1]['state']['draft']='changed by callback'
        journey=self.journey(boundary,finalize);journey.execute()
        self.assertEqual([journey.cleanup_consumption],received)
        self.assertEqual('',journey.samples[-1]['state']['draft'])
        self.assertTrue(boundary.reports[0]['cleanupSucceeded']);self.assertTrue(boundary.reports[0]['sequenceCompleted'])
        before=len(boundary.actions)
        with self.assertRaisesRegex(ValueError,'cannot be replayed'):journey.execute()
        self.assertEqual(before,len(boundary.actions));self.assertEqual(1,len(received))

    def test_lost_or_failed_finalization_keeps_both_success_flags_false_and_never_calls_twice(self):
        boundary=Boundary('chat');calls=[];failure=OSError('final output unavailable')
        def finalize(raw):calls.append(raw);raise failure
        journey=self.journey(boundary,finalize)
        with self.assertRaises(OSError) as caught:journey.execute()
        self.assertIs(failure,caught.exception);self.assertEqual(1,len(calls))
        self.assertFalse(boundary.reports[0]['cleanupSucceeded']);self.assertFalse(boundary.reports[0]['sequenceCompleted'])
        with self.assertRaisesRegex(ValueError,'cannot be replayed'):journey.execute()
        self.assertEqual(1,len(calls))

    def test_failed_actual_cleanup_never_invokes_finalizer(self):
        boundary=Boundary('chat','cleanup-resource-leak');calls=[];journey=self.journey(boundary,calls.append)
        with self.assertRaises(AssertionError):journey.execute()
        self.assertEqual([],calls);self.assertIsNone(journey.cleanup_consumption)
        self.assertFalse(boundary.reports[0]['cleanupSucceeded'])

    def test_primary_error_remains_primary_even_if_postbaseline_cleanup_finalizer_fails(self):
        boundary=Boundary('chat');invoke=boundary.invoke;primary=RuntimeError('ordinary input uncertain');calls=[]
        def uncertain(operation,fields):
            if operation.endswith('.act'):raise primary
            return invoke(operation,fields)
        boundary.invoke=uncertain
        def finalize(raw):calls.append(json.loads(raw));raise OSError('closure uncertain')
        journey=self.journey(boundary,finalize)
        with self.assertRaises(RuntimeError) as caught:journey.execute()
        self.assertIs(primary,caught.exception);self.assertEqual(1,len(calls));self.assertFalse(calls[0]['sequenceSucceeded'])
        self.assertFalse(boundary.reports[0]['cleanupSucceeded']);self.assertFalse(boundary.reports[0]['sequenceCompleted'])

    def test_default_shared_path_emits_no_finalization_receipt(self):
        boundary=Boundary('chat');journey=self.journey(boundary,None);journey.execute()
        self.assertIsNone(journey.cleanup_consumption);self.assertFalse(journey.cleanup_hook_started)
        self.assertTrue(boundary.reports[0]['sequenceCompleted'])


if __name__=='__main__':unittest.main()
