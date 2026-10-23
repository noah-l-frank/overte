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
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--part',choices=('retirement','return'),default='retirement')
    module='self_tests.test_pico_browser_actor_'+parser.parse_args().part
    suite=unittest.defaultTestLoader.loadTestsFromName(module)
    raise SystemExit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())
