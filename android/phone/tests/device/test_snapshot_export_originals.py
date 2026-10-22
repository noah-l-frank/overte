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
            str(ROOT/'android/common/snapshot/java/org/overte/snapshot/SnapshotReadbackFiles.java'),
            str(ROOT/'android/phone/tests/instrumentation/snapshot-export/org/overte/snapshot/SnapshotExportObservationHostTest.java'),
            str(ROOT/'android/phone/tests/instrumentation/snapshot-export/org/overte/snapshot/SnapshotReadbackFilesHostTest.java')],
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
    def test_cancelled_native_lease_does_not_hide_its_running_original_io(self):self.case('io-late')
    def test_actual_executor_rejection_has_no_remaining_io_responsibility(self):self.case('io-rejected')
    def test_foreign_io_completion_cannot_clear_an_owned_responsibility(self):self.case('io-foreign')
    def test_missing_original_io_start_never_becomes_completed_work(self):self.case('io-missing-start')
    def test_duplicate_io_finish_is_permanently_incomplete(self):self.case('io-duplicate-finish')

    def files(self,name):
        with tempfile.TemporaryDirectory(prefix='streams-',dir=self.classes) as parent:
            subprocess.run(['java','-cp',str(self.classes),'org.overte.snapshot.SnapshotReadbackFilesHostTest',name,parent],check=True,timeout=15)

    def test_independently_consumed_stream_has_actual_bytes_and_verified_copy_retirement(self):self.files('original')
    def test_changed_copy_bytes_cannot_be_silently_deleted(self):self.files('mutated')
    def test_symlink_substitution_cannot_be_read_as_an_original_or_removed(self):self.files('alias')
    def test_hardlink_alias_cannot_qualify_private_evidence_or_be_silently_removed(self):self.files('hardlink')
    def test_public_file_permissions_cannot_qualify_private_evidence(self):self.files('mode')
    def test_partial_read_failure_retains_owned_cleanup_responsibility(self):self.files('partial')
    def test_cancelled_read_cannot_publish_a_complete_original(self):self.files('cancel')
    def test_empty_destination_is_not_a_saved_file(self):self.files('empty')
    def test_stream_close_failure_is_not_successful_acquisition(self):self.files('close-failure')
    def test_unknown_files_block_directory_retirement_and_are_preserved(self):self.files('foreign-cleanup')
    def test_retired_directory_recreation_is_detected(self):self.files('recreated')
    def test_rejected_request_also_closes_its_real_stream(self):self.files('rejected-stream')


if __name__=='__main__':unittest.main()
