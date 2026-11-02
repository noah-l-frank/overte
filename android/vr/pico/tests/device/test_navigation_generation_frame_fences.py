"""Actual original-CAS/outer-exit/ignored-release G1 continuation fences."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[5]/'tests/device'))

CASE_NAMES=(
    'self_tests.test_pico_navigation_generation_frames.NavigationGenerationFramesTests.test_phase_advance_after_real_frame_pending_cas_sends_zero_gpu_and_keeps_original_pending',
    'self_tests.test_pico_navigation_generation_frames.NavigationGenerationFramesTests.test_original_close_same_byte_replacement_after_outer_release_refuses_publication',
    'self_tests.test_pico_navigation_generation_frames.NavigationGenerationFramesTests.test_foreign_artifact_after_real_outer_release_refuses_without_new_query_or_capture',
    'self_tests.test_pico_navigation_generation_frames.NavigationGenerationFramesTests.test_ignored_memory_release_retains_original_owner_and_cold_repeats_no_mutation',
)


def load_tests(loader,_tests,_pattern):return loader.loadTestsFromNames(CASE_NAMES)

if __name__=='__main__':unittest.main()
