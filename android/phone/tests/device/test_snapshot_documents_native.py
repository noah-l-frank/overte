"""Actual Documents file/FD owner, explicit synthetic Binder/PFD callbacks."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import json
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[4]
FIXTURE=ROOT/'tests/device/fixture/android-snapshot-receiver/java/org/overte/snapshot'


class SnapshotDocumentsNativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        parent=ROOT/'build/snapshot-documents-host';parent.mkdir(parents=True,exist_ok=True)
        cls.temp=tempfile.TemporaryDirectory(prefix='java-',dir=parent);cls.addClassCleanup(cls.temp.cleanup);cls.classes=Path(cls.temp.name)
        subprocess.run(['javac','--release','8','-d',str(cls.classes),str(FIXTURE/'SnapshotDocumentsEvidence.java'),
            str(ROOT/'android/phone/tests/instrumentation/snapshot-export/org/overte/snapshot/SnapshotDocumentsHostTest.java')],check=True,timeout=30)
    def execute(self,mode):
        with tempfile.TemporaryDirectory(prefix=mode+'-',dir=self.classes) as directory:
            result=subprocess.run(['java','-cp',str(self.classes),'org.overte.snapshot.SnapshotDocumentsHostTest',mode,directory],text=True,capture_output=True,timeout=10)
            self.assertEqual(0,result.returncode,result.stdout+result.stderr);return json.loads(result.stdout) if result.stdout.strip() else None
    def test_actual_original_creation_writer_hash_uid_fd_and_one_send_delete(self):
        source=self.execute('original');self.assertTrue(source['complete']);self.assertEqual(1,source['documents'][0]['deleteCalls'])
        self.assertEqual(1000,source['documents'][0]['createUid']);self.assertEqual(1001,source['documents'][0]['writerUid']);self.assertTrue(source['fdLifetimes'][0]['closed'])
    def test_prewrite_and_partial_writer_never_supply_bytes_or_retirement(self):
        for mode in ('prewrite','pending-writer','failed-close','wrong-fd','oversize'):
            with self.subTest(mode=mode):self.execute(mode)
    def test_changed_originals_and_unknown_files_remain_owned_and_are_not_erased(self):
        for mode in ('changed-bytes','changed-inode','hard-link','symlink','changed-mode','early-absence','foreign-child'):
            with self.subTest(mode=mode):self.execute(mode)
    def test_real_reader_and_source_thread_lifetimes_gate_retirement(self):
        for mode in ('pending-reader','source-thread'):
            with self.subTest(mode=mode):self.execute(mode)
    def test_nonce_scope_rearm_stale_roots_and_late_resurrections_are_rejected(self):
        for mode in ('rearm','stale-root','closed-inputs','resurrected-document','resurrected-root','cancel-empty'):
            with self.subTest(mode=mode):self.execute(mode)


if __name__=='__main__':unittest.main()
