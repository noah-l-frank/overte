"""Actual private patch/reverse checks; native/runtime qualification stays false."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock

from ios import verify_qt_runnable_pool_source_patch as check


class QtRunnablePoolSourcePatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        value = os.environ.get('OVERTE_QT_CORE_POOL_SOURCE_REFERENCE_ROOT')
        if not value:
            raise unittest.SkipTest('Explicit reviewed QtCore references required; no download/build fallback')
        cls.source = Path(value).resolve(strict=True)
        cls.expected = json.loads(check.MANIFEST.read_text())['sourceSha256']
        if len(cls.expected)!=2:raise AssertionError('Exactly two reviewed Qt pool inputs required')

    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix='qt-runnable-pool-source-test-',
                                        dir=check.REPO / '.ios-host-tmp'))
        self.root.chmod(0o700)

    def test_actual_private_apply_reverse_preserves_two_originals(self):
        before = {name: check.original(self.source / name) for name in self.expected}
        report = json.loads(check.verify(self.source, self.root).read_text())
        for field in ('privateApplicationChecked', 'reverseApplicationChecked',
                      'exactReverseBytesRestored', 'sourceOriginalsUnchanged'):
            self.assertTrue(report[field])
        for field in ('nativeCompilationVerified', 'runtimeApiVerified', 'deviceQualified',
                      'admissionGenerationRuntimeVerified', 'selectedPoolCompletionVerified',
                      'globalPoolCompletionVerified',
                      'storageRetirementVerified'):
            self.assertFalse(report[field])
        self.assertEqual(2,len(report['originalSha256']))
        self.assertEqual(before, {name: check.original(self.source / name) for name in self.expected})

    def test_unknown_source_rejects_before_result_creation_or_git(self):
        copied = self.root / 'unknown-source'
        for name in self.expected:
            path = copied / name
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(self.source / name, path)
        with (copied / next(iter(self.expected))).open('ab') as stream:
            stream.write(b'\n// deliberately unknown source\n')
        scratch = self.root / 'empty-scratch'
        scratch.mkdir()
        with mock.patch.object(check.subprocess, 'run', side_effect=AssertionError('git forbidden')):
            with self.assertRaisesRegex(ValueError, 'Unknown Qt source'):
                check.verify(copied, scratch)
        self.assertEqual(list(scratch.iterdir()), [])

    def test_outside_scratch_rejects_before_git_or_source_copy(self):
        with mock.patch.object(check.subprocess, 'run', side_effect=AssertionError('git forbidden')):
            with self.assertRaisesRegex(ValueError, 'Scratch writes'):
                check.verify(self.source, check.REPO)
        self.assertEqual(list(self.root.iterdir()), [])


if __name__ == '__main__':
    unittest.main()
