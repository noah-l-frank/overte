"""Fresh Lifecycle primary observations on the existing restore owner path."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[5]/'tests/device'))
from self_tests.test_pico_lifecycle_observation import LifecycleObservationTests,LifecycleObservationResourceTests

if __name__=='__main__':unittest.main()
