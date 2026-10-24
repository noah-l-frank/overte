#!/usr/bin/env python3
"""Disjoint actual private browser Actor exit checks; no device qualification."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import sys
import unittest
import argparse
ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT/'tests/device'))
if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--part',choices=('retirement','return','independent','independent-journey','archive-source','evidence-archive','host-close-fences'),default='retirement')
    part=parser.parse_args().part
    if part in ('independent','independent-journey','archive-source','evidence-archive','host-close-fences'):
        from self_tests.test_pico_browser_independent_process import PicoBrowserIndependentProcessTests
        prefix='self_tests.test_pico_browser_independent_process.PicoBrowserIndependentProcessTests.'
        whole='test_complete_shared_journey_then_original_independent_return_and_all_capture_retirement'
        names=[name for name in unittest.defaultTestLoader.getTestCaseNames(PicoBrowserIndependentProcessTests)
            if (name==whole if part=='independent-journey' else name.startswith('test_archive_source_') if part=='archive-source'
                else name.startswith('test_evidence_archive_') if part=='evidence-archive'
                else name.startswith('test_host_close_fence_') if part=='host-close-fences'
                else name!=whole and not name.startswith(('test_archive_source_','test_evidence_archive_','test_host_close_fence_')))]
        suite=unittest.defaultTestLoader.loadTestsFromNames([prefix+name for name in names]+(['self_tests.test_pico_browser_actor'] if part=='independent' else []))
        if part=='evidence-archive':
            suite.addTests(unittest.defaultTestLoader.loadTestsFromName('self_tests.test_pico_browser_archive_context'))
    else:suite=unittest.defaultTestLoader.loadTestsFromName('self_tests.test_pico_browser_actor_'+part)
    raise SystemExit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())
