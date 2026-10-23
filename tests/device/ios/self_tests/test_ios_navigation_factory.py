"""Existing Worlds factory and real original owners with declared native clocks."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from ios.adapters.navigation_configuration import settings
from ios.adapters.navigation_whole_feature import NavigationWholeFeature
from ios.self_tests import test_ios_navigation_whole_feature as fixture


class NavigationFactoryTests(unittest.TestCase):
    setUp=fixture.NavigationWholeFeatureTests.setUp

    def test_actual_factory_joins_existing_scope_baselines_and_normal_entry(self):
        h=self.h;original=h.flow;inputs=deepcopy(h.flow_fixture.b.inputs)
        whole=original.runtime._navigation_feature(original.selector,h.run,role='primary',client=original.client,
            settings=dict(artifactRoot=str(h.root)))
        self.assertIs(type(whole),NavigationWholeFeature);flow=whole.flow
        self.assertIs(flow.runtime,original.runtime);self.assertEqual(original.store.path,flow.store.path)
        self.assertEqual(inputs,h.flow_fixture.b.inputs);self.assertIsNone(flow.store.read())
        # Configure this newly constructed model consumer before its first
        # source/fixture acquisition. No retained original is rewritten.
        flow.lock=original.lock;flow.epoch_ms=h.now;flow.monotonic=h.mono;flow.sleep=h.sdk.gpu.sleep
        whole.lock=flow.lock
        flow.fixture.epoch_ms=lambda:int(h.now());flow.fixture.monotonic=h.mono
        flow.fixture.phase.epoch_ms=lambda:int(h.now());flow.fixture.phase.monotonic=h.mono
        h.flow=flow;whole.prepare()
        observed=whole.observe(dict(contractVersion=16,runId=h.run,afterSequence=0))
        self.assertEqual('A',observed['state']['location']);self.assertEqual(1,h.flow_fixture.b.inputs.count('PhoneAddressGoButton'))
        with flow.held():
            flow.load();owner=flow.initial_owner()
            self.assertEqual(h.binding,owner.archive()['binding'])

    def test_configuration_rejects_unowned_roots_and_requested_pixel_policy(self):
        valid=dict(artifactRoot=str(self.h.root));self.assertEqual(valid,settings(valid))
        for value in (dict(artifactRoot='relative'),valid|dict(imagePolicy={}),dict(artifactRoot=True)):
            with self.assertRaises((RuntimeError,ValueError,TypeError)):settings(value)


if __name__=='__main__':unittest.main()
