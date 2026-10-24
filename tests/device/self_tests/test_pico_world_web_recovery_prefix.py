"""Original normal World foreign-origin and HTTP recovery continuation."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from urllib.parse import urlsplit
import unittest

from adapters.normal_ui import NativeUIError
from feature_journeys.phase_fixture import PhasePending
from self_tests import test_pico_world_web_navigation_prefix as previous


class WorldWebRecoveryPrefixTests(unittest.TestCase):
    setUp=previous.WorldWebNavigationPrefixTests.setUp
    run=previous.WorldWebNavigationPrefixTests.run
    stop=previous.WorldWebNavigationPrefixTests.stop
    activate=previous.WorldWebNavigationPrefixTests.activate
    call=previous.WorldWebNavigationPrefixTests.call
    baseline=previous.WorldWebNavigationPrefixTests.baseline
    prefix=previous.WorldWebNavigationPrefixTests.prefix

    def test_continuous_thirteen_normal_steps_foreign_rejection_and_actual_404_restore_reload(self):
        samples=self.prefix(13)
        self.assertEqual('foreign',samples[6]['state']['origin'])
        self.assertEqual(2,samples[7]['state']['attemptedMessages'])
        self.assertEqual(1,samples[7]['state']['bridgeMessages']);self.assertEqual(1,samples[7]['state']['bridgeEchoes'])
        self.assertEqual('primary',samples[8]['state']['origin'])
        self.assertEqual([404,404,404,200],[row['state']['httpStatus'] for row in samples[9:13]])
        self.assertEqual(8,len(self.target.documents));self.assertIn(b'recovery available',self.target.assert_consumption)
        self.assertEqual(1,len([row for row in self.target.normal_inputs if row['controlId']=='scripts.url.submit']))
        self.assertEqual(urlsplit(self.foreign).netloc,urlsplit(self.target.foreign_editor).netloc)
        self.assertTrue(self.target.foreign_editor.endswith('/reference.html'))
        for role in (self.primary,self.actor):
            frame=role.history.last;self.assertEqual(14,len(role.history.rows))
            self.assertEqual(13,len(role.state['completed']));self.assertEqual([],frame['sample']['artifacts'])
            documents=frame['native']['source']['documents'];self.assertEqual(8,len(documents))
            ids=[packet['source']['dom']['document']['responseId'] for packet in frame['native']['source']['domHistory'].values()]
            receipts={row['responseId']:row for row in frame['browser']['responses']}
            self.assertEqual(8,len(set(ids)));self.assertTrue(set(ids)<=set(receipts))
            self.assertEqual(1,len([receipts[key] for key in ids if receipts[key]['origin']=='foreign']))
            self.assertEqual(2,len([receipts[key] for key in ids if receipts[key]['status']==404]))

    def test_lost_applied_foreign_navigation_keeps_original_and_cold_cannot_resend(self):
        self.prefix(6);call=self.call(6);self.target.lost_controls.add('navigate')
        with self.assertRaises(NativeUIError):self.primary.act(call)
        self.assertEqual(urlsplit(self.foreign).netloc,urlsplit(self.target.current['url']).netloc)
        original=self.primary.store.path.read_bytes();commands=deepcopy(self.target.transport.envelopes)
        cold=self.facade.prefix(self.target.selector,self.primary.source,self.foreign)
        with self.assertRaises(NativeUIError):cold.act(call)
        with self.assertRaises(PhasePending):cold.observe()
        self.assertEqual(original,self.primary.store.path.read_bytes());self.assertEqual(commands,self.target.transport.envelopes)
        self.assertEqual(4,len(self.target.documents));self.assertEqual('acting',cold.state['phase'])

    def test_fixture_restore_does_not_relabel_old_404_before_actual_reload(self):
        self.prefix(12)
        self.assertTrue(self.server.browser_resources.snapshot(self.run)['ready'])
        self.assertEqual(404,self.target.current['status'])
        commands=deepcopy(self.target.transport.envelopes);documents=deepcopy(self.target.documents)
        cold=self.facade.prefix(self.target.selector,self.primary.source,self.foreign)
        actual=cold.observe();self.assertEqual(404,actual['state']['httpStatus'])
        self.assertEqual(commands,self.target.transport.envelopes);self.assertEqual(documents,self.target.documents)
        self.assertEqual(12,len(cold.state['completed']))


if __name__=='__main__':unittest.main()
