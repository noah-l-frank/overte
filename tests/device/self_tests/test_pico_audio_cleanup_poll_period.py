"""Actual shared-engine cleanup timing; source work is a declared host model."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json, unittest
from feature_journeys.engine import Journey
from feature_journeys.scenarios import SCENARIOS
from self_tests.test_feature_journeys import Boundary,POLICY,RUN,TICKET

class AudioCleanupPollPeriodTests(unittest.TestCase):
    def setup_wait(self,*,profile='pico-audio-cleanup1',area='audio',work=.3,peer_work=0):
        self.boundary=b=Boundary(area);b.activate(TICKET);self.reads=[];self.sleeps=[];self.receipts=[]
        def invoke(op,fields):
            if op.endswith('.observe'):b.clock+=work;self.reads.append(b.clock)
            return b.invoke(op,fields)
        def sleep(seconds):self.sleeps.append(seconds);b.sleep(seconds)
        def witness():
            b.sleep(peer_work)
            return b.witness()
        self.j=Journey(area,RUN,f'http://controlled.test/feature-fixture/v1/runs/{RUN}/',
            invoke=invoke,witness=witness,activate=b.activate,read_artifact=b.files.__getitem__,
            image_policy=POLICY,continuity=b.continuity,monotonic=lambda:b.clock,epoch_ms=b.epoch,
            sleep=sleep,report=b.reports.append,after_cleanup_baseline=self.receipts.append,
            audio_cleanup_poll_profile=profile)
    def wait(self,label='cleanup-restored-baseline',duration=3):
        return self.j.wait(label,TICKET,2_000_000,deepcopy(SCENARIOS['audio']['baseline']),['peer'],duration=duration)
    def test_original_default_fixed_sleep_is_preserved(self):
        self.setup_wait(profile=None);self.wait(duration=.5)
        self.assertEqual([.25,.25],self.sleeps)
    def test_only_actual_cleanup_window_uses_remaining450ms_period(self):
        self.setup_wait();self.wait()
        self.assertEqual(8,len(self.reads));self.assertTrue(all(abs(s-.15)<1e-9 for s in self.sleeps))
        self.assertTrue(all(abs(b-a-.45)<1e-9 for a,b in zip(self.reads,self.reads[1:])))
        self.assertGreaterEqual(self.j.phases[-1]['stableSeconds'],3)
        self.assertTrue(all(x['witness'] for x in self.j.samples))
        self.j.consumed_cleanup(TICKET,2_000_000,0)
        self.assertEqual([self.j.cleanup_consumption],self.receipts)
        self.assertFalse(json.loads(self.receipts[0])['sequenceSucceeded'])
    def test_other_audio_checkpoints_keep_default_sleep(self):
        self.setup_wait();self.wait(label='normal-audio-checkpoint',duration=.5)
        self.assertEqual([.25,.25],self.sleeps)
    def test_slow_source_cannot_hide_from_original20second_deadline(self):
        self.setup_wait(work=21)
        with self.assertRaisesRegex(AssertionError,'checkpoint deadline'):self.wait()
        self.assertEqual(1,len(self.reads));self.assertEqual([],self.sleeps);self.assertEqual([],self.receipts)
    def test_typed_selection_refuses_other_feature_before_any_source(self):
        for profile,area in ((True,'audio'),(1,'audio'),('pico-audio-cleanup1','chat'),('unknown','audio')):
            with self.subTest(profile=profile,area=area),self.assertRaises(ValueError):self.setup_wait(profile=profile,area=area)
            self.assertEqual([],self.reads)
    def test_changed_selection_refuses_before_first_acquisition(self):
        self.setup_wait();self.j.audio_cleanup_poll_profile=None
        with self.assertRaisesRegex(ValueError,'profile changed'):self.wait()
        self.assertEqual([],self.reads);self.assertEqual([],self.receipts)
    def test_peer_io_cannot_make_an_expired_primary_qualify_cleanup(self):
        self.setup_wait(peer_work=1.6)
        with self.assertRaisesRegex(AssertionError,'checkpoint deadline'):self.wait()
        self.assertEqual([],self.j.phases);self.assertEqual([],self.receipts)
