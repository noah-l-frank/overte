"""Real Graphics worker/finalizer composition over host fixtures and SDK models."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import unittest
from adapters.normal_ui import NativeUIError
from ios import graphics_observer as worker
from ios.self_tests.test_ios_graphics_finalization import FinalizationHarness


class GraphicsWorkerFinalizationTests(FinalizationHarness,unittest.TestCase):
    def run_paired_worker(self,*,lost_stop=False):
        self.baseline();actor=self.feature('actor');self.client.close();ticks=[];parent_done=[];lost=[]
        config=dict(fixtureUrl=self.client.url,artifactRoot=str(actor.root),imagePolicy=actor.policy,durationSeconds=120)
        def sleep(seconds):
            self.sdk.clock+=1.1;ticks.append(seconds)
            self.assertLess(len(ticks),15,'Owned actor never reached its original final receipt')
            if lost_stop and self.binding_phase=='bound':self.fault='lost-stop'
            try:
                if self.finalizer().step():parent_done.append(True)
            except NativeUIError:
                if not lost_stop or self.sdk.running or lost:raise
                lost.append(True);self.fault=''
        result=worker.run_flow(config,actor.store.read,actor.retirement_store.read,lambda run:actor,
            monotonic=lambda:self.sdk.clock,sleep=sleep)
        self.assertEqual(0,result);self.assertTrue(parent_done)
        self.assertFalse(self.sdk.running);self.assertEqual(['app.stop'],self.inputs)
        self.assertTrue(self.finalizer('actor').step());self.assertIsNone(actor.store.read())
        self.assertIsNone(actor.retirement_store.read());self.assertFalse(worker.failure(actor,config))
        self.assertEqual(bool(lost),lost_stop)

    def test_actual_worker_waits_for_paired_restoration_os_quiet_window_and_final_receipt(self):
        self.run_paired_worker()

    def test_actual_worker_finishes_original_parent_lost_stop_without_resending_it(self):
        self.run_paired_worker(lost_stop=True)


if __name__=='__main__':unittest.main()
