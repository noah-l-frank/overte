"""Seven exact native raw admission/return counters; no whole recipe claim."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[5]/'tests/device'))

CASE_NAMES=(
    'self_tests.test_pico_navigation_scene_raw_reader.NavigationSceneRawReaderTests.test_aggregate_part_cap_refuses_before_actual_native_send_and_getter',
    'self_tests.test_pico_navigation_scene_raw_reader.NavigationSceneRawReaderTests.test_issued_late_query_return_is_retained_without_parser_or_later_getter',
    'self_tests.test_pico_navigation_scene_raw_reader.NavigationSceneRawReaderTests.test_issued_lost_parent_return_is_retained_before_business_rejection',
    'self_tests.test_pico_navigation_scene_raw_reader.NavigationSceneRawReaderTests.test_legal_incompressible_nul_literal_is_durable_before_actual_native_parser_boundary',
    'self_tests.test_pico_navigation_scene_raw_reader.NavigationSceneRawReaderTests.test_lost_parent_after_reservation_prevents_actual_send',
    'self_tests.test_pico_navigation_scene_raw_reader.NavigationSceneRawReaderTests.test_original_read_callback_replacement_is_refused_before_source_io',
    'self_tests.test_pico_navigation_scene_raw_reader.NavigationSceneRawReaderTests.test_raw_admission_cost_expiring_original_query_prevents_actual_send',
)


def load_tests(loader,_tests,_pattern):return loader.loadTestsFromNames(CASE_NAMES)

if __name__=='__main__':unittest.main()
