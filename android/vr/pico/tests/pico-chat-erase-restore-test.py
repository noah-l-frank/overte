#!/usr/bin/env python3
"""Original normal Erase/reopening and exact profile restoration ownership."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT/'tests/device'))
if __name__=='__main__':
    suite=unittest.defaultTestLoader.loadTestsFromNames(['self_tests.test_chat_erase_restore','self_tests.test_chat_profile_owner'])
    raise SystemExit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())
