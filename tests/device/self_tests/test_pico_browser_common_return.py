"""Actual short process/export/return; Common and native are declared models."""
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
import uuid

from adapters.normal_ui import NativeUIError
from adapters.normal_feature_state import PrivateFeatureState
from adapters.pico4.lifecycle_process_file import LifecycleProcessFile
from adapters.pico4.browser_common_process import OriginalBrowserRunnerProcess
from adapters.pico4.browser_common_return import OriginalBrowserConsumptionReturn, UNRESOLVED
from self_tests.test_feature_journeys import RUN


class BrowserCommonReturnTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='pico-common-return-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name); self.root.chmod(0o700)
        self.nonce = uuid.uuid4().hex
        self.entry = Path(__file__).with_name('pico_browser_common_worker.py').resolve()
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1',
            OVT_COMMON_MODEL_ROOT=str(self.root), OVT_COMMON_MODEL_NONCE=self.nonce)
        self.worker = subprocess.Popen([sys.executable, str(self.entry), '--area', 'tablet-web'],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, env=env)
        self.owner = self.result = None
        self.expected_export_complete = True
        self.expected_close = True
        self.addCleanup(self.finish)
        ready = json.loads(self.worker.stdout.readline(65538))
        self.assertTrue(ready['ready']); self.sources_before = ready['sources']
        fields = Path(f'/proc/{self.worker.pid}/stat').read_text().rsplit(')', 1)[1].split()
        identity = str(self.worker.pid) + ':' + fields[19] + ':' + Path('/proc/sys/kernel/random/boot_id').read_text().strip()
        self.owner = OriginalBrowserRunnerProcess(identity, self.entry, self.root,
            hashlib.sha256(Path(f'/proc/{self.worker.pid}/exe').read_bytes()).hexdigest(),
            hashlib.sha256(self.entry.read_bytes()).hexdigest(), self.owned)
        self.worker.stdin.write('begin\n'); self.worker.stdin.flush()
        self.request = json.loads(self.worker.stdout.readline(65538))['request']
        self.url = f'http://controlled.test/feature-fixture/v1/runs/{RUN}/'

    def owned(self, pid):
        return pid == self.worker.pid and self.worker.poll() is None

    def finish(self):
        # Only the actual child created by this test receives any stdin command.
        # Negative return tests still acknowledge transport receipt explicitly;
        # this is not a feature success or a repaired receiver.
        if self.worker.poll() is None:
            reply = dict(journeyConsumptionReceivedVersion=2,
                **{key:self.request[key] for key in ('nonce', 'recordSha256', 'commonSha256')})
            self.worker.stdin.write(json.dumps(reply) + '\n'); self.worker.stdin.flush()
            completed = json.loads(self.worker.stdout.readline(65538))
            self.assertIs(self.expected_export_complete, completed['completed'])
            self.assertIs(not self.expected_export_complete, completed['failed'])
            self.assertEqual(self.sources_before, completed['sources'])
            self.worker.stdin.write('stop\n'); self.worker.stdin.flush()
        self.worker.wait(timeout=5)
        error = self.worker.stderr.read()
        self.assertEqual(0, self.worker.returncode, error)
        for stream in (self.worker.stdin, self.worker.stdout, self.worker.stderr): stream.close()
        with self.assertRaises(FileNotFoundError): Path(f'/proc/{self.worker.pid}/stat').read_bytes()
        if self.result is not None: self.assertEqual(self.expected_close, self.result.close_host())
        if self.owner is not None: self.assertTrue(self.owner.close())
        for receiver in tuple(UNRESOLVED):
            if receiver.producer is self.owner:
                self.assertEqual(self.expected_close, receiver.close_host()); UNRESOLVED.remove(receiver)

    def receive(self, request=None):
        self.result = OriginalBrowserConsumptionReturn(self.owner, self.request if request is None else request,
            RUN, self.url, self.nonce, lambda: None)
        return self.result

    def test_actual_live_export_returns_exact_raw_and_all_historical_witness_samples(self):
        result = self.receive()
        self.assertTrue(result.guard())
        self.assertEqual(result.record['commonRaw'].encode('utf-8'), result.common_raw)
        self.assertEqual(self.request['commonSha256'], hashlib.sha256(result.common_raw).hexdigest())
        self.assertTrue(result.record['journey']['samples'])
        self.assertTrue(all('witness' in row for row in result.record['journey']['samples']))
        self.assertEqual(self.request['recordSha256'], result.receipt()['recordSha256'])

    def test_same_bytes_root_replacement_before_initial_receipt_refuses_original_stamp(self):
        path = self.root / self.request['name']
        replacement = self.root / 'foreign-root.json'
        replacement.write_bytes(path.read_bytes()); replacement.chmod(0o600)
        path.rename(self.root / 'retained-original-root.json'); replacement.rename(path)
        self.expected_export_complete = False
        with self.assertRaises(NativeUIError): self.receive()

    def test_same_bytes_child_replacement_before_initial_read_cannot_be_adopted(self):
        path = self.root / (self.request['name'] + '.frame-000.json')
        replacement = self.root / 'foreign-child.json'
        replacement.write_bytes(path.read_bytes()); replacement.chmod(0o600)
        path.rename(self.root / 'retained-original-child.json'); replacement.rename(path)
        self.expected_export_complete = False
        with self.assertRaises(NativeUIError): self.receive()

    def test_current_original_bytes_are_rechecked_and_failure_cannot_resume(self):
        result = self.receive()
        self.expected_export_complete = False
        path = self.root / (self.request['name'] + '.frame-000.json')
        raw = path.read_bytes(); path.write_bytes(raw + b' ')
        with self.assertRaises(NativeUIError): result.guard()
        path.write_bytes(raw)
        with self.assertRaises(NativeUIError): result.guard()

    def test_remote_uncompressed_pin_capacity_refuses_before_any_child_read(self):
        request = dict(self.request, chunkPins=dict(self.request['chunkPins'], bytes=16*1024*1024))
        with self.assertRaises(NativeUIError): self.receive(request)

    def test_mutable_historical_projection_cannot_replace_json_lists_with_tuples(self):
        result = self.receive()
        samples = result.record['journey']['samples']
        result.record['journey']['samples'] = tuple(samples)
        with self.assertRaises(NativeUIError): result.guard()
        result.record['journey']['samples'] = samples
        with self.assertRaises(NativeUIError): result.guard()

    def test_foreign_same_inode_holder_is_not_closed_or_adopted_by_retirement(self):
        result = self.receive(); original = result.file
        foreign = LifecycleProcessFile(PrivateFeatureState(result.store.path))
        result.file = foreign; self.expected_close = False
        try:
            with self.assertRaises(NativeUIError): result.guard()
            self.assertFalse(result.close_host())
            original.guard(); foreign.guard()
            self.assertFalse(original.file.closed); self.assertFalse(foreign.file.closed)
        finally:
            self.assertTrue(foreign.close_host()); self.assertTrue(original.close_host())


if __name__ == '__main__':
    unittest.main()
