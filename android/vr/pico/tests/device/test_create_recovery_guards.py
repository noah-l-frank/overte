"""Bounded normal Create recovery checks."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import unittest
import test_create_recovery_owner as original


def load_tests(loader,tests,pattern):return original.group(loader,'guards')


if __name__=='__main__':unittest.main()
