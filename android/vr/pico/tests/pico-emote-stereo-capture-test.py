#!/usr/bin/env python3
"Original Pico stereo model/pixel/capture and normal View-menu checks."
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import sys
import unittest
ROOT = Path(__file__).resolve().parents[4]
sys.path[:0] = [str(ROOT / "tests/device"), str(ROOT / "tests/device/self_tests")]
suite = unittest.defaultTestLoader.loadTestsFromNames(['self_tests.test_native_avatar_render', 'self_tests.test_pico_emote_model_draws', 'self_tests.test_pico_emote_pixels', 'self_tests.test_pico_emote_capture', 'self_tests.test_pico_view_menu', 'self_tests.test_pico_emote_view'])
if __name__ == "__main__":
    raise SystemExit(0 if unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful() else 1)
