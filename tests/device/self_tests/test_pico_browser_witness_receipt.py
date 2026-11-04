"""Historical receipt entries versus the current independent browser original."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from feature_journeys.witness import projection
from self_tests import test_pico_browser_poll_period as fixture_module
from self_tests import test_feature_journeys as source_fixture


class BrowserWitnessReceiptTests(unittest.TestCase):
    def setup_wait(self,*,old_bad=False):
        self.fixture=fixture_module.BrowserPollPeriodTests();self.fixture.setup_wait(work=.6)
        self.boundary=self.fixture.boundary;self.journey=self.fixture.journey
        b=self.boundary;peer=deepcopy(b.state)
        if old_bad:peer['documentLoads']=1
        b.actor_sequence+=1
        b.journal.publish(source_fixture.RUN,dict(ticket=source_fixture.TICKET,actor='owned-observer',
            actorSequence=b.actor_sequence,capturedEpochMs=b.epoch(),facts=projection('tablet-web',peer)))
        b.clock=1.;first=b.witness();self.first=deepcopy(first);original=self.journey.witness;calls=[]
        def witness():
            calls.append(True)
            return first if len(calls)==1 else original()
        self.journey.witness=witness

    def test_old_entries_remain_history_while_only_latest_fresh_original_qualifies_current_pair(self):
        self.setup_wait();self.fixture.wait(kinds=('peer',))
        self.assertEqual(3,len(self.fixture.reads));first=self.journey.samples[0]
        self.assertEqual(2,first['witness']['actorSequence'])
        self.assertGreater(first['capturedEpochMs']-self.first['entries'][0]['capturedEpochMs'],1500)
        self.assertLess(first['capturedEpochMs']-first['witness']['capturedEpochMs'],1500)
        self.assertEqual(2_000_000,self.first['entries'][0]['capturedEpochMs'])
        self.assertGreaterEqual(self.journey.phases[-1]['advancingSamples'],3)

    def test_historical_contradiction_is_not_dropped_when_latest_peer_agrees(self):
        self.setup_wait(old_bad=True);self.fixture.wait(kinds=('peer',))
        self.assertGreaterEqual(len(self.fixture.reads),4)
        self.assertEqual(0,self.journey.samples[0]['witness']['facts']['documentLoads'])
        self.assertEqual(1,self.first['entries'][0]['facts']['documentLoads'])
        self.assertEqual(3,self.journey.phases[-1]['advancingSamples'])

    def test_stale_at_receipt_is_refused_before_any_product_source(self):
        self.setup_wait();self.boundary.clock=2.
        with self.assertRaises(ValueError):self.fixture.wait(kinds=('peer',))
        self.assertEqual([],self.fixture.reads);self.assertEqual([],self.journey.phases)

    def test_cursor_mutation_during_product_callback_cannot_adopt_the_preview(self):
        self.setup_wait();original=self.journey.invoke
        def changed(operation,fields):
            result=original(operation,fields);self.journey.witness_sequence+=1;return result
        self.journey.invoke=changed
        with self.assertRaisesRegex(ValueError,'cursor changed'):self.fixture.wait(kinds=('peer',))
        self.assertEqual(1,len(self.fixture.reads));self.assertEqual([],self.journey.phases)


if __name__=='__main__':unittest.main()
