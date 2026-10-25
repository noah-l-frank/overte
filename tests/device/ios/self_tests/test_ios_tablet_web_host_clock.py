"""Independent OS processes cannot lose or regress shared fixture time."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import multiprocessing
import unittest
from ios.self_tests.tablet_web_host_clock import advance


def advance_many(clock,ready,count):
    ready.wait(timeout=10)
    for _index in range(count):advance(clock,.001)


class TabletHostClockTests(unittest.TestCase):
    def test_actual_independent_processes_retain_all_concurrent_increments(self):
        context=multiprocessing.get_context('spawn');clock=context.Value('d',0.)
        ready=context.Barrier(3);workers=[context.Process(target=advance_many,args=(clock,ready,2000)) for _ in range(2)]
        try:
            for worker in workers:worker.start()
            ready.wait(timeout=10)
            previous=clock.value
            for worker in workers:
                worker.join(10);self.assertEqual(0,worker.exitcode)
                now=clock.value;self.assertGreaterEqual(now,previous);previous=now
            self.assertAlmostEqual(4.,clock.value,places=9)
        finally:
            for worker in workers:
                if worker.is_alive():worker.terminate();worker.join(5)

    def test_invalid_increment_never_changes_the_original_model_clock(self):
        clock=multiprocessing.get_context('spawn').Value('d',7.)
        for seconds in (-1,True,float('nan'),float('inf')):
            with self.subTest(seconds=seconds),self.assertRaises(ValueError):advance(clock,seconds)
            self.assertEqual(7.,clock.value)
        self.assertEqual(7.,advance(clock,0))


if __name__=='__main__':unittest.main()
