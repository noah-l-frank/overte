"""Parent2 original intent/CAS/expiry/foreign components, no whole claim."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[5]/'tests/device'))

CASE_NAMES=(
    'self_tests.test_pico_emote_common.CommonTests.test_handled_ignored_play_cannot_become_effect_or_allow_next_input',
    'self_tests.test_pico_emote_common.CommonTests.test_actual_ack_then_unknown_parent_cas_retains_child_and_zero_resend',
    'self_tests.test_pico_emote_common.CommonTests.test_original_parent_expiry_after_issued_intent_sends_zero_input',
    'self_tests.test_pico_emote_common.CommonTests.test_foreign_run_cursor_mutation_and_identical_child_replacement_refuse_without_delivery',
    'self_tests.test_pico_emote_common.CommonTests.test_plan_and_declared_digest_replacement_cannot_rebind_original_parent_policy',
    'self_tests.test_pico_emote_common.CommonTests.test_cursor_and_declared_bytes_replacement_cannot_reseal_actual_durable_child',
    'self_tests.test_pico_emote_common.CommonTests.test_original_parent_clock_fields_cannot_be_renewed_before_native_bookends',
)


def load_tests(loader,_tests,_pattern):return loader.loadTestsFromNames(CASE_NAMES)

if __name__=='__main__':unittest.main()
