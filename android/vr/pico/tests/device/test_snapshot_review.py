"""Host verification of the passive actual Pico Snapshot Review boundary."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import subprocess
import sys
import unittest
ROOT=Path(__file__).resolve().parents[5]
sys.path.insert(0,str(ROOT/'tests/device'))
from self_tests.test_pico_snapshot_review import SnapshotReviewTests


class SnapshotReviewNativeTests(unittest.TestCase):
    def test_original_qml_context_pointer_and_hidden_source_without_input_effect_inference(self):
        subprocess.run([sys.executable,str(ROOT/'tests/device/contracts/snapshot/test_snapshot_review_originals.py')],check=True,timeout=90)


if __name__=='__main__':unittest.main()
