"""Current original old-PID, Qt-CAS, retained-source and reader-owner guards."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[5]/'tests/device'))

CASE_NAMES=(
    'self_tests.test_pico_navigation_generation_restoration.NavigationGenerationRestorationTests.test_actual_old_pid_presence_blocks_handoff_before_new_open_or_qt_input',
    'self_tests.test_pico_navigation_generation_restoration.NavigationGenerationRestorationTests.test_phase_changes_after_real_entry_command_cas_send_zero_entry_and_cold_never_repeats',
    'self_tests.test_pico_navigation_generation_restoration.NavigationGenerationRestorationTests.test_foreign_settings_original_is_archived_before_refusal_and_reading_acquisition_cannot_be_adopted',
    'self_tests.test_pico_navigation_generation_restoration.NavigationGenerationRestorationTests.test_reused_reader_keeps_original_writer_and_cannot_bypass_single_owner_on_retry',
)


def load_tests(loader,_tests,_pattern):return loader.loadTestsFromNames(CASE_NAMES)

if __name__=='__main__':unittest.main()
