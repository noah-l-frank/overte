"""Explicit capacity component cases; no Native/device/whole claim."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[5]/'tests/device'))

CASE_NAMES=(
    'self_tests.test_pico_emote_stream_capacity.StreamCapacityTests.test_fixed_native_file_slots_and_receipts_charge_the_one_actual_aggregate',
    'self_tests.test_pico_emote_stream_capacity.StreamCapacityTests.test_selection_after_original_source_acquisition_refuses_without_new_source',
    'self_tests.test_pico_emote_stream_capacity.StreamCapacityTests.test_callback_or_equal_bytes_graph_replacement_refuses_before_native_io',
    'self_tests.test_pico_emote_stream_capacity.StreamCapacityTests.test_equal_bytes_state_graph_replacement_cannot_be_resealed',
    'self_tests.test_pico_emote_stream_capacity.StreamCapacityTests.test_actual_completed_capacity_cas_lost_reply_retains_original_owner_and_zero_send',
    'self_tests.test_pico_emote_stream_capacity.StreamCapacityTests.test_global_bytes_refusal_preserves_an_already_issued_exact_raw_return',
    'self_tests.test_pico_emote_stream_capacity.StreamCapacityTests.test_global_part_refusal_sends_zero_and_does_not_reset_an_allowance',
    'self_tests.test_pico_emote_stream_capacity.StreamCapacityTests.test_original_parent_expiry_blocks_capacity_without_starting_another_budget',
    'self_tests.test_pico_emote_stream_capacity.StreamCapacityTests.test_partial_constructor_actual_fd_is_strongly_retained_before_unwind',
)


def load_tests(loader,_tests,_pattern):return loader.loadTestsFromNames(CASE_NAMES)

if __name__=='__main__':unittest.main()
