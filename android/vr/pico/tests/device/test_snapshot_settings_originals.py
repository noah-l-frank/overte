"""Actual passive native bodies and hardware-free source admission guards."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import importlib.util
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[5]
sys.path.insert(0,str(ROOT/'tests/device'))
from self_tests.test_pico_snapshot_settings_originals import SnapshotSettingsReaderTests
spec=importlib.util.spec_from_file_location('pico_settings_native',ROOT/'tests/device/contracts/snapshot/test_snapshot_settings_native.py')
original=importlib.util.module_from_spec(spec);spec.loader.exec_module(original)
SnapshotSettingsNativeTests=original.SnapshotSettingsNativeTests


if __name__=='__main__':unittest.main()
