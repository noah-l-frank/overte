"""Actual fresh multi-read fixture stamps; no source query or device executes."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from adapters.normal_ui import NativeUIError
from ios.adapters import emote_world
from ios.self_tests.assets_geometry_release_fixture import DomainProducer
from ios.self_tests import test_ios_create_state as create
from ios.self_tests.assets_reply_fixture import RUN


class NativeState:
    elapsed=0
    def tick(self):self.elapsed+=1;return create.EPOCH+self.elapsed
    def state(self):
        value=create.version2(create.packet());self.tick()
        value['clockBefore']=dict(epochMs=create.EPOCH+self.elapsed,monotonicMs=self.elapsed)
        value['clockAfter']=dict(epochMs=self.tick(),monotonicMs=self.elapsed)
        return value


class AssetsGeometryClockTests(unittest.TestCase):
    def query(self,index):return dict(schemaVersion=1,action=emote_world.ACTION,commandId='ios-'+format(index,'032x'),runId=RUN)
    def test_fresh_domain_reads_advance_both_real_producer_clocks_without_retiming_the_prior_original(self):
        state=NativeState();producer=DomainProducer(state);first=producer(self.query(1));saved=deepcopy(first)
        state.elapsed+=3200;last=producer(self.query(2))
        emote_world.validate(last,self.query(2),42,previous=first)
        utc=last['clockBefore']['epochMs']-first['clockAfter']['epochMs']
        mono=last['clockBefore']['monotonicMs']-first['clockAfter']['monotonicMs']
        self.assertEqual(utc,mono);self.assertGreaterEqual(mono,3200);self.assertEqual(saved,first)
        self.assertEqual(first['instance'],last['instance']);self.assertGreater(last['sequence'],first['sequence'])
    def test_relabeling_the_old_constant_monotonic_sample_clock_cannot_replace_current_original_progress(self):
        state=NativeState();producer=DomainProducer(state);first=producer(self.query(1));state.elapsed+=3200;last=producer(self.query(2))
        last['clockBefore']['monotonicMs']=last['clockAfter']['monotonicMs']=0
        with self.assertRaises(NativeUIError):emote_world.validate(last,self.query(2),42,previous=first)
