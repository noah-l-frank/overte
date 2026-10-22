#!/usr/bin/env python3
"""Original Script QObject lifetime source, narrow Qt producer and protocol checks."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import importlib.util
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT/'tests/device'))
SPEC=importlib.util.spec_from_file_location('pico_script_object_lifetimes_native',ROOT/'tests/device/contracts/lifecycle/test_script_object_lifetimes.py')
NATIVE=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(NATIVE)
if __name__=='__main__':
    loader=unittest.defaultTestLoader
    suite=loader.loadTestsFromName('self_tests.test_native_script_object_lifetimes')
    suite.addTests(loader.loadTestsFromName('self_tests.test_pico_browser_vm'))
    suite.addTests(loader.loadTestsFromModule(NATIVE))
    raise SystemExit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())
