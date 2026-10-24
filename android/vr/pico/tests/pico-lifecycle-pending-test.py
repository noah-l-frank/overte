#!/usr/bin/env python3
"""Disjoint owning Lifecycle continuation and original-source checks."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import argparse
from pathlib import Path
import sys
import unittest

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
sys.path.insert(0,str(ROOT/'tests/device'))
sys.path.insert(0,str(HERE/'device'))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('part',choices=('progress','failure','originals'))
    part=parser.parse_args().part
    from self_tests.test_pico_lifecycle_pending import lifecycle_pending_progress_tests,lifecycle_pending_failure_tests
    if part=='progress':suite=lifecycle_pending_progress_tests()
    elif part=='failure':suite=lifecycle_pending_failure_tests()
    else:
        from self_tests.test_lifecycle_pending_freshness import LifecyclePendingFreshnessTests
        from self_tests.test_lifecycle_pending_originals import LifecyclePendingOriginalsTests
        from test_lifecycle_pending_factory import LifecyclePendingFactoryTests
        suite=unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromTestCase(case)
            for case in (LifecyclePendingFreshnessTests,LifecyclePendingOriginalsTests,LifecyclePendingFactoryTests))
    return not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful()


if __name__=='__main__':raise SystemExit(main())
