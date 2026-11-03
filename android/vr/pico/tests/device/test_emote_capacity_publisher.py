"""Explicit capacity component cases; no Native/device/whole claim."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[5]/'tests/device'))

CASE_NAMES=(
    'self_tests.test_pico_emote_capacity_publisher.StreamPublisherTests.test_actual_exact_cap_write_then_oversize_keeps_original_bytes_and_failed_nonce',
    'self_tests.test_pico_emote_capacity_publisher.StreamPublisherTests.test_actual_partial_write_retains_marker_original_ofds_and_partial_bytes',
    'self_tests.test_pico_emote_capacity_publisher.StreamPublisherTests.test_actual_complete_write_lost_return_never_becomes_clean_success_or_retry',
    'self_tests.test_pico_emote_capacity_publisher.StreamPublisherTests.test_actual_equal_bytes_inode_replacement_refuses_before_intent_or_write',
    'self_tests.test_pico_emote_capacity_publisher.StreamPublisherTests.test_actual_ancestor_directory_exchange_refuses_before_native_publication',
    'self_tests.test_pico_emote_capacity_publisher.StreamPublisherTests.test_actual_orphan_receipt_prevents_any_fixed_slot_or_native_output',
)


def load_tests(loader,_tests,_pattern):return loader.loadTestsFromNames(CASE_NAMES)

if __name__=='__main__':unittest.main()
