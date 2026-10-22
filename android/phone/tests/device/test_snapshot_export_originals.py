"""Compile/run passive export originals with the prepared host JDK.

The recorder uses its original clocks. Android operations remain unexecuted.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[4]


class SnapshotExportOriginalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        build=ROOT/'build/snapshot-export-contract';build.mkdir(parents=True,exist_ok=True)
        cls.temporary=tempfile.TemporaryDirectory(prefix='java-',dir=build);cls.addClassCleanup(cls.temporary.cleanup)
        cls.classes=Path(cls.temporary.name)
        subprocess.run(['javac','--release','8','-d',str(cls.classes),
            str(ROOT/'android/common/snapshot/java/org/overte/snapshot/SnapshotExportObservation.java'),
            str(ROOT/'android/phone/tests/instrumentation/snapshot-export/org/overte/snapshot/SnapshotExportObservationHostTest.java')],
            check=True,timeout=60)

    def case(self,name):
        subprocess.run(['java','-cp',str(self.classes),'org.overte.snapshot.SnapshotExportObservationHostTest',name],check=True,timeout=15)

    def test_original_request_identity_callback_order_and_clocks_are_retained(self):self.case('originals')
    def test_unrelated_request_cannot_supply_a_success_callback(self):self.case('foreign')
    def test_late_success_after_retirement_cannot_rewrite_cancellation(self):self.case('duplicate-terminal')
    def test_share_component_selection_does_not_claim_file_consumption(self):self.case('ack-only')
    def test_unknown_result_is_permanently_incomplete(self):self.case('invalid')
    def test_overlapping_active_requests_are_not_collapsed_into_one_identity(self):self.case('overlap')
    def test_overflow_retains_the_original_prefix_and_cannot_reset(self):self.case('overflow')
    def test_concurrent_snapshots_never_mix_sequences_or_mutable_rows(self):self.case('concurrent')


if __name__=='__main__':unittest.main()
