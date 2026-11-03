"""Original capture3 binary returns; no native/device or whole-feature claim."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[5]/'tests/device'))

CASE_NAMES=(
    'self_tests.test_pico_emote_stream_capture.StreamWorldWireTests.test_actual_world_invalid_utf8_near_cap_and_nul_retained_before_decode',
    'self_tests.test_pico_emote_stream_capture.StreamWorldWireTests.test_actual_issued_world_wire_return_after_expiry_is_retained_without_new_query',
    'self_tests.test_pico_emote_stream_capture.StreamWorldWireTests.test_actual_world_partial_timeout_prefix_is_retained_and_never_retried',
)


def load_tests(loader,_tests,_pattern):return loader.loadTestsFromNames(CASE_NAMES)

if __name__=='__main__':unittest.main()
