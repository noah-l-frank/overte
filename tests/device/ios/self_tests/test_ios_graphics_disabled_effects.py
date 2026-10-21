"""Current disabled pixels must not retain an earlier enabled effect signature."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from adapters.normal_ui import NativeUIError
from ios.adapters.graphics_current_effects import compare_disabled
from ios.adapters.graphics_world_effects import GraphicsWorldEffectPending
from ios.self_tests.test_ios_graphics_current_effects import CurrentEffectsHarness,CurrentRestartHarness
from ios.self_tests.test_ios_graphics_observer import CurrentObserverHarness
from ios.self_tests.test_ios_graphics_samples import POLICY,raster as render_original
from ios.self_tests.test_ios_graphics_scene import RUN


class DisabledHarness(CurrentEffectsHarness):
    def qualify_disabled(self,feature,pair):
        (old,before,a),(binding,current,b)=pair
        return compare_disabled(RUN,feature,self.client.url+'/runs/'+RUN+'/',old,before,a,binding,current,b,POLICY,
            self.client.graphics_instance,lambda:round(self.sdk.host_epoch()),lambda:True,monotonic=lambda:self.sdk.clock)
    def disabled_pair(self,feature,*,other=False,resolution=False):
        before,_enabled=self.setup_pair(feature,other=other,resolution=resolution)
        self.action('set-haze' if feature=='haze' else 'set-mirrors',dict(enabled=False))
        return before,self.grab()
    def stuck_pixels(self,feature):
        def stuck(ticket,*,sdk=None,effects=True):
            if sdk is not None:
                sdk=SimpleNamespace(model=SimpleNamespace(haze=True if feature=='haze' else sdk.model.haze,
                    mirrors=True if feature=='mirror' else sdk.model.mirrors),scene_rows=sdk.scene_rows)
            return render_original(ticket,sdk=sdk,effects=effects)
        return patch('ios.self_tests.test_ios_graphics_samples.raster',side_effect=stuck)


class DisabledEffectsTests(DisabledHarness,unittest.TestCase):
    def test_actual_haze_removal_matches_the_original_off_signature(self):
        with self.lock.held():
            pair=self.disabled_pair('haze');stats=self.qualify_disabled('haze',pair)
            self.assertEqual(1,stats['iosGraphicsDisabledEffectsVersion'])
            self.assertLessEqual(stats['blueDominanceAfter']-stats['blueDominanceBefore'],10)
            self.assertNotEqual(pair[0][1]['capture']['requestId'],pair[1][1]['capture']['requestId'])

    def test_actual_reflection_removal_allows_resolution_and_other_effect_changes(self):
        with self.lock.held():
            stats=self.qualify_disabled('mirror',self.disabled_pair('mirror',other=True,resolution=True))
            self.assertLessEqual(stats['orangeFractionAfter']-stats['orangeFractionBefore'],.005)

    def assert_stuck(self,feature):
        with self.lock.held():
            before,_current=self.disabled_pair(feature)
            with self.stuck_pixels(feature):current=self.grab()
            self.assertFalse(current[1]['nativeAfter']['graphics']['hazeSetting' if feature=='haze' else 'mirrorsSetting'])
            with self.assertRaises(GraphicsWorldEffectPending):self.qualify_disabled(feature,(before,current))

    def test_disabled_native_haze_and_no_issued_haze_draws_cannot_hide_stale_haze_pixels(self):self.assert_stuck('haze')
    def test_disabled_native_mirrors_and_no_issued_mirror_draws_cannot_hide_stale_reflection_pixels(self):self.assert_stuck('mirror')

    def test_reused_current_image_and_expired_off_reference_cannot_prove_disabled_state(self):
        with self.lock.held():
            before,current=self.disabled_pair('haze')
            with self.assertRaises(NativeUIError):self.qualify_disabled('haze',(before,before))
            saved=deepcopy(before);self.sdk.sleep(46);current=self.grab()
            with self.assertRaises(NativeUIError):self.qualify_disabled('haze',(before,current))
            self.assertEqual(saved,before)


class DisabledObserverTests(CurrentObserverHarness,unittest.TestCase):
    def test_false_initial_baseline_uses_private_role_originals_and_retains_disabled_pixel_proofs(self):
        with self.lock.held():
            self.prepare();observer=self.observer();self.assertEqual(0,observer.state['sequence'])
            observer.read(0,0);self.assertEqual({'haze','mirror'},{r['feature'] for r in observer.state['disabledEffects']})
            self.assertTrue(all(r['before']['requestId']!=r['after']['requestId'] for r in observer.state['disabledEffects']))
            self.assertNotEqual(self.observer('actor').state['offFrames'],observer.state['offFrames'])

    def test_restored_false_preferences_cannot_succeed_with_current_enabled_pixels(self):
        with self.lock.held():
            self.prepare();self.observer().read(0,0);self.action('open');self.action('set-haze',dict(enabled=True))
            self.observer().read(0,0);self.action('restore-original');self.assertFalse(self.sdk.model.haze)
            def stuck(ticket,*,sdk=None,effects=True):
                if sdk is not None:sdk=SimpleNamespace(model=SimpleNamespace(haze=True,mirrors=sdk.model.mirrors),scene_rows=sdk.scene_rows)
                return render_original(ticket,sdk=sdk,effects=effects)
            with patch('ios.self_tests.test_ios_graphics_samples.raster',side_effect=stuck),self.assertRaises(NativeUIError):self.observer().read(0,0)
            observer=self.observer();self.assertEqual('reading',observer.state['phase']);self.assertEqual(2,observer.state['sequence'])
            self.assertTrue(observer.frame(observer.state['last'],observer.state['binding'])[2]['state']['haze'])


class DisabledRestartTests(CurrentRestartHarness,unittest.TestCase):
    def test_current_off_pixels_cross_only_the_original_strict_restart_receipt(self):
        with self.lock.held():
            before,_current,receipt=self.restarted_pair();self.action('set-haze',dict(enabled=False));self.action('set-mirrors',dict(enabled=False))
            current=self.grab(1,'8'*32);(old,a,raw_a),(binding,b,raw_b)=before,current
            args=(RUN,'haze',self.client.url+'/runs/'+RUN+'/',old,a,raw_a,binding,b,raw_b,POLICY,
                self.client.graphics_instance,lambda:round(self.sdk.host_epoch()),lambda:True)
            with self.assertRaises(NativeUIError):compare_disabled(*args,monotonic=lambda:self.sdk.clock)
            stats=compare_disabled(*args,restart=receipt,monotonic=lambda:self.sdk.clock)
            self.assertIsNotNone(stats['restartSha256']);self.assertEqual(['app.stop','app.launch'],self.inputs)


if __name__=='__main__':unittest.main()
