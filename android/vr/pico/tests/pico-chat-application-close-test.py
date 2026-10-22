#!/usr/bin/env python3
"""Disjoint original Chat application release and archive checks; no devices."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import argparse
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT/'tests/device'),str(ROOT/'android/vr/pico/tests/device')]


def selected(part):
    if part=='archive':
        return unittest.defaultTestLoader.loadTestsFromNames([
            'self_tests.test_chat_evidence_archive','self_tests.test_chat_archive_files',
            'self_tests.test_chat_archive_plan','test_chat_application_close',
            'self_tests.test_chat_archive_unlink_fence',
            'self_tests.test_chat_archive_index','self_tests.test_chat_host_close',
            'self_tests.test_chat_compiled_dispatcher.CompiledDispatcherTests.test_original_compiled_prefix_uses_distinct_code_roles_and_independent_witness_sources'])
    from self_tests.test_pico_chat_application_close import _application_tests
    return _application_tests(part)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('part',choices=('journey','recovery','admission','delivery','post-ipc','archive'))
    result=unittest.TextTestRunner(verbosity=2).run(selected(parser.parse_args().part))
    raise SystemExit(not result.wasSuccessful())
