"""Owning wrapper for the actual native Avatar/Model URL bodies and getter."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import importlib.util
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[5]
SPEC=importlib.util.spec_from_file_location('pico_avatar_state_native',ROOT/'tests/device/contracts/avatar/test_avatar_state_native.py')
MODULE=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(MODULE)
AvatarStateNativeTests=MODULE.AvatarStateNativeTests
if __name__=='__main__':unittest.main()
