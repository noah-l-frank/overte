"""Three exact owning-CAS/registered-cleanup counters; no live feature verdict."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[5]/'tests/device'))

CASE_NAMES=(
    'self_tests.test_pico_navigation_scene_relation.NavigationSceneRelationTests.test_unknown_actual_first_cas_cannot_load_or_reseal_failed_owner',
    'self_tests.test_pico_navigation_scene_relation.NavigationSceneRelationTests.test_actual_primary_cas_can_advance_original_actor_typed_load',
    'self_tests.test_pico_navigation_scene_prefix.NavigationScenePrefixTests.test_registered_original_model_cleanup_retains_bytes_but_closes_owned_server_and_fds',
)


def load_tests(loader,_tests,_pattern):return loader.loadTestsFromNames(CASE_NAMES)

if __name__=='__main__':unittest.main()
