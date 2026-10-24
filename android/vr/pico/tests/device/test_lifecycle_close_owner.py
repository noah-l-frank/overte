"""Original normal X close, second World action and original cap refusal."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[5]/'tests/device'))
from self_tests.test_pico_lifecycle_close import LifecycleCloseTests
from test_lifecycle_close_factory import LifecycleCloseFactoryTests

if __name__=='__main__':unittest.main()
