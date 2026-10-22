"""Same genuine modeled SDK before input and after normal restart/restoration."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import unittest
import uuid

from adapters.normal_ui import NativeUIError
from ios.adapters.navigation_static_comparison import compare
from ios.self_tests.navigation_baseline_image_fixture import Baseline
from ios.self_tests.navigation_feature_restart_fixture import RestartWorld
from ios.self_tests import test_ios_navigation_restored_image as image


class NavigationStaticComparisonTests(image.NavigationRestoredImageTests):
    # Keep only this composed case; the inherited image case would repeat the
    # same expensive actual normal sequence without adding a new boundary.
    test_current_static_render_replays_without_sdk_and_keeps_all_root_lifetimes_explicit=None

    def setUp(self):
        self.h=RestartWorld(self);h=self.h;raster=h.gpu.raster
        self.baseline_fixture=Baseline(self,world=h)
        with h.flow.held():
            self.initial_image=self.baseline_fixture.owner();self.initial_image.acquire(h.now())
        h.gpu.raster=raster;h.flow.prepare();h.flow.observe_active(0)

    def test_original_full_target_matches_only_after_actual_process_transfer_and_static_restoration(self):
        call=self.acquire();h=self.h;request='ios-'+uuid.uuid4().hex
        with h.flow.held():
            current=self.owner(call,request);current.acquire(h.now())
            initial=self.baseline_fixture.owner(historical=True)
            result=compare(initial,current,h.flow.initial_owner(),h.flow.transferred_owner())
            self.assertEqual(0,result['changedPixels']);self.assertEqual(0,result['meanChannelDelta'])
            self.assertEqual(h.run,result['runId']);self.assertEqual('primary',result['role'])
            old=initial.originals()['capture'];new=current.originals()['capture']
            self.assertNotEqual(old['instance'],new['instance']);self.assertEqual(42,old['processId']);self.assertEqual(43,new['processId'])
            with self.assertRaises(NativeUIError):compare(current,current,h.flow.initial_owner(),h.flow.transferred_owner())


if __name__=='__main__':unittest.main()
