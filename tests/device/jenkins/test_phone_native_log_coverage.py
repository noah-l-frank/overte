#!/usr/bin/env python3
"""Host-only counterexamples for complete bounded native timeline publication."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import phone_native_log_coverage as coverage
import phone_worker as worker


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


class NativeCoverageTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.root = self.base / 'debug-hold'
        self.root.mkdir(mode=0o700)
        self.rows = []
        for number in (1, 2):
            raw = (json.dumps({'sequence': number, 'epochNs': number * 1000}) + '\n').encode()
            self.write(coverage.FILES[number], raw)
            self.rows.append({'schemaVersion': 1, 'part': number, 'file': coverage.FILES[number],
                              'bytes': len(raw), 'sha256': sha(raw), 'closed': number == 1,
                              'contextSha256': 'a' * 64, 'sourceSha256': 'b' * 64,
                              'first': {'sequence': number}, 'last': {'sequence': number}})
        self.write_index()

    def write(self, name, raw):
        path = self.root / name
        path.write_bytes(raw)
        path.chmod(0o600)
        return path

    def write_index(self):
        return self.write(coverage.INDEX, b''.join((json.dumps(row) + '\n').encode() for row in self.rows))

    def test_valid_readonly_prefix_coverage_and_owned_append(self):
        before = {path.name: path.read_bytes() for path in self.root.iterdir()}
        baseline = coverage.check(root=self.root)
        self.assertEqual(before, {path.name: path.read_bytes() for path in self.root.iterdir()})
        extra = (json.dumps({'sequence': 3, 'epochNs': 3000}) + '\n').encode()
        path = self.root / coverage.FILES[2]
        with path.open('ab') as stream:
            stream.write(extra)
        row = copy.deepcopy(self.rows[-1])
        row.update(bytes=path.stat().st_size, sha256=sha(path.read_bytes()), last={'sequence': 3})
        with (self.root / coverage.INDEX).open('ab') as stream:
            stream.write((json.dumps(row) + '\n').encode())
        result = coverage.check(baseline, require_headroom=False, root=self.root)
        self.assertEqual(result['activePart'], 2)
        self.assertEqual(result['parts']['2']['bytes'], path.stat().st_size)

    def test_part9_or_missing_part_is_rejected_instead_of_silently_omitted(self):
        baseline = coverage.check(root=self.root)
        path = self.write('MEMORY_TIMELINE.part-000009.private.jsonl', b'{"sequence":3}\n')
        with self.assertRaisesRegex(ValueError, 'PART_SET_UNCOVERED'):
            coverage.check(baseline, root=self.root)
        path.unlink()
        (self.root / coverage.FILES[1]).unlink()
        with self.assertRaisesRegex(ValueError, 'PART_SET_UNCOVERED'):
            coverage.check(baseline, root=self.root)

    def test_index_hash_corruption_and_in_place_prefix_rewrite_are_rejected(self):
        baseline = coverage.check(root=self.root)
        original = (self.root / coverage.FILES[1]).read_bytes()
        self.write(coverage.FILES[1], original.replace(b'1000', b'1001'))
        with self.assertRaisesRegex(ValueError, 'INDEX_PREFIX_HASH_MISMATCH'):
            coverage.check(root=self.root)
        self.rows[0]['sha256'] = sha((self.root / coverage.FILES[1]).read_bytes())
        self.write_index()
        with self.assertRaisesRegex(ValueError, 'BASELINE_PREFIX_CHANGED'):
            coverage.check(baseline, root=self.root)

    def binding(self, publish):
        private = self.base / 'private'
        private.mkdir()
        source = HERE.parents[2]
        script = source / 'tests/device/jenkins/phone_native_log_coverage.py'
        streams = {'native-memory': {'path': str(self.root / coverage.FILES[1]),
                                     'scopeRoot': str(self.base), 'kind': 'memory'}}
        for number, name in coverage.FILES.items():
            if number != 1:
                streams['part-' + str(number)] = {'path': str(self.root / name),
                                                  'scopeRoot': str(self.base), 'kind': 'memory'}
        streams['index'] = {'path': str(self.root / coverage.INDEX), 'scopeRoot': str(self.base), 'kind': 'text'}
        policy = SimpleNamespace(root=private, context='c' * 64, config={
            'domainRequiredModules': ['domain-enter'], 'publicLogStreams': streams,
            'nativeLogCoverage': {'path': str(script), 'sha256': sha(script.read_bytes()), 'root': str(self.root)}},
            publish_full_logs=publish)
        admission = SimpleNamespace(source=source, plan={'moduleIds': ['launch-smoke', 'domain-enter']},
                                    inventory={'tests/device/jenkins/phone_native_log_coverage.py': sha(script.read_bytes())})
        return admission, policy

    def test_publication_is_checked_before_and_after_without_stopping_producer(self):
        def publish():
            self.write('MEMORY_TIMELINE.part-000009.private.jsonl', b'{"sequence":3}\n')
        admission, policy = self.binding(publish)
        guard = worker.install_native_log_guard(admission, policy)
        guard()
        self.assertTrue((policy.root / 'native-log-coverage-before.private.json').is_file())
        with self.assertRaisesRegex(ValueError, 'PART_SET_UNCOVERED'):
            policy.publish_full_logs()
        self.assertTrue((self.root / 'MEMORY_TIMELINE.part-000009.private.jsonl').exists())
        self.assertFalse((policy.root / 'native-log-coverage-publication.private.json').exists())

    def test_wrong_index_projection_or_part_scope_rejected_before_publication(self):
        calls = []
        admission, policy = self.binding(lambda: calls.append('published'))
        policy.config['publicLogStreams']['index']['kind'] = 'memory'
        with self.assertRaisesRegex(worker.WorkerError, 'STREAM_SCHEMA'):
            worker.install_native_log_guard(admission, policy)
        with self.assertRaisesRegex(worker.WorkerError, 'GUARD_NOT_ADMITTED'):
            policy.publish_full_logs()
        self.assertEqual(calls, [])
        policy.config['publicLogStreams']['index']['kind'] = 'text'
        policy.config['publicLogStreams']['part-2']['scopeRoot'] = str(self.root)
        with self.assertRaisesRegex(worker.WorkerError, 'STREAM_SCHEMA'):
            worker.install_native_log_guard(admission, policy)


if __name__ == '__main__':
    unittest.main()
