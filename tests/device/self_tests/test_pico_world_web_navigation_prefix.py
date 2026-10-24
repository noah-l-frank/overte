"""Continuous first six normal World steps; no image or whole-feature claim."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest

from adapters.normal_ui import NativeUIError
from adapters.pico4.world_web_prefix import PicoWorldWebPrefix
from feature_journeys.engine import matches
from feature_journeys.fixtures import context
from feature_journeys.phase_fixture import PhasePending
from feature_journeys.scenarios import SCENARIOS,expand
from self_tests import test_pico_world_web_prefix as original_prefix


class WorldWebNavigationPrefixTests(unittest.TestCase):
    # Reuse the exact normal actuator and independent original producers. Do
    # not inherit/discover the first packet's cases in another selector.
    setUp=original_prefix.WorldWebPrefixTests.setUp
    run=original_prefix.WorldWebPrefixTests.run
    stop=original_prefix.WorldWebPrefixTests.stop
    activate=original_prefix.WorldWebPrefixTests.activate
    call=original_prefix.WorldWebPrefixTests.call
    baseline=original_prefix.WorldWebPrefixTests.baseline

    def prefix(self,count):
        self.baseline();samples=[]
        for index in range(count):
            call=self.call(index);self.primary.act(call)
            sample=self.primary.observe();actor=self.actor.observe()
            self.assertEqual(sample['state'],actor['state'])
            self.assertTrue(matches(sample['state'],expand(SCENARIOS['world-web']['steps'][index]['state'],context(self.run))))
            samples.append(sample)
        return samples

    def test_normal_unicode_send_clear_then_actual_second_document_and_history_back(self):
        samples=self.prefix(6)
        self.assertEqual(['reference','reference','reference','reference','B','reference'],[row['state']['page'] for row in samples])
        root=self.primary.state['scriptUrl'].rsplit('/',1)[0]+'/'
        self.assertEqual([root+'index.html',root+'page-b.html',root+'index.html'],[row['url'] for row in self.target.documents])
        self.assertEqual(3,len({row['page'] for row in self.target.documents}))
        self.assertEqual(7,len(self.target.transport.envelopes))
        self.assertEqual(1,len([row for row in self.target.normal_inputs if row['controlId']=='scripts.url.submit']))
        for role in (self.primary,self.actor):
            self.assertEqual(7,len(role.history.rows));self.assertEqual(6,len(role.state['completed']))
            current=role.history.last['native']['source']['current']
            self.assertEqual(root+'index.html',current['source']['nativeView']['url'])
            self.assertEqual('',current['source']['dom']['editor']['text'])
            self.assertEqual(3,len(role.history.last['native']['source']['documents']))
            self.assertEqual([],role.history.last['sample']['artifacts'])
        ime=[row['original']['command']['text'] for row in self.primary.state['inputs'] if row['original'].get('operation')=='world-browser-ime']
        self.assertEqual([expand('$unicode',context(self.run)),''],ime)
        self.assertEqual(1,len(self.target.requests));self.assertEqual(1,len(self.target.replies))

    def test_lost_applied_second_document_ray_preserves_originals_and_never_replays_cold(self):
        self.prefix(4);call=self.call(4);self.target.lost_controls.add('second')
        with self.assertRaises(NativeUIError):self.primary.act(call)
        self.assertTrue(self.target.current['url'].endswith('/page-b.html'))
        commands=deepcopy(self.target.transport.envelopes);inputs=deepcopy(self.target.normal_inputs)
        documents=deepcopy(self.target.documents);original=self.primary.store.path.read_bytes()
        cold=self.facade.prefix(self.target.selector,self.primary.source,self.foreign)
        with self.assertRaises(NativeUIError):cold.act(call)
        with self.assertRaises(PhasePending):cold.observe()
        self.assertEqual(commands,self.target.transport.envelopes);self.assertEqual(inputs,self.target.normal_inputs)
        self.assertEqual(documents,self.target.documents);self.assertEqual(original,self.primary.store.path.read_bytes())

    def test_ignored_clear_ime_cannot_become_empty_text_or_retry_after_ack(self):
        self.prefix(3);call=self.call(3);self.target.ignore_ime=True
        before=self.target.current['text'];self.assertTrue(before)
        with self.assertRaises(NativeUIError):self.primary.act(call)
        self.assertEqual(before,self.target.current['text']);commands=deepcopy(self.target.transport.envelopes)
        cold=self.facade.prefix(self.target.selector,self.primary.source,self.foreign)
        with self.assertRaises(NativeUIError):cold.act(call)
        self.assertEqual(commands,self.target.transport.envelopes)
        self.assertEqual('acting',self.primary.state['phase'])

    def test_ignored_second_hit_ack_does_not_manufacture_document_or_common_state(self):
        self.prefix(4);call=self.call(4);self.target.ignored_controls.add('second')
        self.primary.act(call);actual=self.primary.observe();actor=self.actor.observe()
        self.assertEqual(actual['state'],actor['state']);self.assertEqual('reference',actual['state']['page'])
        self.assertEqual(1,actual['state']['documentLoads'])
        self.assertFalse(matches(actual['state'],SCENARIOS['world-web']['steps'][4]['state']))
        self.assertEqual(1,len(self.target.documents))

    def test_v1_owner_grammar_still_reads_first_three_and_cannot_admit_new_fourth_step(self):
        self.prefix(3);self.primary.validate(deepcopy(self.primary.state),version=1)
        self.primary.act(self.call(3));sample=self.primary.observe()
        with self.assertRaises(NativeUIError):self.primary.validate(deepcopy(self.primary.state),version=1)
        self.primary.validate(deepcopy(self.primary.state),version=2)
        cold=self.facade.prefix(self.target.selector,self.primary.source,self.foreign)
        actual=cold.observe();self.assertEqual(sample['state'],actual['state'])
        self.assertEqual(4,len(cold.state['completed']))


if __name__=='__main__':unittest.main()
