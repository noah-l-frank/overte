"""Explicit Source4 wire cases; no compiled/native/device or whole-feature claim."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[5]/'tests/device'))

CASE_NAMES=(
    'self_tests.test_pico_emote_stream_wire.StreamWireTests.test_actual_near_cap_incompressible_nul_literal_is_retained_before_utf8_or_json',
    'self_tests.test_pico_emote_stream_wire.StreamWireTests.test_actual_overcap_prefix_stays_original_and_incomplete_without_parser',
    'self_tests.test_pico_emote_stream_wire.StreamWireTests.test_actual_partial_timeout_bytes_are_retained_before_terminal_refusal',
    'self_tests.test_pico_emote_stream_wire.StreamWireTests.test_already_issued_wire_survives_business_guard_loss_then_zero_new_getter',
    'self_tests.test_pico_emote_stream_wire.StreamWireTests.test_capacity_refusal_emits_zero_actual_control_send',
    'self_tests.test_pico_emote_stream_wire.StreamWireTests.test_capacity_refusal_emits_zero_actual_getter',
    'self_tests.test_pico_emote_stream_wire.StreamWireTests.test_control_guarantees_both_ack_and_real_send_return_before_dispatch',
    'self_tests.test_pico_emote_stream_wire.StreamWireTests.test_duplicate_json_keys_are_retained_then_refused',
    'self_tests.test_pico_emote_stream_wire.StreamWireTests.test_fixed_actual_script_retains_wire_before_parser_and_never_sends_for_sample',
    'self_tests.test_pico_emote_stream_wire.StreamWireTests.test_last_native_callback_delay_sends_zero_with_both_issued_reservations',
    'self_tests.test_pico_emote_stream_wire.StreamWireTests.test_legacy_same_arena_file_prevents_source4_acceptance',
    'self_tests.test_pico_emote_stream_wire.StreamWireTests.test_native_issued_write_marker_prevents_current_sample_acceptance',
)


def load_tests(loader,_tests,_pattern):return loader.loadTestsFromNames(CASE_NAMES)

if __name__=='__main__':unittest.main()
