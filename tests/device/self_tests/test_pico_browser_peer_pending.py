"""Independent publication cadence versus original Common source windows.

These are declared time/source/peer models running the actual Common grammar;
no Native, canonical coordinator or headset qualification is implied.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from feature_journeys.witness import projection
from self_tests import test_pico_browser_poll_period as fixture_module
from self_tests import test_feature_journeys as source_fixture


class BrowserPeerPendingTests(unittest.TestCase):
    def setup_wait(self,*,enabled=True,period=.4,first=0):
        self.fixture=fixture_module.BrowserPollPeriodTests()
        self.fixture.setup_wait(enabled=enabled,work=.01)
        self.boundary=self.fixture.boundary;self.journey=self.fixture.journey
        self.queries=[];self.next_publication=first
        actual=self.journey.witness
        def independently_timed():
            self.queries.append((len(self.fixture.reads),self.boundary.clock))
            if self.boundary.clock+1e-9>=self.next_publication:
                self.next_publication+=period
                return actual()
            return self.boundary.journal.snapshot(source_fixture.RUN)
        self.journey.witness=independently_timed

    def test_faster_primary_waits_for_new_independent_publication_without_extra_product_read(self):
        self.setup_wait(enabled=False)
        with self.assertRaises(AssertionError):self.fixture.wait(kinds=('peer',))
        self.assertEqual([],self.journey.phases)
        self.setup_wait();self.fixture.wait(kinds=('peer',))
        self.assertEqual(3,len(self.fixture.reads));self.assertGreater(len(self.queries),3)
        self.assertTrue(all(sample['witness'] for sample in self.journey.samples))
        self.assertGreaterEqual(self.journey.phases[-1]['stableSeconds'],.5)
        for index in range(3):
            stamps=[stamp for read,stamp in self.queries if read==index]
            self.assertTrue(stamps);self.assertGreaterEqual(self.fixture.reads[index],stamps[-1])
            self.assertLessEqual(self.fixture.reads[index]-stamps[-1],1.5)

    def test_missing_peer_keeps_original_checkpoint_and_never_issues_a_product_query(self):
        self.setup_wait(first=1000)
        with self.assertRaises(AssertionError):self.fixture.wait(kinds=('peer',))
        self.assertEqual([],self.journey.phases)
        self.assertEqual([],self.fixture.reads);self.assertGreater(len(self.queries),20)
        self.assertEqual([],self.boundary.actions)

    def test_actual_contradicting_peer_is_recorded_and_not_hidden_by_waiting_for_a_replacement(self):
        self.setup_wait();actual=self.journey.witness;calls=[]
        def wrong_first():
            if not calls:
                peer=deepcopy(self.boundary.state);peer['documentLoads']+=1
                self.boundary.actor_sequence+=1
                self.boundary.journal.publish(source_fixture.RUN,dict(ticket=source_fixture.TICKET,
                    actor='owned-observer',actorSequence=self.boundary.actor_sequence,
                    capturedEpochMs=self.boundary.epoch(),facts=projection('tablet-web',peer)))
                self.next_publication=.4
                value=self.boundary.journal.snapshot(source_fixture.RUN)
            else:value=actual()
            calls.append(len(self.fixture.reads));return value
        self.journey.witness=wrong_first;self.fixture.wait(kinds=('peer',))
        self.assertEqual(1,calls.count(0))
        self.assertEqual(1,self.journey.samples[0]['witness']['facts']['documentLoads'])
        self.assertEqual(0,self.journey.samples[0]['state']['documentLoads'])
        self.assertGreaterEqual(len(self.fixture.reads),4)
        self.assertGreaterEqual(self.journey.phases[-1]['advancingSamples'],3)

    def test_foreign_or_stale_journal_errors_are_not_pending_retries(self):
        for fault in ('foreign-witness','stale-sample'):
            self.setup_wait();self.boundary.fault=fault
            with self.subTest(fault=fault),self.assertRaises(ValueError):self.fixture.wait(kinds=('peer',))
            self.assertEqual(0 if fault=='foreign-witness' else 1,len(self.fixture.reads));self.assertEqual([],self.journey.phases)

    def test_peer_work_cannot_extend_original_checkpoint_or_trigger_a_second_product_query(self):
        self.setup_wait(first=1000);original=self.journey.witness
        def delayed():self.boundary.clock+=21;return original()
        self.journey.witness=delayed
        with self.assertRaisesRegex(AssertionError,'checkpoint deadline'):self.fixture.wait(kinds=('peer',))
        self.assertEqual([],self.fixture.reads);self.assertEqual([],self.fixture.sleeps)
        self.assertEqual([],self.journey.phases)

    def test_late_peer_is_acquired_before_product_source_without_manufacturing_its_timestamp(self):
        self.setup_wait(first=1.7)
        self.fixture.wait(kinds=('peer',))
        self.assertGreaterEqual(self.fixture.reads[0],1.7)
        self.assertTrue(all(sample['witness'] for sample in self.journey.samples))
        self.assertEqual(1,self.journey.samples[0]['sequence'])
        self.assertGreaterEqual(self.journey.phases[-1]['advancingSamples'],3)

    def test_retained_peer_cannot_be_refreshed_after_slow_product_work(self):
        self.setup_wait();invoke=self.journey.invoke;queries=[]
        def delayed(operation,fields):
            self.boundary.clock+=1.6;return invoke(operation,fields)
        original=self.journey.witness
        def witness():queries.append(True);return original()
        self.journey.invoke=delayed;self.journey.witness=witness
        with self.assertRaises(ValueError):self.fixture.wait(kinds=('peer',))
        self.assertEqual(1,len(self.fixture.reads));self.assertEqual(1,len(queries))
        self.assertEqual([],self.fixture.sleeps);self.assertEqual([],self.journey.phases)

    def test_preview_grants_no_cursor_progress_and_original_is_immutable_through_product_callback(self):
        self.setup_wait();invoke=self.journey.invoke;original=self.journey.witness;raw=[]
        def witness():
            value=original();raw.append(value);return value
        def product(operation,fields):
            if len(self.fixture.reads)==0:
                self.assertEqual((0,0,0),(self.journey.witness_sequence,self.journey.last_actor_sequence,self.journey.last_actor_epoch))
            # This provider-owned inspection object is no longer authority.
            if raw:raw[-1]['entries'].clear()
            return invoke(operation,fields)
        self.journey.witness=witness;self.journey.invoke=product
        self.fixture.wait(kinds=('peer',))
        self.assertTrue(all(sample['witness'] for sample in self.journey.samples))
        self.assertGreater(self.journey.witness_sequence,0)


if __name__=='__main__':unittest.main()
