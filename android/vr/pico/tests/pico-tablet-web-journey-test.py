#!/usr/bin/env python3
"""Complete independent Pico stereo Journey; production/GPU sources are host seams."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT/'tests/device'))
if __name__=='__main__':
    suite=unittest.defaultTestLoader.loadTestsFromName('self_tests.test_pico_tablet_web_stereo_flow.PicoTabletWebStereoFlowTests.test_complete_shared_journey_keeps_independent_actor_and_original_two_eye_evidence')
    raise SystemExit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())
