#!/usr/bin/env python3
"""Disjoint original Chat cache/IPC release cases within the existing budget."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT/'tests/device'))
GROUPS={'positive':'cache_release_positive_tests','admission':'cache_release_admission_tests',
    'quiet':'cache_release_quiet_tests','final-clock':'cache_release_final_clock_tests',
    'deferred':'cache_release_deferred_tests'}
if __name__=='__main__':
    if len(sys.argv)!=2 or sys.argv[1] not in GROUPS:raise SystemExit('Select one original Chat cache-release group')
    suite=unittest.defaultTestLoader.loadTestsFromName('self_tests.test_chat_cache_release.'+GROUPS[sys.argv[1]])
    raise SystemExit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())
