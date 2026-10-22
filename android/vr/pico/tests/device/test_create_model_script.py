"""Original bridge/createNewEntity algorithm with declared actor/clock seams."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import subprocess
import unittest


class CreateModelScriptTests(unittest.TestCase):
    def test_original_model_create_timeout_dimensions_and_permission_routes(self):
        subprocess.run(['node',str(Path(__file__).with_name('create-model-script.js'))],check=True,timeout=10)


if __name__=='__main__':unittest.main()
