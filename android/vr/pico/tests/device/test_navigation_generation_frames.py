"""Fresh G1 originals, recovery and capture namespace guards; native seams modeled."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[5]/'tests/device'))

CASE_NAMES=(
    'self_tests.test_pico_navigation_generation_frames.NavigationGenerationFramesTests.test_fifteen_actions_then_fresh_g1_two_eye_source_and_retirement_preserve_original_close',
    'self_tests.test_pico_navigation_generation_frames.NavigationGenerationFramesTests.test_lost_applied_gpu_result_keeps_original_intent_and_cold_never_reacquires',
    'self_tests.test_pico_navigation_generation_frames.NavigationGenerationFramesTests.test_foreign_file_between_evidence_and_final_namespace_pin_cannot_be_admitted_or_cold_adopted',
    'self_tests.test_pico_navigation_capture_namespaces.NavigationRetiredCaptureNamespacesTests.test_every_canonical_capture_factory_refuses_each_existing_navigation_namespace_before_send',
    'self_tests.test_pico_navigation_capture_namespaces.NavigationRetiredCaptureNamespacesTests.test_g0_and_g1_both_roles_block_browser_and_graphics_retirement_inspection_even_after_admission',
    'self_tests.test_pico_navigation_generation_frame_catalog.NavigationGenerationFrameCatalogTests.test_focused_wrappers_are_disjoint_and_cover_actual_owning_cases',
)


def load_tests(loader,_tests,_pattern):return loader.loadTestsFromNames(CASE_NAMES)

if __name__=='__main__':unittest.main()
