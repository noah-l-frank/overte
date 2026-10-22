#!/usr/bin/env python3
"""Fixed original Chat journey, recovery and phase admission, without devices."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import argparse
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT/'tests/device'),str(ROOT/'android/vr/pico/tests/device')]
LEGACY_JOURNEY='self_tests.test_chat_dispatcher.DispatcherTests.test_all_25_real_child_steps_share_original_native_ui_storage_and_peer_histories'
JOURNEY='self_tests.test_chat_compiled_dispatcher.CompiledDispatcherTests.test_all_original_25_steps_and_26_independent_compiled_witness_stages'


def cases(suite):
    for item in suite:
        if isinstance(item,unittest.TestSuite):yield from cases(item)
        else:yield item


def selected(part):
    loader=unittest.defaultTestLoader
    if part=='journey':return loader.loadTestsFromName(JOURNEY)
    if part=='phase':return loader.loadTestsFromNames([
        'self_tests.test_chat_phase_fence','self_tests.test_chat_phase_transports',
        'self_tests.test_chat_cleanup_admission',
        'test_chat_lifecycle_phase_transport'])
    suite=loader.loadTestsFromName('self_tests.test_chat_dispatcher')
    return unittest.TestSuite(case for case in cases(suite) if case.id()!=LEGACY_JOURNEY)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('part',choices=('journey','recovery','phase'))
    result=unittest.TextTestRunner(verbosity=2).run(selected(parser.parse_args().part))
    raise SystemExit(0 if result.wasSuccessful() else 1)
