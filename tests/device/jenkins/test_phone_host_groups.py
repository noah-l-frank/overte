#!/usr/bin/env python3
"""Export Phone group regressions through the existing mandatory host owner."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import importlib.util
import unittest

ROOT = Path(__file__).resolve().parents[3]


def _export_test_cases(filename, name):
    path = ROOT / 'android/phone/tests' / filename
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    # Do not register this synthetic name in sys.modules. The existing unittest
    # runner's load_name contract then finds this importable exporter instead
    # of asking a fresh worker to import a synthetic module. Original case IDs
    # stay unchanged, so worker discovery and execution remain comparable.
    spec.loader.exec_module(module)
    exported = 0
    for attribute, value in vars(module).items():
        if (isinstance(value, type) and issubclass(value, unittest.TestCase)
                and value.__module__ == name):
            if not attribute.isidentifier() or attribute in globals():
                raise AssertionError('Invalid or duplicate mandatory Phone test export')
            globals()[attribute] = value
            exported += unittest.defaultTestLoader.loadTestsFromTestCase(value).countTestCases()
    if exported == 0:
        raise AssertionError('Mandatory Phone group regression module is empty')


_export_test_cases('test_phone_runtime_groups.py', '_phone_host_group_scheduler_tests')
_export_test_cases('test_phone_runtime_group_coverage.py', '_phone_host_group_coverage_tests')


if __name__ == '__main__':
    unittest.main()
