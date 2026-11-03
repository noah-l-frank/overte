"""Original applied Return resumes across cold G1 reconstruction without replay."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[5]/'tests/device'))

CASE_NAMES=(
    'self_tests.test_pico_navigation_generation_restoration.NavigationGenerationRestorationTests.test_applied_lost_return_cold_finishes_same_original_without_second_qt_or_controller_input',
)


def load_tests(loader,_tests,_pattern):return loader.loadTestsFromNames(CASE_NAMES)

if __name__=='__main__':unittest.main()
