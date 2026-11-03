"""Actual production owner admission with a known live original model Parent.

No complete public journey or native/candidate qualification is claimed.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ENTRY = Path(__file__).with_name('pico_browser_owner_admission_worker.py').resolve()


class BrowserOwnerAdmissionTests(unittest.TestCase):
    def test_actual_owner_constructs_and_receives_one_original_begin_without_native_query(self):
        self.run_admission('normal')

    def test_duplicate_original_begin_is_sticky_and_preserves_actual_marker_without_native_query(self):
        self.run_admission('duplicate')

    def test_real_actor_cli_refusal_blocks_public_admission_and_keeps_original_marker(self):
        self.run_admission('actor-parser')

    def test_foreign_store_holder_cannot_resume_after_restoring_original_holder(self):
        self.run_admission('holder-swap')

    def run_admission(self, fault):
        temporary = tempfile.TemporaryDirectory(prefix='pico-browser-owner-admission-')
        self.addCleanup(temporary.cleanup); root = Path(temporary.name); root.chmod(0o700)
        original = self.pin()
        environment = dict(os.environ, OVT_BROWSER_ADMISSION_ROOT=str(root),
            OVT_BROWSER_ADMISSION_FAULT=fault, PYTHONDONTWRITEBYTECODE='1')
        process = subprocess.Popen([sys.executable, str(ENTRY), '--area', 'tablet-web'],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=environment)
        stdout, stderr = process.communicate(timeout=25)
        (root/'parent.stdout.bin').write_bytes(stdout); (root/'parent.stderr.bin').write_bytes(stderr)
        self.assertEqual(0, process.returncode, stderr.decode('utf-8', 'replace'))
        self.assertFalse(Path(f'/proc/{process.pid}').exists()); self.assertEqual(original, self.pin())
        result = json.loads(stdout)
        self.assertTrue(result['actualOperationOwner'] and result['actualParentProgram'] and result['originalBegin'])
        self.assertTrue(result['markerRetained']); self.assertEqual(fault == 'duplicate', result['duplicateRefused'])
        self.assertEqual(0, result['nativeReads']); self.assertEqual(0, result['normalInputs'])
        self.assertEqual(fault == 'actor-parser', result['actorParserRefused'])
        self.assertEqual(2 if fault == 'actor-parser' else None, result['actorExitCode'])
        self.assertEqual(fault == 'actor-parser', result['actualPublicAdmissionAttempted'])
        self.assertEqual(fault == 'holder-swap', result['holderSwapRefused'])
        self.assertFalse(result['completeProductionJourney'] or result['nativeQualified'])
        sources = json.loads((root/'child-source-pins.json').read_text())
        self.assertTrue(sources['currentSHA8']); self.assertEqual(sources['before'], sources['after'])
        self.assertGreater(len(sources['after']), 100)
        for name, expected in sources['after'].items():
            p = Path(name); s = p.lstat()
            self.assertEqual(expected, dict(sha256=hashlib.sha256(p.read_bytes()).hexdigest(),
                physical=[s.st_dev,s.st_ino,s.st_mode,s.st_uid,s.st_nlink,s.st_size,s.st_mtime_ns,s.st_ctime_ns]))
        (root/'entry-source-pin.json').write_text(json.dumps(original))

    def pin(self):
        s = ENTRY.lstat()
        return dict(sha256=hashlib.sha256(ENTRY.read_bytes()).hexdigest(),
            physical=[s.st_dev,s.st_ino,s.st_mode,s.st_uid,s.st_nlink,s.st_size,s.st_mtime_ns,s.st_ctime_ns])


if __name__ == '__main__': unittest.main()
