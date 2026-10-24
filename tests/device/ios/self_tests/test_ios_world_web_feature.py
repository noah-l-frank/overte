"""Actual feature/factory assembly; SDK/Qt/GPU/OS use declared model clocks."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import unittest
from adapters.normal_ui import NativeUIError
from ios.self_tests.world_web_feature_fixture import FeatureWorldWeb


class WorldWebFeatureTests(unittest.TestCase):
    def test_actual_factory_baseline_normal_script_open_and_independent_dual_sdk_admission(self):
        fixture=FeatureWorldWeb();self.addCleanup(fixture.close)
        call=dict(contractVersion=16,runId=fixture.network.run,afterSequence=0)
        primary=fixture.primary.observe(call);actor=fixture.secondary.observe(call)
        self.assertFalse(primary['state']['open']);self.assertFalse(actor['state']['open'])
        active=fixture.sdk.activate('open',{});self.assertEqual(dict(performed=True),fixture.primary.act(active))
        after=fixture.primary.observe(dict(call,afterSequence=primary['sequence']))
        independent=fixture.secondary.observe(dict(call,afterSequence=actor['sequence']))
        self.assertTrue(after['state']['open']);self.assertTrue(independent['state']['open'])
        self.assertNotEqual(fixture.primary.state['binding'],fixture.secondary.state['binding'])
        self.assertEqual(fixture.primary.state['binding'],fixture.secondary.state['primaryBinding'])
        with fixture.primary.held():
            own=fixture.primary.parts();frame=own['source'].frame(own['source'].state['records'][-1])
            roots=frame['originals']['widgets']['scriptInventory']['rootOwnership']['roots']
            self.assertEqual({'manager','picker'},{root['kind'] for root in roots})
            self.assertTrue(all(root['weakAlive'] for root in roots))
            self.assertTrue(all(root['observedIdentity'] for root in roots))
        # The actual marker is local to Primary. Actor's own world inventory
        # never supplies a fictional replicated Primary Entity/renderer.
        with fixture.secondary.held():
            own=fixture.secondary.parts()
            self.assertEqual(fixture.primary.state['binding'],own['source'].binding)
            self.assertEqual(fixture.secondary.state['binding'],own['peer'].binding)
            peer=own['peer'].frame(own['peer'].state['records'][-1])
            self.assertEqual([],peer['originals']['geometry']['source']['entities'])


if __name__=='__main__':unittest.main()
