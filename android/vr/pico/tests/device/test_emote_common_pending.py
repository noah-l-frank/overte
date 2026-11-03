"""Actual Parent2 once-input/pending-restore component, not Common whole."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[5]/'tests/device'))

CASE_NAMES=(
    'self_tests.test_pico_emote_common.CommonTests.test_once_act_pending_natural_restore_then_next_actual_play',
)


def load_tests(loader,_tests,_pattern):return loader.loadTestsFromNames(CASE_NAMES)

if __name__=='__main__':unittest.main()
