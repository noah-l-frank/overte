#!/usr/bin/env python3
"""Actual lookup/dismissal/normal-close source ownership on explicit host seams."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[4]

if __name__=='__main__':
    raise SystemExit(subprocess.run([sys.executable,'-m','unittest',
        'self_tests.test_navigation_lookup_close','self_tests.test_navigation_tablet_close','-v'],
        cwd=ROOT/'tests/device',check=False).returncode)
