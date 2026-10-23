"""Partial cleanup preserves its original budget and actual input ownership."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
import uuid
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import unpack
from ios.adapters.navigation_feature import NavigationFeaturePending
from ios.adapters.navigation_whole_feature import NavigationWholeFeature
from ios.self_tests import test_ios_navigation_whole_feature as fixture


class NavigationWholeCleanupClockTests(unittest.TestCase):
    setUp=fixture.NavigationWholeFeatureTests.setUp

    def cleanup_call(self):
        h=self.h;h.harness.client.activate(uuid.uuid4().hex,'cleanup',{})
        return dict(contractVersion=16,runId=h.run)

    def test_original_failed_cleanup_clock_survives_reconstruction_without_an_input(self):
        self.whole.prepare();h=self.h;call=self.cleanup_call()
        # This fixture has not acquired either observer's original image.
        # Its real restoration reader must reject incomplete evidence. That
        # failure cannot renew the already retained ordinary-cleanup clock.
        with self.assertRaises(NativeUIError):self.whole.cleanup(call)
        state=unpack(self.whole.store.read()['payload'])[0];started=deepcopy(state['cleanup']['started'])
        commands=deepcopy(h.flow_fixture.b.inputs);h.sdk.gpu.sleep(31)
        with self.assertRaises(NativeUIError) as caught:NavigationWholeFeature(h.flow).cleanup(call)
        self.assertNotIsInstance(caught.exception,NavigationFeaturePending)
        self.assertEqual(commands,h.flow_fixture.b.inputs)
        self.assertEqual(started,unpack(self.whole.store.read()['payload'])[0]['cleanup']['started'])
        self.assertIsNone(h.flow.operation_clock)

    def test_slow_durable_cleanup_intent_cannot_renew_the_original_budget(self):
        self.whole.prepare();h=self.h;call=self.cleanup_call();write=self.whole.store.write
        commands=deepcopy(h.flow_fixture.b.inputs)
        def slow(value,previous):
            write(value,previous)
            if unpack(value['payload'])[0]['phase']=='cleaning':h.sdk.gpu.sleep(31)
        with patch.object(self.whole.store,'write',side_effect=slow),self.assertRaises(NativeUIError) as caught:self.whole.cleanup(call)
        self.assertNotIsInstance(caught.exception,NavigationFeaturePending)
        self.assertEqual(commands,h.flow_fixture.b.inputs)
        self.assertEqual('cleaning',unpack(self.whole.store.read()['payload'])[0]['phase'])
        self.assertIsNone(h.flow.operation_clock)


if __name__=='__main__':unittest.main()
