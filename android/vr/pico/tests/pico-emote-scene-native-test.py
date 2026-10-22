#!/usr/bin/env python3
"""Compile the original Pico stimulus getter and two-object lifetime contract."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import runpy
runpy.run_path(str(Path(__file__).resolve().parents[4]/'tests/device/contracts/emote/test_emote_scene_native.py'),run_name='__main__')
