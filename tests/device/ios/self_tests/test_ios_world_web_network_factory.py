"""Register the real run before the first original; no old packet relabeling."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import unittest

from ios.self_tests.world_web_network_fixture import NetworkWorldWeb


class WorldWebNetworkFactoryTests(unittest.TestCase):
    def test_actual_authority_run_exists_before_first_native_source_original(self):
        network=NetworkWorldWeb();self.addCleanup(network.close);whole=network.whole
        reference=whole.source.capture('network-initial')
        frame=whole.source.frame(reference)
        self.assertEqual(network.run,frame['phaseBefore']['runId'])
        self.assertEqual(network.ticket,frame['phaseBefore']['activations'][0]['ticket'])
        self.assertEqual(network.fixture_url,frame['originals']['ledgerAfter']['fixtureUrl'])
        self.assertEqual(network.run,whole.scope.originals.run)
        self.assertEqual('baseline',frame['phaseBefore']['activations'][-1]['stimulus']['verb'])
        self.assertEqual([],frame['originals']['ledgerAfter']['events'])
        self.assertEqual([],network.server.journal.snapshot(network.run)['entries'])


if __name__=='__main__':unittest.main()
