"""Explicit capacity component cases; no Native/device/whole claim."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[5]/'tests/device'))

CASE_NAMES=(
    'self_tests.test_pico_emote_capacity_routing.StreamRoutingTests.test_explicit_policy2_selected_before_queue_remote_lifecycle_and_expired_arm_refusals',
    'self_tests.test_pico_emote_capacity_routing.StreamRoutingTests.test_selected_policy2_absent_publisher_never_deletes_or_overwrites_real_original',
    'self_tests.test_pico_emote_capacity_routing.StreamRoutingTests.test_malformed_duplicate_and_string_policy2_cannot_restore_legacy_route',
    'self_tests.test_pico_emote_capacity_routing.StreamRoutingTests.test_exact_canonical_legacy_policy1_keeps_original_file_behavior',
    'self_tests.test_pico_emote_capacity_routing.StreamRoutingTests.test_noncanonical_valid_json_policy1_is_already_refused_before_modeled_publication_or_confirmation',
    'self_tests.test_pico_emote_capacity_routing.StreamRoutingTests.test_actual_uncompiled_native_source_has_original_canonical_policy_gate_before_gate_file_and_tick',
)


def load_tests(loader,_tests,_pattern):return loader.loadTestsFromNames(CASE_NAMES)

if __name__=='__main__':unittest.main()
