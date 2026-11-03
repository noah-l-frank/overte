"""Original capture3 fences; no native/device or whole-feature claim."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[5]/'tests/device'))

CASE_NAMES=(
    'self_tests.test_pico_emote_stream_capture.StreamCaptureFenceTests.test_equal_bytes_memory_graph_replacement_refuses_before_new_source_or_gpu',
    'self_tests.test_pico_emote_stream_capture.StreamCaptureFenceTests.test_mutated_component_clock_cannot_be_admitted_by_remember',
    'self_tests.test_pico_emote_stream_capture.StreamCaptureFenceTests.test_factory_replacement_refuses_before_any_source_or_gpu',
    'self_tests.test_pico_emote_stream_capture.StreamCaptureFenceTests.test_actual_completed_intent_cas_lost_ack_is_sticky_and_sends_zero_gpu',
    'self_tests.test_pico_emote_stream_capture.StreamCaptureFenceTests.test_original_five_second_expiry_before_complete_sends_zero_new_queries',
    'self_tests.test_pico_emote_stream_capture.StreamCaptureFenceTests.test_actual_near_cap_noise_and_nul_model_wire_retained_before_parser',
)


def load_tests(loader,_tests,_pattern):return loader.loadTestsFromNames(CASE_NAMES)

if __name__=='__main__':unittest.main()
