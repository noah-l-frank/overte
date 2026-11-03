"""Actual Policy2 composition; declared Native producers, no whole/device claim."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[5]/'tests/device'))

CASE_NAMES=(
    'self_tests.test_pico_emote_stream_capacity_fences.StreamCapacityIntegrationFences.test_passive_prelock_identity_reads_no_source_and_cannot_authorize_unheld_admission',
    'self_tests.test_pico_emote_stream_capacity_fences.StreamCapacityIntegrationFences.test_actual_policy2_capacity_graph_substitution_refuses_before_any_new_getter_or_native_send',
    'self_tests.test_pico_emote_stream_capacity_fences.StreamCapacityIntegrationFences.test_real_storage_capacity_cas_completed_then_lost_ack_sends_zero_storage_and_keeps_gpu_intent',
    'self_tests.test_pico_emote_stream_capacity_fences.StreamCapacityIntegrationFences.test_ignored_actual_native_receipt_removal_never_releases_allowance_or_original_owner',
    'self_tests.test_pico_emote_stream_capacity_fences.StreamCapacityIntegrationFences.test_actual_retirement_cas_lost_reply_keeps_pending_witness_and_never_relabels_it_admitted',
)


def load_tests(loader,_tests,_pattern):return loader.loadTestsFromNames(CASE_NAMES)

if __name__=='__main__':unittest.main()
