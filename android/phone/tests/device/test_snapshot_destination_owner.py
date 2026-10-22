"""Compile actual OS ownership logic; host files stand in for Android content."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[4]


class SnapshotDestinationOwnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        parent=ROOT/'build/snapshot-destination-owner';parent.mkdir(parents=True,exist_ok=True)
        cls.tmp=tempfile.TemporaryDirectory(prefix='java-',dir=parent);cls.addClassCleanup(cls.tmp.cleanup);cls.classes=Path(cls.tmp.name)
        subprocess.run(['javac','--release','8','-d',str(cls.classes),str(ROOT/'android/common/snapshot/java/org/overte/snapshot/SnapshotDestinationOwner.java'),str(ROOT/'android/phone/tests/instrumentation/snapshot-export/org/overte/snapshot/SnapshotDestinationOwnerHostTest.java')],check=True,timeout=30)
    def test_actual_file_identity_bytes_close_delete_and_fresh_absence(self):
        for mode in ('original','foreign','changed-bytes','changed-inode','early-missing','ignored-delete','lost-return','permission-denied','pending-close','close-failure','late-file'):
            with self.subTest(mode=mode),tempfile.TemporaryDirectory(prefix=mode+'-',dir=self.classes) as root:
                subprocess.run(['java','-cp',str(self.classes),'org.overte.snapshot.SnapshotDestinationOwnerHostTest',mode,root],check=True,timeout=10)


if __name__=='__main__':unittest.main()
