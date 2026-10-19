"""Run the existing original Create bridge cases without Qt/native compilation."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import subprocess
import unittest


class CreateSourceSemantics(unittest.TestCase):
    def test_original_create_bridge_import_ownership_permissions_and_stale_callbacks(self):
        root=Path(__file__).resolve().parents[3]
        result=subprocess.run(['node','--test','tests/javascript/test/mobile-create.bridge.test.js'],
            cwd=root,capture_output=True,text=True,timeout=15)
        self.assertEqual(0,result.returncode,result.stdout+result.stderr)
        self.assertIn('tests 7',result.stdout)
        self.assertIn('fail 0',result.stdout)


if __name__=='__main__':unittest.main()
