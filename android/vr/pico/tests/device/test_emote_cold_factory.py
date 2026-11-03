"""Cold ordinary Emote constructors and first normal effects; no whole claim."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[5]/'tests/device'))
from self_tests.test_pico_emote_cold_factory import ColdFactoryTests


def load_tests(loader,tests,pattern):
    return loader.loadTestsFromTestCase(ColdFactoryTests)


if __name__=='__main__':unittest.main()
