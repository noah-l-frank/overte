"""Offline real patch application; Qt compilation and runtime are unverified."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from ios import verify_qt_qml_source_patch as checker


class QtQmlSourcePatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        value = os.environ.get('OVERTE_QT_SOURCE_REFERENCE_ROOT')
        if not value:
            raise unittest.SkipTest('Explicit reviewed Qt source references are required; no download/build fallback')
        cls.source = Path(value).resolve(strict=True)
        cls.manifest = json.loads(checker.MANIFEST.read_text())

    def setUp(self):
        # Retain source/negative corpora and reports; these are small source files.
        self.root = Path(tempfile.mkdtemp(prefix='qt-qml-patch-test-', dir=checker.REPO / '.ios-host-tmp'))
        self.root.chmod(0o700)

    def test_real_private_application_preserves_references_and_cannot_claim_native_qualification(self):
        names = self.manifest['sourceSha256'] | self.manifest['referenceSha256']
        before = {name: checker.original(self.source / name) for name in names}
        report_path = checker.verify(self.source, self.root)
        report = json.loads(report_path.read_text())
        self.assertTrue(report['privateApplicationChecked'])
        self.assertTrue(report['reverseApplicationChecked'])
        self.assertTrue(report['sourceOriginalsUnchanged'])
        self.assertEqual(18, len(report['appliedSha256']))
        self.assertEqual(checker.REVIEWED_SOURCE_PATHS, set(self.manifest['sourceSha256']))
        self.assertEqual(checker.REVIEWED_REFERENCE_PATHS, set(self.manifest['referenceSha256']))
        self.assertEqual(set(names), set(report['appliedSha256']))
        self.assertFalse(report['runtimeApiVerified'])
        self.assertFalse(report['nativeCompilationVerified'])
        self.assertFalse(report['deviceQualified'])
        self.assertEqual(before, {name: checker.original(self.source / name) for name in names})

    def test_changed_qt_source_is_rejected_before_scratch_or_git_mutations(self):
        copied = self.root / 'foreign-reference'
        for name in self.manifest['sourceSha256'] | self.manifest['referenceSha256']:
            target = copied / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((self.source / name).read_bytes())
        changed = copied / next(iter(self.manifest['sourceSha256']))
        changed.write_bytes(changed.read_bytes() + b'\n// Different Qt source, never admitted.\n')
        before = set(self.root.rglob('*'))
        with patch.object(checker.subprocess, 'run', side_effect=AssertionError('Unknown Qt source must not reach git')):
            with self.assertRaisesRegex(ValueError, 'differs from its reviewed SHA-256'):
                checker.verify(copied, self.root)
        self.assertEqual(before, set(self.root.rglob('*')))

    def test_external_scratch_directory_cannot_receive_files_or_git_commands(self):
        with patch.object(checker.subprocess, 'run', side_effect=AssertionError('External scratch must not reach git')):
            with self.assertRaisesRegex(ValueError, 'Scratch writes must stay inside'):
                checker.verify(self.source, checker.REPO.parent)
        self.assertEqual([], list(self.root.iterdir()))


if __name__ == '__main__':
    unittest.main()
