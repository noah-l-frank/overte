#!/usr/bin/env python3
"""Fixed Phone5527 original Java contracts on actual host streams and threads.

Android provider/UID/chooser access remains an explicit fixture. No Android OS
or product executor termination is inferred from these portable owner tests.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[4]
PACKAGE='org.overte.snapshot.'


class SnapshotExportJavaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary=tempfile.TemporaryDirectory(prefix='pico-export-java-');cls.addClassCleanup(cls.temporary.cleanup)
        cls.stage=Path(cls.temporary.name);cls.stage.chmod(0o700)
        names=('SnapshotExportObservation','SnapshotReadbackFiles','SnapshotDestinationOwner')
        sources=[ROOT/'android/common/snapshot/java/org/overte/snapshot'/str(name+'.java') for name in names]
        sources += [Path(__file__).parent/'java/org/overte/snapshot'/str(name+'HostTest.java') for name in names]
        subprocess.run(['javac','-d',str(cls.stage),*map(str,sources)],check=True,timeout=20)
    def execute(self,name,modes):
        for mode in modes:
            with self.subTest(mode=mode),tempfile.TemporaryDirectory(prefix='original-',dir=self.stage) as directory:
                subprocess.run(['java','-cp',str(self.stage),PACKAGE+name+'HostTest',mode,directory],check=True,timeout=8)
    def test_actual_monotone_callback_and_pending_work_history(self):
        self.execute('SnapshotExportObservation',('originals','foreign','duplicate-terminal','ack-only','invalid','overlap','overflow','concurrent',
            'io-late','io-rejected','io-foreign','io-missing-start','io-duplicate-finish'))
    def test_actual_private_readback_stream_faults_and_release(self):
        self.execute('SnapshotReadbackFiles',('original','mutated','alias','hardlink','mode','partial','cancel','empty','close-failure',
            'foreign-cleanup','recreated','rejected-stream'))
    def test_actual_original_destination_one_send_delete_and_readonly_recovery(self):
        self.execute('SnapshotDestinationOwner',('original','pending-close','close-failure','foreign','changed-bytes','changed-inode','early-missing',
            'ignored-delete','lost-return','permission-denied','late-file','pending-origin','pending-origin-denied','pending-origin-failed'))


if __name__=='__main__':unittest.main()
