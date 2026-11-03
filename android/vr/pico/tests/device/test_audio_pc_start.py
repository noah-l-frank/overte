"""Normal Audio/independent PC originals; explicit native/media/OS test models.

Only owned stdin Python workers run. No audio service, device or compiler.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[5]/'tests/device'))

CASE_NAMES=(
    'self_tests.test_pico_audio_pc_start.AudioPCStartTests.test_same_fourteen_normal_actions_independent_originals_and_actual_digital_recorder_handback',
)


def load_tests(loader,_tests,_pattern):return loader.loadTestsFromNames(CASE_NAMES)

if __name__=='__main__':unittest.main()
