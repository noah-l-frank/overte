"""Composed normal Script recipe, actual retained VM/page and original owners."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import unittest
from adapters.normal_feature_state import PrivateFeatureState
from feature_journeys.fixtures import context
from ios.adapters.world_web_identity import WorldWebLease
from ios.adapters.world_web_input import WorldWebInput
from ios.adapters.world_web_observer import WorldWebObserver
from ios.self_tests.world_web_whole_fixture import ComposedWorldWeb


class WorldWebWholeActiveTests(unittest.TestCase):
    def test_actual_normal_owned_setup_touch_echo_and_return_tree_vm_document_original_join(self):
        whole=ComposedWorldWeb();self.addCleanup(whole.close);scope,source,sdk=whole.scope,whole.source,whole.sdk
        before=source.capture('before-normal-setup');scope.prepare();scope.admit_rendered();after=source.capture('after-normal-setup')
        lease=WorldWebLease(scope,source,before,after);packet=lease.packet();self.assertEqual(whole.domain.marker['id'],packet['returned']['returned']['entityId'])
        inputs=WorldWebInput(PrivateFeatureState(scope.root/'ios-world-web-inputs.json'),source,sdk.ui(),packet['returned']['returned']['entityId'],lambda:True,
            epoch_ms=sdk.host_epoch,monotonic=lambda:sdk.time)
        observer=WorldWebObserver(PrivateFeatureState(scope.root/'ios-world-web-primary-observer.json'),source,sdk.origins,lambda:True,lease=lease)
        _,original=observer.capture();self.assertTrue(original['public']['state']['open']);self.assertEqual(0,original['public']['state']['bridgeMessages'])
        inputs.perform(sdk.ticket,'focus','tap','text');inputs.perform(sdk.ticket,'type','replace','text',text=context(sdk.run)['unicode'])
        inputs.perform(sdk.ticket,'submit','tap','bridge');_,observed=observer.capture()
        self.assertEqual([1,1,1],[observed['public']['state'][key] for key in ('attemptedMessages','bridgeMessages','bridgeEchoes')])
        self.assertFalse(whole.domain.vm['deleted']);scope.cleanup();closed=source.capture('closed')
        self.assertIsNone(source.frame(closed)['originals']['document']);self.assertIsNone(sdk.item_weak())


if __name__=='__main__':unittest.main()
