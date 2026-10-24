"""Real native file reader and host consumer; only HTTP/AFC/process are seams."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

DEVICE = Path(__file__).resolve().parents[2]
ROOT = DEVICE.parents[1]
sys.path.insert(0, str(DEVICE))
from adapters.normal_ui import NativeUIError
from ios.adapters import snapshot_files
from ios.adapters.appium_adapter import WebDriver, WebDriverRequestError
from snapshot_file_contract import CHUNK_BYTES, read_request


class FileBoundary:
    def __init__(self, binary, environment, directory, mutation=''):
        self.root = directory / 'Snapshots'; self.root.mkdir()
        self.artifacts = directory / 'artifacts'
        self.prefix = 'parity-0123456789abcdef-still-png'
        self.name = self.prefix + '-snap_123_1.png'
        self.content = bytes(range(256)) * 700
        (self.root / self.name).write_bytes(self.content)
        self.target = {'appId': 'org.example.client',
            'nativeUiObservation': {'kind': 'uikit-documents', 'version': 1},
            'testBuild': {'fixtureOrigin': 'http://controlled.invalid:49121', 'resultsDirectory': 'owned-results'}}
        self.reader = subprocess.Popen([str(binary), str(self.root)], env=environment,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
        self.pid, self.clock, self.mutation = self.reader.pid, 0.0, mutation
        self.requests, self.lists, self.reads, self.pulls = [], 0, 0, 0

    def close(self):
        self.reader.stdin.close(); self.reader.wait(timeout=5); self.reader.stdout.close()

    def process(self):
        return {'bundleId': self.target['appId'], 'pid': self.pid, 'foreground': True}

    def tick(self):
        self.clock += 1
        return self.clock

    def post(self, request, timeout):
        command = read_request(json.loads(request.data))
        self.requests.append(command)
        if command['operation'] == 'list':
            self.lists += 1
            if self.lists == 2:
                if self.mutation == 'changed-before-final-list':
                    (self.root / self.name).write_bytes(b'changed original')
                elif self.mutation == 'reservation-completed':
                    (self.root / self.name).write_bytes(self.content)
                elif self.mutation == 'companion-completed':
                    (self.root / (self.prefix + '-snap_123_1.gif')).write_bytes(b'original companion')
        else:
            self.reads += 1
            if self.mutation == 'native-read-failure':
                (self.root / self.name).unlink(missing_ok=True)
        self.reader.stdin.write(json.dumps(command) + '\n'); self.reader.stdin.flush()
        value = json.loads(self.reader.stdout.readline())
        if self.mutation == 'foreign-nonce': value['commandId'] = 'ios-' + 'f' * 32
        elif self.mutation == 'stale': value['sampleEpochMs'] -= 60000
        elif self.mutation == 'slow-immutable-byte-transfer': value['sampleEpochMs'] -= 5000
        elif self.mutation == 'ack-only': value = {'performed': True, 'commandId': command['commandId']}
        elif self.mutation == 'foreign-process': value['processId'] += 1
        elif self.mutation == 'cross-process': self.pid += 1
        elif self.mutation == 'extra-verdict': value['snapshotPassed'] = True
        elif self.mutation == 'forged-manifest-hash' and command['operation'] == 'list':
            value['files'][0]['sha256'] = 'a' * 64
        elif self.mutation == 'duplicate-file' and command['operation'] == 'list':
            value['files'].append(value['files'][0])
        elif command['operation'] == 'read' and value['ok']:
            if self.mutation == 'corrupt-chunk':
                content = bytearray(base64.b64decode(value['file']['data'])); content[0] ^= 1
                value['file']['data'] = base64.b64encode(content).decode()
            elif self.mutation == 'short-chunk': value['file']['data'] = base64.b64encode(b'short').decode()
            elif self.mutation == 'wrong-offset': value['file']['offset'] += 1
            elif self.mutation == 'wrong-revision': value['file']['revision'] = 'f' * 64
        self.receipt = value
        self.response = json.dumps(command).encode()
        return self

    status = 200
    def __enter__(self): return self
    def __exit__(self, *_): return False
    def read(self, size): return self.response[:size]

    def execute(self, session, operation, arguments):
        assert session == 'owned-session' and operation == 'mobile: pullFile'
        assert arguments == {'remotePath': '@org.example.client:documents/owned-results/ios-snapshot-file-result.json'}
        self.pulls += 1
        if self.mutation == 'first-receipt-not-ready' and self.pulls == 1 or self.mutation == 'persistent-read-error':
            raise WebDriverRequestError(500)
        if self.mutation == 'unknown-session': raise WebDriverRequestError(404)
        if self.mutation == 'malformed-receipt': return 'not base64'
        if self.mutation == 'oversize-receipt': return 'a' * (3 * CHUNK_BYTES + 1)
        return base64.b64encode(json.dumps(self.receipt).encode()).decode()

    def files(self):
        return snapshot_files.SnapshotFiles(self, 'owned-session', self.target, self.process,
            '11111111-2222-3333-4444-555555555555', self.artifacts,
            monotonic=self.tick, sleep=lambda _: None)


class OriginalSnapshotFiles(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = ROOT / 'ios/tests/ios-snapshot-files-test.py'
        spec = importlib.util.spec_from_file_location('_ios_snapshot_file_native_sdk_fixture', path)
        cls.native = importlib.util.module_from_spec(spec); spec.loader.exec_module(cls.native)
        cls.native.SnapshotFiles.setUpClass()

    @classmethod
    def tearDownClass(cls):
        cls.native.SnapshotFiles.tearDownClass()

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='ios-snapshot-original-consumer-')
        self.directory = Path(self.temporary.name)
        self.boundaries = []

    def tearDown(self):
        for boundary in self.boundaries: boundary.close()
        self.temporary.cleanup()

    def boundary(self, mutation=''):
        directory = self.directory / str(len(self.boundaries)); directory.mkdir(mode=0o700)
        cls = self.native.SnapshotFiles
        boundary = FileBoundary(cls.binary, cls.environment, directory, mutation)
        self.boundaries.append(boundary)
        return boundary

    def test_actual_native_multichunk_originals_publish_private_immutable_content_addressed_artifacts(self):
        boundary = self.boundary()
        boundary.content = bytes(range(256)) * 20000
        (boundary.root / boundary.name).write_bytes(boundary.content)
        with patch.object(snapshot_files, 'urlopen', boundary.post):
            files = boundary.files()
            result = files.files(boundary.prefix)
            self.assertEqual(len(result['files']), 1)
            row = result['files'][0]; path = boundary.artifacts / row['artifact']
            self.assertEqual(row['artifact'], path.name)
            self.assertEqual(row['basename'], boundary.name)
            self.assertEqual(path.read_bytes(), boundary.content)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            first_reads = boundary.reads
            self.assertGreater(first_reads, 1)
            self.assertEqual(files.files(boundary.prefix), result)
            self.assertEqual(boundary.reads, first_reads, 'unchanged original hashes may reuse verified private bytes')
            self.assertEqual(files.context['scope'], 'NATIVE_UI_COMPONENT_ONLY')
            self.assertNotIn('sourceRevision', files.context)
        self.assertEqual(set(command['operation'] for command in boundary.requests), {'list', 'read'})
        self.assertTrue(all('root' not in command and 'data' not in command for command in boundary.requests))

    def test_corrupt_stale_foreign_changed_partial_or_claimed_results_never_publish(self):
        for mutation in ('foreign-nonce', 'stale', 'ack-only', 'foreign-process', 'cross-process', 'extra-verdict',
                         'forged-manifest-hash', 'duplicate-file', 'corrupt-chunk', 'short-chunk', 'wrong-offset',
                         'wrong-revision', 'native-read-failure', 'changed-before-final-list',
                         'malformed-receipt', 'oversize-receipt', 'persistent-read-error'):
            boundary = self.boundary(mutation)
            with self.subTest(mutation=mutation), patch.object(snapshot_files, 'urlopen', boundary.post):
                with self.assertRaises((NativeUIError, WebDriverRequestError)):
                    boundary.files().files(boundary.prefix)
            self.assertEqual(list(boundary.artifacts.iterdir()), [])
            self.assertLessEqual(boundary.pulls, 16)

    def test_late_first_receipt_retries_only_reads_and_unknown_session_fails(self):
        boundary = self.boundary('first-receipt-not-ready')
        with patch.object(snapshot_files, 'urlopen', boundary.post):
            self.assertEqual(len(boundary.files().files(boundary.prefix)['files']), 1)
        self.assertEqual(boundary.pulls, len(boundary.requests) + 1)
        boundary = self.boundary('unknown-session')
        with patch.object(snapshot_files, 'urlopen', boundary.post), self.assertRaises(WebDriverRequestError):
            boundary.files().files(boundary.prefix)
        self.assertEqual(boundary.pulls, 1)

    def test_empty_reservation_may_complete_and_companion_may_arrive_on_later_poll(self):
        boundary = self.boundary('reservation-completed')
        (boundary.root / boundary.name).write_bytes(b'')
        with patch.object(snapshot_files, 'urlopen', boundary.post):
            files = boundary.files()
            first = files.files(boundary.prefix)
            self.assertEqual(len(first['files']), 1)
            self.assertEqual((boundary.artifacts / first['files'][0]['artifact']).read_bytes(), boundary.content)
            self.assertEqual(len(files.files(boundary.prefix)['files']), 1)
        boundary = self.boundary('companion-completed')
        with patch.object(snapshot_files, 'urlopen', boundary.post):
            files = boundary.files()
            self.assertEqual(len(files.files(boundary.prefix)['files']), 1)
            self.assertEqual(len(files.files(boundary.prefix)['files']), 2)

    def test_altered_shared_linked_or_foreign_local_artifacts_cannot_be_reused(self):
        for mutation in ('corrupt', 'symbolic', 'hard', 'shared'):
            boundary = self.boundary()
            with self.subTest(mutation=mutation), patch.object(snapshot_files, 'urlopen', boundary.post):
                files = boundary.files(); result = files.files(boundary.prefix)
                path = boundary.artifacts / result['files'][0]['artifact']
                if mutation == 'corrupt': path.write_bytes(b'altered')
                elif mutation == 'symbolic':
                    original = boundary.root.parent / 'foreign'; original.write_bytes(boundary.content)
                    path.unlink(); path.symlink_to(original)
                elif mutation == 'hard': os.link(path, boundary.root.parent / 'alias')
                else: path.chmod(0o644)
                with self.assertRaises(NativeUIError): files.files(boundary.prefix)

    def test_prefix_validation_precedes_any_transport_and_clock_cannot_rewind(self):
        boundary = self.boundary()
        with patch.object(snapshot_files, 'urlopen', boundary.post):
            files = boundary.files()
            for invalid in ('foreign', boundary.prefix + '\n', '../' + boundary.prefix):
                with self.subTest(prefix=invalid), self.assertRaises(ValueError): files.files(invalid)
            self.assertEqual(boundary.requests, [])
            files._now(); boundary.clock = -5
            with self.assertRaisesRegex(NativeUIError, 'clock'): files._now()

    def test_artifact_root_alias_or_shared_permissions_never_receive_original_bytes(self):
        for mutation in ('alias', 'shared'):
            boundary = self.boundary()
            with self.subTest(mutation=mutation), patch.object(snapshot_files, 'urlopen', boundary.post):
                files = boundary.files()
                if mutation == 'alias':
                    foreign = boundary.root.parent / 'foreign-artifacts'; foreign.mkdir(mode=0o700)
                    boundary.artifacts.rmdir(); boundary.artifacts.symlink_to(foreign, target_is_directory=True)
                else:
                    boundary.artifacts.chmod(0o755)
                with self.assertRaises(NativeUIError): files.files(boundary.prefix)
                self.assertEqual(boundary.requests, [])

    def test_stable_empty_original_remains_visible_to_precapture_freshness_checks(self):
        boundary = self.boundary()
        (boundary.root / boundary.name).write_bytes(b'')
        with patch.object(snapshot_files, 'urlopen', boundary.post):
            result = boundary.files().files(boundary.prefix)
        self.assertEqual(len(result['files']), 1)
        self.assertEqual((boundary.artifacts / result['files'][0]['artifact']).read_bytes(), b'')

    def test_large_original_fits_the_actual_probe_polling_and_webdriver_response_budgets(self):
        boundary = self.boundary()
        boundary.content = bytes(range(256)) * (25 * 1024 * 4)
        (boundary.root / boundary.name).write_bytes(boundary.content)
        with patch.object(snapshot_files, 'urlopen', boundary.post):
            result = boundary.files().files(boundary.prefix)
        self.assertEqual((boundary.artifacts / result['files'][0]['artifact']).read_bytes(), boundary.content)
        source = (DEVICE / 'probe/overte_e2e_probe.js').read_text()
        interval = int(re.search(r'var sampleIntervalMs = ([0-9]+);', source)[1]) / 1000
        # One sequential native request per actual probe poll. Small compressed
        # fixture images conceal the old >100s minimum for25MiB. Reserve half
        # the outer file deadline for actual byte transport/OS observations.
        self.assertLess(len(boundary.requests) * interval, 60)
        self.assertLess(3 * CHUNK_BYTES, WebDriver.MAX_RESPONSE_BYTES)
        print(f'Original25MiB: {len(boundary.requests)} native requests; '
              f'{len(boundary.requests) * interval:.2f}s minimum probe polling; '
              'actual original bytes verified, no device timing claim.')

    def test_immutable_byte_transfer_age_does_not_relax_focused_ui_freshness(self):
        from ios.adapters.normal_input import _fresh
        now = time.time() * 1000
        self.assertFalse(_fresh(now - 5000, now))
        self.assertTrue(snapshot_files._file_fresh(now - 5000, now))
        for value in (now - 16000, now + 2000, True, None, float('nan'), float('inf')):
            with self.subTest(value=value): self.assertFalse(snapshot_files._file_fresh(value, now))
        boundary = self.boundary('slow-immutable-byte-transfer')
        with patch.object(snapshot_files, 'urlopen', boundary.post):
            result = boundary.files().files(boundary.prefix)
        self.assertEqual((boundary.artifacts / result['files'][0]['artifact']).read_bytes(), boundary.content)


if __name__ == '__main__':
    unittest.main(verbosity=2)
