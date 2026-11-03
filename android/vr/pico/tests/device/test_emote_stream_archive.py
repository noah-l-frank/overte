"""Passive source4 original replay; no native/device or whole-feature claim."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[5]/'tests/device'))

CASE_NAMES=(
    'self_tests.test_pico_emote_stream_archive.StreamArchiveTests.test_actual_role_and_range_replay_survives_business_source_loss_without_any_getter_or_input',
    'self_tests.test_pico_emote_stream_archive.StreamArchiveTests.test_real_unknown_role_cas_tail_remains_unconfirmed_original_without_becoming_accepted_arm',
    'self_tests.test_pico_emote_stream_archive.StreamArchiveTests.test_actual_equal_bytes_foreign_range_inode_cannot_be_replayed_as_original_source',
    'self_tests.test_pico_emote_stream_archive.StreamArchiveTests.test_mutated_passive_packet_memory_never_replaces_actual_retained_original',
)


def load_tests(loader,_tests,_pattern):return loader.loadTestsFromNames(CASE_NAMES)

if __name__=='__main__':unittest.main()
