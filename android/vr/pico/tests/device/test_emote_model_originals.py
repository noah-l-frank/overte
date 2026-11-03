"""Disjoint no-build original model reply and predispatch capacity counters."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[5]/'tests/device'))
from self_tests.test_pico_emote_model_originals import EmoteModelOriginalTests

if __name__=='__main__':unittest.main()
