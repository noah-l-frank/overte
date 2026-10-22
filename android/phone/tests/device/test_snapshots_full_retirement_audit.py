"""Adversarial full Snapshot retirement through the actual public facade.

Only native/render/Android sources use the explicit host target producers.
TLS, normal inputs, provider bodies, actor process/quiet, archives and unlinks
remain real. This is host composition evidence, not device qualification.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

import test_snapshots_feature_journey as journey

from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from overte_phone_script_history import unpack
from overte_phone_snapshots_retirement import NAMES, terminated


class FullRetirementAuditTests(unittest.TestCase):
    SDK = 29
    invoke = journey.SnapshotJourneyTests.invoke
    act = journey.SnapshotJourneyTests.act
    start_actor = journey.SnapshotJourneyTests.start_actor
    actor_ok = journey.SnapshotJourneyTests.actor_ok

    @classmethod
    def setUpClass(cls):
        journey.SnapshotJourneyTests.setUpClass.__func__(cls)

    @classmethod
    def tearDownClass(cls):
        journey.SnapshotJourneyTests.tearDownClass.__func__(cls)

    def setUp(self):
        # The reusable setup installs HostOnlyBoundary before any target or
        # fixture setup; its fresh actor does the same before constructing SDKs.
        # Only this fixture uses existing tmpfs. All actual fsync/inode checks
        # remain enabled; global TMPDIR and source deadlines stay unchanged.
        with patch.object(tempfile, 'tempdir', '/tmp'):
            journey.SnapshotJourneyTests.setUp(self)

    def cleanup_public(self):
        return self.invoke('feature.snapshots.cleanup',
                           dict(contractVersion=journey.VERSION, runId=journey.RUN))

    def normal_cleanup(self):
        self.client.activate('c' * 32)
        self.invoke('feature.snapshots.observe',
                    dict(contractVersion=journey.VERSION, runId=journey.RUN, afterSequence=0))
        self.act('open')
        self.act('capture', dict(mode='still', format='png'))
        self.act('save')
        self.act('upload')
        self.assertEqual(1, self.service.snapshot(journey.RUN, os.urandom(16).hex())['stories'])
        self.assertTrue(any(path.exists() for path in self.model.os_files.values()))
        self.client.activate('d' * 32, 'cleanup', {})
        self.assertEqual({'performed': True}, self.cleanup_public())
        self.assertEqual(0, self.service.snapshot(journey.RUN, os.urandom(16).hex())['stories'])
        self.assertTrue(all(not path.exists() for path in self.model.os_files.values()))
        owner = PrivateFeatureState(self.root / 'phone-snapshots-feature.json').read()
        self.assertFalse(unpack(owner['payload'])[0]['partial'])
        self.assertEqual('cleaned', unpack(owner['payload'])[0]['phase'])

    def close_with_original_actor(self):
        self.start_actor()
        deadline = time.monotonic() + 30
        while not self.client.request('/runs/' + journey.RUN)['entries']:
            self.actor_ok()
            self.assertLess(time.monotonic(), deadline)
            time.sleep(.1)
        header = PrivateFeatureState(self.root / 'phone-snapshots-actor-lifecycle.json').read()
        state = unpack(header['payload'])[0]
        self.assertTrue(state['quiet']['complete'])
        self.assertIsNone(state['partialClosure'])
        self.client.close()
        _, error = self.actor.communicate(timeout=30)
        self.assertEqual(0, self.actor.returncode, error[-5000:])
        header = PrivateFeatureState(self.root / 'phone-snapshots-actor-lifecycle.json').read()
        state = unpack(header['payload'])[0]
        self.assertEqual('retired', state['phase'])
        self.assertTrue(terminated(state['process']))
        return state

    def assert_controls_retained(self):
        self.assertIsNotNone(PrivateFeatureState(self.root / 'phone-snapshots-feature.json').read())
        self.assertFalse(list(self.root.glob('emote-frame-snapshots-retirement-*.json')))

    def test_full_public_finalize_requires_original_quiet_exit_and_is_repeatable(self):
        self.normal_cleanup()
        self.close_with_original_actor()
        self.assertEqual({'performed': True}, self.cleanup_public())
        archives = list(self.root.glob('emote-frame-snapshots-retirement-*.json'))
        self.assertEqual(1, len(archives))
        original = (archives[0].stat().st_ino, hashlib.sha256(archives[0].read_bytes()).hexdigest())
        self.assertTrue(all(PrivateFeatureState(self.root / name).read() is None for name in NAMES))
        self.assertEqual({'performed': True}, self.cleanup_public())
        self.assertEqual(original, (archives[0].stat().st_ino, hashlib.sha256(archives[0].read_bytes()).hexdigest()))

    def test_actual_late_owned_file_blocks_full_finalize_and_is_not_deleted(self):
        self.normal_cleanup()
        self.close_with_original_actor()
        prefix = self.model.producer.body['plans'][-1]['prefix']
        late = self.model.producer.directory / (prefix + '-late.png')
        # Hold a real host FD for the late namespace member. The producer
        # performs its original directory scan; no pending/closed DTO is edited.
        with late.open('wb+') as stream:
            stream.write(self.model.raw_png)
            stream.flush()
            os.fsync(stream.fileno())
            before = (late.stat().st_ino, late.read_bytes())
            with self.assertRaises(NativeUIError):
                self.cleanup_public()
            self.assertEqual(before, (late.stat().st_ino, late.read_bytes()))
            self.assertEqual(before[0], os.fstat(stream.fileno()).st_ino)
            self.assertFalse(stream.closed)
        self.assert_controls_retained()

    def test_actual_retired_actor_process_must_exit_before_any_archive_or_unlink(self):
        self.normal_cleanup()
        configuration = self.root / 'held-actor-configuration.json'
        PrivateFeatureState(configuration).write(dict(targetUrl=self.proxy.url, root=str(self.root),
            fixtureUrl=self.base, actorToken='a' * 64), None)
        # Hold only the actual process exit after unchanged Actor.step has
        # retired. Its journals, proof, source reads and quiet are untouched.
        exit_statement = 'if flow.step():sys.exit(0)'
        self.assertEqual(1, journey.ACTOR.count(exit_statement))
        program = journey.ACTOR.replace(
            exit_statement,
            "if flow.step():\n"
            "            sys.stdin.readline()\n            sys.exit(0)")
        self.assertNotEqual(journey.ACTOR, program)
        self.actor = subprocess.Popen([sys.executable, '-c', program, json.dumps(sys.path), str(configuration)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        def stop():
            if self.actor.poll() is None:
                self.actor.terminate()
            self.actor.communicate(timeout=5)
        self.addCleanup(stop)
        deadline = time.monotonic() + 30
        while not self.client.request('/runs/' + journey.RUN)['entries']:
            self.actor_ok()
            self.assertLess(time.monotonic(), deadline)
            time.sleep(.1)
        self.client.close()
        store = PrivateFeatureState(self.root / 'phone-snapshots-actor-lifecycle.json')
        while unpack(store.read()['payload'])[0]['phase'] != 'retired':
            self.actor_ok()
            self.assertLess(time.monotonic(), deadline)
            time.sleep(.1)
        process = unpack(store.read()['payload'])[0]['process']
        self.assertEqual(self.actor.pid, process['pid'])
        self.assertFalse(terminated(process))
        sampled_alive = threading.Event()
        results, errors = [], []
        def actual_process_check(value):
            answer = terminated(value)
            if value == process and not answer:
                sampled_alive.set()
            return answer
        def finalize():
            try:
                results.append(self.cleanup_public())
            except Exception as error:
                errors.append(error)
        with patch('overte_phone_snapshots_retirement.terminated', actual_process_check):
            thread = threading.Thread(target=finalize)
            thread.start()
            try:
                self.assertTrue(sampled_alive.wait(10))
                self.assertTrue(thread.is_alive())
                self.assertEqual([], results)
                self.assertEqual([], errors)
                self.assert_controls_retained()
            finally:
                self.actor.stdin.write('\n')
                self.actor.stdin.flush()
                _, error = self.actor.communicate(timeout=5)
                thread.join(30)
        self.assertEqual(0, self.actor.returncode, error[-5000:])
        self.assertFalse(thread.is_alive())
        self.assertEqual([], errors)
        self.assertEqual([{'performed': True}], results)

    def test_actual_foreign_child_header_blocks_full_finalize_and_is_preserved(self):
        self.normal_cleanup()
        self.close_with_original_actor()
        child = PrivateFeatureState(self.root / 'phone-snapshots-actor-originals.json')
        original = child.read()
        foreign = deepcopy(original)
        foreign['runId'] = 'a' * 32
        self.assertNotEqual(original['runId'], foreign['runId'])
        child.write(foreign, original)
        with self.assertRaises(NativeUIError):
            self.cleanup_public()
        self.assertEqual(foreign, child.read())
        self.assert_controls_retained()

    def test_actual_child_unlink_interruption_resumes_from_immutable_full_archive(self):
        self.normal_cleanup()
        self.close_with_original_actor()
        discarded = []
        real_discard = PrivateFeatureState.discard

        def interrupt(store, previous):
            real_discard(store, previous)
            if store.path == self.root / 'phone-snapshots-primary-originals.json':
                discarded.append(store.path)
                raise OSError('Explicit host interruption after actual child unlink')

        with patch.object(PrivateFeatureState, 'discard', interrupt):
            with self.assertRaises(NativeUIError):
                self.cleanup_public()
        self.assertEqual([self.root / 'phone-snapshots-primary-originals.json'], discarded)
        self.assertFalse(discarded[0].exists())
        self.assertIsNotNone(PrivateFeatureState(self.root / 'phone-snapshots-feature.json').read())
        retirement = PrivateFeatureState(self.root / 'phone-snapshots-retirement.json').read()
        self.assertEqual('retiring', unpack(retirement['payload'])[0]['phase'])
        archives = list(self.root.glob('emote-frame-snapshots-retirement-*.json'))
        self.assertEqual(1, len(archives))
        immutable = (archives[0].stat().st_ino, archives[0].read_bytes())
        self.assertEqual({'performed': True}, self.cleanup_public())
        self.assertEqual({'performed': True}, self.cleanup_public())
        self.assertEqual(immutable, (archives[0].stat().st_ino, archives[0].read_bytes()))
        self.assertTrue(all(PrivateFeatureState(self.root / name).read() is None for name in NAMES))
        self.assertIsNone(PrivateFeatureState(self.root / 'phone-snapshots-retirement.json').read())


if __name__ == '__main__':
    unittest.main()
