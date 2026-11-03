"""Original fifteen-action G1 directory restoration and pre-input type admission."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[5]/'tests/device'))

CASE_NAMES=(
    'self_tests.test_pico_navigation_generation_restoration.NavigationGenerationRestorationTests.test_fifteen_original_actions_then_normal_g1_login_return_home_close_restore_exact_original',
    'self_tests.test_pico_navigation_generation_restoration.NavigationGenerationRestorationTests.test_original_qurl_setting_is_refused_before_any_normal_mutation',
    'self_tests.test_pico_navigation_generation_restoration.NavigationGenerationRestorationTests.test_original_absent_setting_is_refused_before_any_normal_mutation',
    'self_tests.test_pico_navigation_restoration_catalog.NavigationRestorationCatalogTests.test_three_wrappers_select_all_original_cases_once',
)


def load_tests(loader,_tests,_pattern):return loader.loadTestsFromNames(CASE_NAMES)

if __name__=='__main__':unittest.main()
