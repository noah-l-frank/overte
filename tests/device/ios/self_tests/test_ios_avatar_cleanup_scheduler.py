"""Actual concurrent waits preserve one existing model clock, without facts."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import threading
import unittest
from ios.self_tests.avatar_cleanup_scheduler import CleanupScheduler


class CleanupSchedulerTests(unittest.TestCase):
    @staticmethod
    def finish_primary_and_join(scheduler,worker):
        with scheduler.condition:
            if 'primary' in scheduler.roles:scheduler.finish('primary')
        worker.join(1)

    def test_parallel_equal_waits_advance_once(self):
        clock=[1.];scheduler=CleanupScheduler(clock,lambda seconds:clock.__setitem__(0,clock[0]+seconds));done=[]
        def actor():scheduler.sleep('actor',.1);done.append('actor');scheduler.finish('actor')
        worker=threading.Thread(target=actor,daemon=True);worker.start()
        self.addCleanup(self.finish_primary_and_join,scheduler,worker)
        scheduler.sleep('primary',.1);scheduler.finish('primary');worker.join(1)
        self.assertFalse(worker.is_alive());self.assertEqual(['actor'],done);self.assertAlmostEqual(1.1,clock[0])
        self.assertEqual(1,len(scheduler.steps))

    def test_busy_peer_cpu_or_lock_wait_adds_no_model_time_or_original_event(self):
        clock=[1.];events=[]
        def advance(seconds):events.append(seconds);clock[0]+=seconds
        scheduler=CleanupScheduler(clock,advance);done=[]
        def actor():scheduler.sleep('actor',.25);done.append('actor');scheduler.finish('actor')
        worker=threading.Thread(target=actor,daemon=True);worker.start()
        self.addCleanup(self.finish_primary_and_join,scheduler,worker)
        with scheduler.condition:
            self.assertTrue(scheduler.condition.wait_for(lambda:scheduler.roles.get('actor') is not None,1))
            self.assertEqual([],events);self.assertEqual(1.,clock[0]);self.assertEqual([],done)
        scheduler.sleep('primary',.1);self.assertAlmostEqual(1.1,clock[0]);scheduler.finish('primary');worker.join(1)
        self.assertFalse(worker.is_alive());self.assertAlmostEqual(1.25,clock[0]);self.assertEqual(2,len(events))


if __name__=='__main__':unittest.main()
