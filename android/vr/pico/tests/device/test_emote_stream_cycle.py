"""Explicit Source4 cycle cases; no compiled/native/device or whole-feature claim."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[5]/'tests/device'))

CASE_NAMES=(
    'self_tests.test_pico_emote_stream_cycle.StreamCycleTests.test_original_normal_play_cancel_close_quiet_and_two_role_arm_stop_drain_share_one_parent',
)


def load_tests(loader,_tests,_pattern):return loader.loadTestsFromNames(CASE_NAMES)

if __name__=='__main__':unittest.main()
