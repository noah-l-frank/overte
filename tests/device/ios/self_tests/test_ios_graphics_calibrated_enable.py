"""Same-phase calibration cannot replace mandatory current effect pixel proof."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import unittest
from unittest.mock import patch

from adapters.normal_ui import NativeUIError
from ios.adapters.graphics_current_effects import compare
from ios.adapters.graphics_world_effects import GraphicsWorldEffectPending
from ios.self_tests.test_ios_graphics_calibration import CalibrationHarness


class CalibratedEnableTests(CalibrationHarness,unittest.TestCase):
    def calibrated_enable(self):
        self.prepare();self.observer().read(0,0);self.action('open')
        self.action('set-haze',dict(enabled=True));self.action('set-mirrors',dict(enabled=True))
        calibration,_observer=self.calibration();calibration.begin(0);calibration.advance_primary();self.captures()
        calibration,_observer=self.calibration();calibration.advance_primary();return self.observer()

    def test_same_phase_private_calibration_uses_both_disjoint_original_pixel_proofs(self):
        with self.lock.held():
            observer=self.calibrated_enable();value=observer.read(0,0)
            self.assertTrue(value['state']['haze']);self.assertTrue(value['state']['mirror'])
            rows=[row for row in observer.state['currentEffects'] if row['after']==observer.state['last']]
            self.assertEqual({'haze','mirror'},{row['feature'] for row in rows})
            self.assertTrue(all(row['observed']['changedFraction']>=.05 for row in rows))
            self.assertFalse(observer.state['effects'])
            self.assertTrue(all(observer.frame(row['before'],observer.state['binding'])[0]['provider']['ticket']==
                observer.frame(row['after'],observer.state['binding'])[0]['provider']['ticket'] for row in rows))

    def test_current_native_settings_and_draws_without_effect_pixels_still_fail_after_private_calibration(self):
        with self.lock.held():
            observer=self.calibrated_enable();sequence=observer.state['sequence'];self.gpu.effects=False;rejected=[]
            def measured(*args,**kwargs):
                try:return compare(*args,**kwargs)
                except GraphicsWorldEffectPending as error:rejected.append(error.observation);raise
            # One original failed-pixel acquisition followed by expiration is
            # sufficient; no dozens of equivalent synthetic renders are needed.
            observer.sleep=lambda _seconds:self.sdk.sleep(20)
            with patch('ios.adapters.graphics_observer.compare_current',side_effect=measured),self.assertRaises(NativeUIError):observer.read(0,0)
            self.assertEqual(sequence,observer.state['sequence']);self.assertEqual('reading',observer.state['phase'])
            self.assertEqual(1,len(rejected));self.assertEqual(0,rejected[0]['changedFraction'])
            self.assertTrue(self.sdk.model.haze);self.assertTrue(self.sdk.model.mirrors)
            self.assertFalse(observer.state['currentEffects'])


if __name__=='__main__':unittest.main()
