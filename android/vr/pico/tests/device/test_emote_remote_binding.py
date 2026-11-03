"""Disjoint no-build remote Emote component checks; native edges are models."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[5]/'tests/device'))

CASE_NAMES=(
    'self_tests.test_pico_emote_capture.PicoEmoteRemoteBindingTests.test_actual_typed_script_route_completes_normal_capture_and_quiet_cycle',
    'self_tests.test_pico_emote_capture.PicoEmoteRemoteBindingTests.test_failed_source_cannot_acquire_but_same_existing_intent_retires_with_original_files',
    'self_tests.test_pico_emote_capture.PicoEmoteRemoteBindingTests.test_actual_binding_refuses_foreign_type_scope_path_lock_and_competing_owners',
)

def load_tests(loader,_tests,_pattern):
    return loader.loadTestsFromNames(CASE_NAMES)

if __name__=='__main__':unittest.main()
