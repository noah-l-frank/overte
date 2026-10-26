"""Actual complete shared Emote scenario; device/native execution is untested."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import unittest
import secrets
from feature_journeys.scenarios import SCENARIOS,expand
from feature_journeys.fixtures import context
from ios.self_tests.emote_common_journey_fixture import CommonEmoteJourneyFixture


class CommonEmoteJourneyTests(unittest.TestCase):
    def test_all_ordinary_common_steps_and_typed_paired_end(self):
        f=CommonEmoteJourneyFixture(self,retain_originals=True)
        f.journey.execute()
        self.assertTrue(f.report['sequenceCompleted']);self.assertTrue(f.report['cleanupSucceeded'])
        self.assertEqual(28,len(SCENARIOS['emotes']['steps']))
        self.assertEqual({'Sit1','Sit2','Sit3'},f.journey.sit_variants)
        self.assertEqual(['lifecycle.background','app.launch'],f.end.lifecycle_inputs)
        self.assertEqual(['actor','primary'],f.end.stops);self.assertEqual({'actor','primary'},f.end.deleted)
        self.assertIsNotNone(f.journey.terminal_end)
        self.assertFalse(f.report['deviceAcceptance'])


class CommonEmoteStartTests(unittest.TestCase):
    def test_original_baseline_open_and_first_common_play_checkpoint(self):
        f=CommonEmoteJourneyFixture(self,retain_originals=True);journey=f.journey
        ticket=secrets.token_hex(16);f.activate(ticket);barrier=f.primary.epoch_ms()
        journey.wait('owned-clean-baseline',ticket,barrier,SCENARIOS['emotes']['baseline'],['peer'])
        for index,step in enumerate(SCENARIOS['emotes']['steps'][:2]):
            ticket=secrets.token_hex(16);inputs=expand(step['inputs'],context(f.primary.run))
            f.activate(ticket,step['verb'],inputs);barrier=f.primary.epoch_ms()
            journey.required_lifecycle=journey.lifecycle.copy()
            journey.call('act',dict(verb=step['verb'],inputs=inputs,ticket=ticket,fixtureUrl=journey.url))
            journey.wait(str(index+1)+'-'+step['verb'],ticket,barrier,
                expand(step['state'],context(f.primary.run)),step['evidence'])
        self.assertEqual('Crying',journey.samples[-1]['state']['animation'])


if __name__=='__main__':unittest.main()
