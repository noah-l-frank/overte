"""Pico passive Environment v2 and V1 compatibility; explicit native host seams."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import importlib.util
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[5]/'tests/device'))
from self_tests.test_native_navigation_environment import NavigationEnvironmentTests
path=Path(__file__).resolve().parents[5]/'tests/device/contracts/navigation/test_navigation_environment_native.py'
spec=importlib.util.spec_from_file_location('navigation_environment_native',path)
original=importlib.util.module_from_spec(spec);spec.loader.exec_module(original)
NavigationEnvironmentNativeTests=original.NavigationEnvironmentNativeTests
if __name__=='__main__':unittest.main()
