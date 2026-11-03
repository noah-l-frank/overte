"""Disjoint no-build remote Emote component checks; native edges are models."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[5]/'tests/device'))

CASE_NAMES=(
    'self_tests.test_pico_emote_capture.PicoEmoteRemoteCaptureTests.test_complete_normal_input_remote_two_eye_png_cancel_close_and_original_quiet_cycle',
    'self_tests.test_pico_emote_capture.PicoEmoteRemoteCaptureTests.test_unrelated_ui_bridge_does_not_supply_or_override_native_avatar_session',
    'self_tests.test_pico_emote_capture.PicoEmoteRemoteCaptureTests.test_malformed_foreign_subject_or_same_pid_foreign_renderer_is_retained_before_refusal',
    'self_tests.test_pico_emote_capture.PicoEmoteRemoteCaptureTests.test_missing_executed_eye_or_ignored_capture_cannot_become_remote_stereo',
    'self_tests.test_pico_emote_capture.PicoEmoteRemoteCaptureTests.test_lost_acquire_or_model_reply_keeps_issue_and_recovers_only_original_resources',
    'self_tests.test_pico_emote_capture.PicoEmoteRemoteCaptureTests.test_real_png_change_inode_link_or_root_replacement_never_becomes_original',
    'self_tests.test_pico_emote_capture.PicoEmoteRemoteCaptureTests.test_original_parent_deadline_inside_native_send_prevents_capture_without_renewal',
    'self_tests.test_pico_emote_capture.PicoEmoteRemoteCaptureTests.test_delayed_final_validation_is_durable_failed_never_cold_completed_or_reacquired',
    'self_tests.test_pico_emote_capture.PicoEmoteRemoteCaptureTests.test_original_model_guard_expiry_keeps_saved_png_and_sends_zero_late_model_queries',
    'self_tests.test_pico_emote_capture.PicoEmoteRemoteCaptureTests.test_lost_original_journal_return_cannot_dispatch_or_be_cold_adopted',
    'self_tests.test_pico_emote_capture.PicoEmoteRemoteCaptureTests.test_original_pending_child_is_not_adopted_or_removed_on_capture_constructor_refusal',
    'self_tests.test_pico_emote_capture.PicoEmoteRemoteCaptureTests.test_actual_recycled_capture_directory_ofd_is_retained_until_real_child_exit',
    'self_tests.test_pico_emote_capture.PicoEmoteRemoteCaptureTests.test_callback_or_live_parent_timer_cannot_finish_a_retired_component',
)

def load_tests(loader,_tests,_pattern):
    return loader.loadTestsFromNames(CASE_NAMES)

if __name__=='__main__':unittest.main()
