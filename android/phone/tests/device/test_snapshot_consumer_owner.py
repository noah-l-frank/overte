"""Real receiver core/files/threads on explicit synthetic Android grant seams."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import subprocess
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[4]

class SnapshotConsumerOwnerTests(unittest.TestCase):
    def test_actual_receiver_original_and_retirement_counterexamples(self):
        parent=ROOT/'build/snapshot-consumer-owner';parent.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='java-',dir=parent) as folder:
            build=Path(folder)
            sources=[ROOT/'android/common/snapshot/java/org/overte/snapshot/SnapshotReadbackFiles.java',ROOT/'tests/device/fixture/android-snapshot-receiver/java/org/overte/snapshot/SnapshotConsumerEvidence.java',ROOT/'android/phone/tests/instrumentation/snapshot-export/org/overte/snapshot/SnapshotConsumerHostTest.java']
            subprocess.run(['javac','--release','8','-d',str(build),*map(str,sources)],check=True,timeout=30)
            for mode in ('original','orphan','unconsumed','missing-grant','failed-close','pending-close','changed-bytes','changed-inode','pending-transfer','late-grant','late-file'):
                with self.subTest(mode=mode),tempfile.TemporaryDirectory(prefix='original-',dir=build) as data:
                    result=subprocess.run(['java','-cp',str(build),'org.overte.snapshot.SnapshotConsumerHostTest',mode,data],capture_output=True,text=True,timeout=12)
                    self.assertEqual(0,result.returncode,result.stdout+result.stderr)
if __name__=='__main__':unittest.main()
