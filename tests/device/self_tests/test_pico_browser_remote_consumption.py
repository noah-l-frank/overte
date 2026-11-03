"""Actual Common producer/Actor return and existing Browser retirement graph.

OpenXR, native/Qt/GPU and native clocks are declared source models. This is a
short Open/Close component, not the whole 26-action Common feature recipe.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import hashlib
import json
import os
from pathlib import Path
import select
import subprocess
import sys
import unittest
import uuid
from unittest.mock import patch

from adapters.normal_ui import NativeUIError
from adapters.pico4.browser_common_process import OriginalBrowserRunnerProcess
from adapters.pico4.browser_common_return import OriginalBrowserConsumptionReturn
from adapters.pico4.browser_remote_consumption import PicoBrowserRemoteCleanupConsumption
from feature_journeys.scenarios import VERSION
from self_tests import test_pico_browser_directory_archive as directory


class BrowserRemoteConsumptionTests(unittest.TestCase):
    def read(self):
        self.assertTrue(select.select([self.common.stdout], [], [], 10)[0])
        raw = self.common.stdout.readline(4*1024*1024+1)
        self.assertTrue(raw, self.common.stderr.read(16384) if self.common.poll() is not None else '')
        return json.loads(raw)

    def send(self, value):
        self.common.stdin.write(json.dumps(value) + '\n'); self.common.stdin.flush()

    def test_original_common_return_joins_same_primary_actor_capture_archive_and_actual_host_close(self):
        self.component()

    def test_changed_primary_original_refuses_consumption_without_capture_query_or_replay(self):
        self.component(fault='primary-original')

    def test_unknown_consumption_cas_retains_reading_intent_without_redelivery(self):
        self.component(fault='consumption-cas')

    def component(self, *, fault=None):
        fixture = directory.PicoBrowserDirectoryArchiveTests('runTest')
        case = fixture.make(); self.addCleanup(fixture.doCleanups)
        f = case.f
        entry = Path(__file__).with_name('pico_browser_common_worker.py').resolve()
        nonce = uuid.uuid4().hex
        environment = dict(os.environ, PYTHONDONTWRITEBYTECODE='1',
            OVT_COMMON_MODEL_ROOT=str(f.artifacts), OVT_COMMON_MODEL_NONCE=nonce,
            OVT_COMMON_MODEL_RPC='cleanup', OVT_COMMON_MODEL_RUN=f.run, OVT_COMMON_MODEL_URL=f.fixture_url)
        self.common = subprocess.Popen([sys.executable, str(entry), '--area', 'tablet-web'],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=environment)
        self.addCleanup(self.close_common)
        ready = self.read(); self.assertTrue(ready['ready'])
        fields = Path(f'/proc/{self.common.pid}/stat').read_text().rsplit(')', 1)[1].split()
        identity = str(self.common.pid) + ':' + fields[19] + ':' + Path('/proc/sys/kernel/random/boot_id').read_text().strip()
        process = OriginalBrowserRunnerProcess(identity, entry, f.artifacts,
            hashlib.sha256(Path(f'/proc/{self.common.pid}/exe').read_bytes()).hexdigest(),
            hashlib.sha256(entry.read_bytes()).hexdigest(), lambda pid:pid == self.common.pid and self.common.poll() is None)
        self.addCleanup(process.close)
        f.activate(); f.primary.prepare(); case.observe(); case.command('publish', 'publication')
        f.act('open'); case.observe(); case.command('publish', 'publication')
        f.act('close'); case.observe(); case.command('publish', 'publication')
        ticket = f.activate('cleanup'); f.primary.cleanup(dict(contractVersion=VERSION, runId=f.run))
        slot = PicoBrowserRemoteCleanupConsumption(f.primary); f.primary.cleanup_consumption = slot
        self.send(dict(ticket=ticket, barrier=f.clock.epoch(), started=0))
        while True:
            value = self.read()
            if 'request' in value:
                request = value['request']; break
            self.assertEqual({'rpc', 'fields'}, set(value)); operation = value['rpc']; fields = value['fields']
            if operation == 'invoke':
                self.assertEqual('feature.tablet-web.observe', fields['operation'])
                result = f.primary.observe(fields['fields'])
            elif operation == 'witness':
                case.command('publish', 'publication'); result = f.client.observe()
            elif operation == 'monotonic': result = f.clock.now()
            elif operation == 'epoch': result = f.clock.epoch()
            elif operation == 'sleep': result = f.clock.sleep(fields)
            else: self.fail('Undeclared source-model RPC')
            self.send(dict(result=result))
        returned = OriginalBrowserConsumptionReturn(process, request, f.run, f.fixture_url, nonce, lambda:None)
        self.addCleanup(returned.close_host)
        if fault is not None:
            if fault == 'primary-original':
                path = f.primary.history_cache.chunks.store(0).path
                replacement = path.with_name('retained-foreign-primary.json')
                replacement.write_bytes(path.read_bytes()); replacement.chmod(0o600)
                path.rename(path.with_name('retained-original-primary.json')); replacement.rename(path)
            original_write = slot.store.write
            def unknown(value, previous):
                original_write(value, previous)
                raise OSError('Declared lost consumption CAS return')
            with patch.object(slot.store, 'write', side_effect=unknown) if fault == 'consumption-cas' else patch.object(
                    slot.store, 'write', wraps=original_write):
                with self.assertRaises(NativeUIError): slot.consume(returned)
            self.assertTrue(slot.failed); self.assertFalse(slot.complete); self.assertEqual([], case.batches)
            if fault == 'consumption-cas': self.assertEqual('reading', slot.store.read()['phase'])
            else: self.assertIsNone(slot.store.read())
            with self.assertRaises(NativeUIError): slot.consume(returned)
            self.common.stdin.close()
            completed = self.read(); self.assertFalse(completed['completed']); self.assertTrue(completed['failed'])
            self.common.wait(timeout=5); self.assertEqual(1, self.common.returncode)
            return
        reply = slot.consume(returned)
        self.assertTrue(slot.complete); self.assertFalse(slot.receipt()['header']['sequenceSucceeded'])
        self.assertEqual(2, slot.receipt()['picoBrowserCleanupConsumptionVersion'])
        self.send(reply); completed = self.read()
        self.assertTrue(completed['completed'], completed)
        self.assertFalse(completed['failed']); self.assertEqual(ready['sources'], completed['sources'])
        f.client.close(); actor = case.consume_original_return()
        captures = f.primary.retire_returned_actor_captures(actor)
        self.assertEqual(3, captures['picoBrowserRemoteCaptureRetirementVersion'])
        self.assertFalse(captures['commonSequenceSucceeded'])
        capture = f.primary.remote_capture_retirement
        self.assertTrue(any(row['store'].path == returned.store.path for row in capture.catalog.rows.values()))
        f.primary.archive_retired_sources(directory_retirement=True)
        closed = f.primary.close_archived_host()
        self.assertTrue(closed['hostReleased']); self.assertFalse(closed['commonSequenceSucceeded'])
        self.assertTrue(all(owner.closed and not owner.lost for owner in returned.original_holders[2:]))
        self.common.stdin.write('stop\n'); self.common.stdin.flush()
        self.common.wait(timeout=5); self.assertEqual(0, self.common.returncode, self.common.stderr.read())
        with self.assertRaises(FileNotFoundError): Path(f'/proc/{self.common.pid}/stat').read_bytes()
        self.assertTrue(actor.close_host())

    def close_common(self):
        if self.common.poll() is None:
            # Releasing only this test's owned source-model stdin lets its
            # actual worker finally close known handles; no success is inferred.
            self.common.stdin.close()
        self.common.wait(timeout=10)
        for stream in (self.common.stdin, self.common.stdout, self.common.stderr):
            if not stream.closed: stream.close()


if __name__ == '__main__':
    unittest.main()
