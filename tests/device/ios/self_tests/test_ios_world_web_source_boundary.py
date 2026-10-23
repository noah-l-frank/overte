"""Standalone native producer clocks and weak lifetimes; no feature owner."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import gc
import unittest
from ios.self_tests.world_web_surfaces_fixture import CacheOriginals
from ios.adapters.world_web_surfaces import source


class WorldWebSourceBoundaryTests(unittest.TestCase):
    def test_legacy_default_clock_and_pid_are_literal_and_reads_do_not_end_weak_lease(self):
        cache=CacheOriginals();cache.reserve();value=cache.read()
        self.assertEqual((42,20004,4),(value['processId'],value['capturedEpochMs'],value['monotonicMs']))
        self.assertEqual([20001,20002,20003],[row['epochMs'] for row in value['events']])
        source(value,42,value['capturedEpochMs'])

    def test_injected_observation_clock_and_pid_are_taken_before_new_original_and_never_retime_old(self):
        calls=[];now=[1700000000000]
        def epoch():now[0]+=1;calls.append(now[0]);return now[0]
        cache=CacheOriginals(clock_ms=epoch,monotonic_ms=lambda:now[0]-1700000000000,pid=73)
        cache.reserve();renderer=cache.acquire('12345678-1234-4234-8234-123456789012','http://controlled.invalid/index.html')
        first=cache.read();held=renderer['lease'];cache.release(renderer);second=cache.read()
        self.assertEqual(73,first['processId']);self.assertEqual(calls[-1],second['capturedEpochMs'])
        self.assertEqual(list(range(1,len(calls)+1)),[n-1700000000000 for n in calls])
        self.assertEqual(first['events'],second['events'][:len(first['events'])]);self.assertTrue(second['leases'][0]['alive'])
        source(first,73,first['capturedEpochMs']);source(second,73,second['capturedEpochMs'],first)
        del held;gc.collect();third=cache.read();source(third,73,third['capturedEpochMs'],second)
        self.assertFalse(third['leases'][0]['alive']);self.assertTrue(third['surfaces'][0]['rootAlive'])
        self.assertTrue(first['leases'][0]['alive']);self.assertLess(first['capturedEpochMs'],third['capturedEpochMs'])


if __name__=='__main__':unittest.main()
