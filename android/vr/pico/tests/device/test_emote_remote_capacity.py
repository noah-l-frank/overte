"""Disjoint no-build remote Emote component checks; native edges are models."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[5]/'tests/device'))

CASE_NAMES=(
    'self_tests.test_pico_emote_capture.PicoEmoteRemoteCaptureTests.test_actual_remaining_source_slots_are_not_reset_for_a_new_capture_index',
)

def load_tests(loader,_tests,_pattern):
    return loader.loadTestsFromNames(CASE_NAMES)

if __name__=='__main__':unittest.main()
