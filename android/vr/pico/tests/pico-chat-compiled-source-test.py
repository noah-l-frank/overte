#!/usr/bin/env python3
"""Original configured Script/compiled-code ownership and actual Pico binding."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[4]
sys.path[:0] = [str(ROOT / 'tests/device'), str(Path(__file__).resolve().parent / 'device')]

if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromNames([
        'self_tests.test_chat_script_source', 'self_tests.test_chat_script_continuation', 'test_chat_script_source',
        'self_tests.test_chat_compiled_samples',
    ])
    raise SystemExit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())
