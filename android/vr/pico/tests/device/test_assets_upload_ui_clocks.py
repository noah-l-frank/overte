"""Explicit Assets Upload UI component; native/product effects are models."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[5]/'tests/device'))
from self_tests.test_pico_assets_upload_ui_raw import AssetsUploadUiRawTests

METHODS=('test_changed_original_upload_clock_refuses_before_native_clock_or_input', 'test_real_delayed_factory_is_charged_before_runtime_sdk_or_input', 'test_real_action_anchor_cas_delay_cannot_start_a_fresh_factory_budget', 'test_acquired_cold_ui_after_original_twenty_seconds_stays_durable')

def load_tests(loader,_tests,_pattern):
    return unittest.TestSuite(loader.loadTestsFromName(name,AssetsUploadUiRawTests) for name in METHODS)

if __name__=='__main__':unittest.main()
