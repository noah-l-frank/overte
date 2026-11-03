"""Four exact SDK/wire source counters; native producers are explicit models."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[5]/'tests/device'))

CASE_NAMES=(
    'self_tests.test_pico_navigation_scene_probe.NavigationSceneProbeTests.test_actual_sdk_wire_is_retained_in_original_c_lease_before_every_normal_mutation',
    'self_tests.test_pico_navigation_scene_probe.NavigationSceneProbeTests.test_both_actual_role_probe_readers_are_bound_before_source_acquisition',
    'self_tests.test_pico_navigation_scene_probe.NavigationSceneProbeTests.test_foreign_sdk_callback_is_refused_before_any_binary_probe_or_input',
    'self_tests.test_pico_navigation_scene_probe.NavigationSceneProbeTests.test_issued_late_actual_wire_remains_durable_before_sdk_parser_without_new_probe',
)


def load_tests(loader,_tests,_pattern):return loader.loadTestsFromNames(CASE_NAMES)

if __name__=='__main__':unittest.main()
