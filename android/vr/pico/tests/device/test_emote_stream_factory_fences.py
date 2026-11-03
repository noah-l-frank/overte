"""Actual cold factory; declared SDK/Native/GPU models, no whole/device claim."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[5]/'tests/device'))

CASE_NAMES=(
    'self_tests.test_pico_emote_stream_factory.StreamFactoryTests.test_actual_private_factory_constructs_on_same_parent_before_any_runtime_source_or_gpu',
    'self_tests.test_pico_emote_stream_factory.StreamFactoryTests.test_actual_initial_marker_noise_nul_wire_retained_before_cold_constructor_parser_or_gpu',
    'self_tests.test_pico_emote_stream_factory.StreamFactoryTests.test_actual_first_ui_original_is_hooked_before_picoscriptio_constructor_parser',
    'self_tests.test_pico_emote_stream_factory.StreamFactoryTests.test_actual_issued_initial_wire_after_original_expiry_is_retained_before_guard_without_new_getter',
    'self_tests.test_pico_emote_stream_factory.StreamFactoryTests.test_actual_partial_initial_sdk_timeout_bytes_are_original_and_never_retried',
    'self_tests.test_pico_emote_stream_factory.StreamFactoryTests.test_first_clock_callback_reentry_is_refused_before_getter_and_keeps_original_outer_claim',
    'self_tests.test_pico_emote_stream_factory.StreamFactoryTests.test_first_original_native_guard_reentry_is_refused_before_getter_and_keeps_original_outer_claim',
    'self_tests.test_pico_emote_stream_factory.StreamFactoryTests.test_foreign_target_and_callback_swaps_refuse_before_runtime_getter_or_gpu',
    'self_tests.test_pico_emote_stream_factory.StreamFactoryTests.test_actual_admitted_reader_clock_substitution_refuses_before_any_further_sdk_or_gpu',
    'self_tests.test_pico_emote_stream_factory.StreamFactoryTests.test_expiry_in_original_cold_process_query_stops_before_initial_file_getter_without_new_clock',
    'self_tests.test_pico_emote_stream_factory_capacity.StreamFactoryCapacityTests.test_actual_pending_original_reservations_exhaust_same_bill_before_first_cold_getter',
)


def load_tests(loader,_tests,_pattern):return loader.loadTestsFromNames(CASE_NAMES)

if __name__=='__main__':unittest.main()
