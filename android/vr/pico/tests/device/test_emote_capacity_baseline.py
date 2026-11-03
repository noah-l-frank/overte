"""Actual Policy2 composition; declared Native producers, no whole/device claim."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[5]/'tests/device'))

CASE_NAMES=(
    'self_tests.test_pico_emote_stream_capacity_cycle.StreamCapacityCycleTests.test_original_policy2_and_scope2_arm_sample_normal_cancel_close_quiet_share_original_parent',
    'self_tests.test_pico_emote_stream_capacity_fences.StreamCapacityRequiredTests.test_policy1_without_native_file_capacity_cannot_construct_capture3_or_send_gpu',
    'self_tests.test_pico_emote_stream_capacity_fences.StreamCapacityConstructionTests.test_actual_policy2_can_construct_capture3_on_same_original_budget_without_gpu_request',
)


def load_tests(loader,_tests,_pattern):return loader.loadTestsFromNames(CASE_NAMES)

if __name__=='__main__':unittest.main()
