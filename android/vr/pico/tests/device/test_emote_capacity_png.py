"""Explicit capacity component cases; no Native/device/whole claim."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[5]/'tests/device'))

CASE_NAMES=(
    'self_tests.test_pico_emote_stream_capacity.StreamPNGCapacityTests.test_actual_png_larger_than_compound_limit_refuses_before_first_storage_chunk',
    'self_tests.test_pico_emote_stream_capacity.StreamPNGCapacityTests.test_future_png_copy_transfers_only_to_actual_original_file_with_same_full_stamp',
    'self_tests.test_pico_emote_stream_capacity.StreamPNGCapacityTests.test_actual_equal_bytes_foreign_png_inode_refuses_without_freeing_more_allowance',
    'self_tests.test_pico_emote_stream_capacity.StreamPNGCapacityTests.test_actual_png_capacity_cas_lost_reply_keeps_constructed_file_owner_strong',
    'self_tests.test_pico_emote_stream_capacity.StreamPNGCapacityTests.test_generic_commit_cannot_clear_or_reduce_actual_native_receipt_reservation',
)


def load_tests(loader,_tests,_pattern):return loader.loadTestsFromNames(CASE_NAMES)

if __name__=='__main__':unittest.main()
