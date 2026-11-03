"""Optional common input context ordering, without promoting any Pico facts."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
import unittest
from feature_journeys.engine import Journey
from self_tests.test_feature_journeys import Boundary,RUN,POLICY


class CreateOperationEngineTests(unittest.TestCase):
    def execute(self,boundary,*,fail_act=False):
        held=[];events=[];activate=boundary.activate;invoke=boundary.invoke;continuity=boundary.continuity
        @contextmanager
        def context(kind,fields):
            self.assertFalse(held);self.assertIn(kind,('prepare','act','cleanup'))
            if kind=='act':
                self.assertEqual({'contractVersion','runId','verb','inputs','ticket','fixtureUrl'},set(fields));self.assertNotIn('expectedFacts',fields)
            else:self.assertIsNone(fields)
            held.append(kind);events.append(('enter',kind))
            try:yield
            finally:events.append(('exit',kind));held.pop()
        def activating(*args,**kwargs):
            self.assertTrue(held);events.append(('activate',held[-1]));return activate(*args,**kwargs)
        def invoking(operation,fields):
            kind=operation.rsplit('.',1)[1]
            if kind in ('act','cleanup'):
                self.assertTrue(held);self.assertEqual(kind,held[-1]);events.append(('input',kind))
                if fail_act and kind=='act':raise ValueError('Explicit ordinary input failure')
            return invoke(operation,fields)
        def continuous(phase,verb):
            if phase in ('before','after'):self.assertEqual(['act'],held)
            return continuity(phase,verb)
        journey=Journey(boundary.area,RUN,f'http://controlled.test/feature-fixture/v1/runs/{RUN}/',invoke=invoking,witness=boundary.witness,
            activate=activating,read_artifact=boundary.files.__getitem__,image_policy=POLICY,continuity=continuous,
            monotonic=lambda:boundary.clock,epoch_ms=boundary.epoch,sleep=boundary.sleep,report=boundary.reports.append,
            navigation_source=boundary.navigation_source,input_context=context)
        try:return journey.execute(),events
        finally:self.assertFalse(held);self.assertEqual(sum(kind=='enter' for kind,_ in events),sum(kind=='exit' for kind,_ in events))
    def test_original_create_phase_activation_and_normal_inputs_are_inside_actual_context(self):
        phases,events=self.execute(Boundary('create'));self.assertTrue(phases)
        self.assertEqual(('enter','prepare'),events[0]);self.assertEqual(('activate','prepare'),events[1]);self.assertEqual(('exit','prepare'),events[2])
        self.assertEqual(2,events.count(('input','cleanup')))
    def test_original_normal_input_failure_still_unwinds_context_before_cleanup(self):
        with self.assertRaisesRegex(ValueError,'ordinary input failure'):self.execute(Boundary('create'),fail_act=True)
