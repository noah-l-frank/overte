"""Explicit UI2 shared weak-object relation; native source remains uncompiled."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import unittest
from self_tests.test_pico_lifecycle_field_binding import LifecycleFieldBindingTests


def load_tests(loader,tests,pattern):
    return loader.loadTestsFromTestCase(LifecycleFieldBindingTests)
