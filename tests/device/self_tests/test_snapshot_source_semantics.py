"""Reuse original Snapshot JS cases without native compilation or device access."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import subprocess
import unittest


class SnapshotSourceSemantics(unittest.TestCase):
    def test_original_capture_cancellation_late_callbacks_uploads_and_local_readiness(self):
        root=Path(__file__).resolve().parents[3]
        result=subprocess.run(['node','--test','tests/javascript/test/snapshot.production.test.js'],
            cwd=root,capture_output=True,text=True,timeout=15)
        self.assertEqual(0,result.returncode,result.stdout+result.stderr)
        self.assertIn('tests 14',result.stdout)
        self.assertIn('pass 14',result.stdout)
        self.assertIn('cancelled 0',result.stdout)
        self.assertIn('skipped 0',result.stdout)
        self.assertIn('fail 0',result.stdout)


if __name__=='__main__':unittest.main()
