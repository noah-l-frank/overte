"""Exact directory/archive ownership counters; no product or device facts."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[5]/'tests/device'))

CASE_NAMES=('self_tests.test_original_directory_retirement', 'self_tests.test_chat_archive_directories', 'self_tests.test_chat_archive_directory_scale')

def load_tests(loader,_tests,_pattern):return loader.loadTestsFromNames(CASE_NAMES)

if __name__=='__main__':unittest.main()
