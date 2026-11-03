"""Original capture3 callback and owner identity; no native/device or whole-feature claim."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[5]/'tests/device'))

CASE_NAMES=(
    'self_tests.test_pico_emote_stream_capture.StreamRawIdentityTests.test_model_raw_callback_and_clock_replacement_refuse_before_send',
    'self_tests.test_pico_emote_stream_capture.StreamRawIdentityTests.test_world_raw_saved_getter_and_mutable_catalog_replacement_refuse_before_send',
    'self_tests.test_pico_emote_stream_capture.StreamRawIdentityTests.test_actual_owner_stays_strong_after_unknown_intent_and_traceback_loss',
)


def load_tests(loader,_tests,_pattern):return loader.loadTestsFromNames(CASE_NAMES)

if __name__=='__main__':unittest.main()
