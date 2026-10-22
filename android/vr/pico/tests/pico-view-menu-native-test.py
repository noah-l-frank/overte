#!/usr/bin/env python3
"""Run the original native/QML Pico View-menu input contract."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import runpy
runpy.run_path(str(Path(__file__).resolve().parents[4]/'tests/device/contracts/emote/test_view_menu_native.py'),run_name='__main__')
