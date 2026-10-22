"""Actual normal Pico field/capture/cancel path; SDK and renderer are seams."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch
import test_native_execution_binding as original
ROOT=Path(__file__).resolve().parents[5]
sys.path.insert(0,str(ROOT/'tests/device'))
from self_tests.test_pico_snapshot_cancel import SnapshotCancelTests
from adapters.pico4.snapshot_cancel import PicoSnapshotCancel,PicoSnapshotCancelIO
from adapters.normal_ui import NativeUIError


class PicoSnapshotCancelTests(unittest.TestCase):
    def test_actual_private_factory_preserves_parent_lock_and_final_input_callback(self):
        fixture=original.NativeExecutionBindingTest();fixture.setUp();self.addCleanup(fixture.doCleanups)
        fixture.snapshot_setup();adapter=fixture.instance();native=fixture.fake;admitted=[]
        lock=adapter._script_journey()._lock(native.target)
        def reject(command):admitted.append(command);raise NativeUIError('Parent phase unavailable')
        reader=adapter._snapshot_cancel(native.target,before_send=reject,source_lock=lock)
        self.assertIs(lock,reader.lock);self.assertIsInstance(reader.io,PicoSnapshotCancelIO)
        request=PicoSnapshotCancel.envelope('a'*32,'b'*32,'observe')
        with patch.object(native,'write_debug_app_file',side_effect=AssertionError('Writer after rejected parent')):
            with self.assertRaises(NativeUIError):reader.request(request)
        self.assertEqual([request],admitted)
        native.digest='f'*64
        with self.assertRaises((ValueError,RuntimeError)):reader.io.guard()
        with self.assertRaises((ValueError,RuntimeError)):reader.request(request)
        self.assertEqual([request],admitted)
        self.assertFalse(any(value.startswith('feature.snapshots.') for value in adapter.capabilities(native.target)))
    def test_actual_original_native_recipe_bridge_getter_qml_pointer_and_readonly_recovery(self):
        subprocess.run([sys.executable,str(ROOT/'tests/device/contracts/snapshot/test_snapshot_cancel_originals.py')],check=True,timeout=90)


if __name__=='__main__':unittest.main()
