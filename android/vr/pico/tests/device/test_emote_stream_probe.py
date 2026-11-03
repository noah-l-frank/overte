"""Explicit Source4 probe cases; no compiled/native/device or whole-feature claim."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[5]/'tests/device'))

CASE_NAMES=(
    'self_tests.test_pico_emote_stream_probe.StreamProbeTests.test_actual_control_allowance_is_32_and_cannot_reset_by_new_run',
    'self_tests.test_pico_emote_stream_probe.StreamProbeTests.test_actual_control_dispatch_preserves_original_once_and_never_writes_native_sample',
    'self_tests.test_pico_emote_stream_probe.StreamProbeTests.test_missing_native_capability_only_records_unavailable_and_default_source3_still_uses_own_path',
)


def load_tests(loader,_tests,_pattern):return loader.loadTestsFromNames(CASE_NAMES)

if __name__=='__main__':unittest.main()
