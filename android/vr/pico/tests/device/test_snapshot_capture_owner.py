"""Original host-file/scan ownership; the target source producer is a seam."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import hashlib
import sys
import unittest
from unittest.mock import patch
import test_native_execution_binding as original
ROOT=Path(__file__).resolve().parents[5]
sys.path.insert(0,str(ROOT/'tests/device'))
from self_tests.test_pico_snapshot_capture_owner import CaptureFilesTests
from adapters.normal_ui import NativeUIError


class PicoSnapshotCaptureOwnerTests(unittest.TestCase):
    def test_actual_factory_verifies_original_ui_candidate_and_exact_source_lock_before_control(self):
        fixture=original.NativeExecutionBindingTest();fixture.setUp();self.addCleanup(fixture.doCleanups)
        fixture.snapshot_setup();adapter=fixture.instance();native=fixture.fake
        snapshot=adapter._snapshot(native.target);observed=snapshot.ui.snapshot();installed=adapter._installation(native.target)
        binding={key:installed[key] for key in ('sourceRevision','artifactSha256')}
        binding.update(processIdentity=snapshot.ui.io.identity,sessionId=observed['bridgeId'],generation=0,
            targetFingerprint=hashlib.sha256((native.target+'\0'+str(adapter.pico_configuration)).encode()).hexdigest())
        lock=adapter._script_journey()._lock(native.target);path=lock.path.with_name('snapshot-capture-files-test.json');seen=[]
        def reject(command):seen.append(command);raise NativeUIError('Parent phase unavailable')
        owner=adapter._snapshot_capture_files(native.target,native.artifacts,path,binding,before_send=reject,source_lock=lock)
        self.assertIs(lock,owner.source.lock)
        with patch.object(native,'write_debug_app_file',side_effect=AssertionError('Writer after rejected parent')):
            with self.assertRaises(NativeUIError):owner.plan('a'*32,'parity-'+('a'*16)+'-animated')
        self.assertEqual(1,len(seen));self.assertEqual('pico-snapshot-files-observe',seen[0]['action'])
        self.assertFalse(path.exists())
        foreign=dict(binding,sessionId='foreign')
        with self.assertRaises((ValueError,RuntimeError)):
            adapter._snapshot_capture_files(native.target,native.artifacts,path,foreign,before_send=reject,source_lock=lock)
        self.assertFalse(any(cap.startswith('feature.snapshots.') for cap in adapter.capabilities(native.target)))


if __name__=='__main__':unittest.main()
