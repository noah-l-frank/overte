"""Real temporary files behind a synthetic native SDK; no native compilation."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import base64
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest

from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.evidence import file_observation
from feature_journeys.fixtures import document
from ios.adapters import create_files as files
from ios.self_tests.test_ios_create_state import RUN, EPOCH

TICKET = 'b'*32
URL = 'http://controlled.invalid/feature-fixture/v1/runs/'+RUN+'/'
BINDING = dict(sourceRevision='d'*40, artifactSha256='e'*64, processIdentity='42', sessionId='bound-session',
               generation=1, targetFingerprint='f'*64)


class Boundary:
    def __init__(self, root):
        self.root = Path(root)/('feature-create-'+RUN); self.requests = []; self.packet = None
        self.sequence = 0; self.elapsed = 0; self.missing = False; self.lost_stage = False; self.live = True; self.mutate = None

    def clock(self): self.elapsed += 1; return EPOCH+self.elapsed
    def monotonic(self): return self.elapsed/1000
    def sleep(self, seconds): self.elapsed += int(seconds*1000)

    def rows(self):
        result = []
        for name in files.NAMES:
            path = self.root/name; row = dict(name=name, exists=path.exists())
            if path.exists():
                raw = path.read_bytes(); stat = path.stat()
                row.update(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest(), base64=base64.b64encode(raw).decode(),
                    identity={key: str(value) for key, value in dict(device=stat.st_dev, inode=stat.st_ino, bytes=stat.st_size,
                        modifiedSeconds=stat.st_mtime_ns//10**9, modifiedNanoseconds=stat.st_mtime_ns%10**9,
                        changedSeconds=stat.st_ctime_ns//10**9, changedNanoseconds=stat.st_ctime_ns%10**9).items()})
            result.append(row)
        return result

    def send(self, query):
        files.command(query); self.requests.append(deepcopy(query)); before = self.clock(); operation = query['operation']
        if operation == 'stage':
            self.root.mkdir(mode=0o700); path = self.root/'entity-import.json'
            path.write_bytes(base64.b64decode(query['inputBase64'])); path.chmod(0o600); observed = dict(performed=True)
        elif operation == 'observe':
            observed = dict(exists=self.root.exists(), files=self.rows() if self.root.exists() else [])
            if observed['exists']: observed['directory'] = self.root.as_uri()
        elif operation == 'locate': observed = dict(exists=self.root.exists(), directory=self.root.as_uri())
        else:
            if self.root.exists():
                if query['originals'] != self.rows(): raise NativeUIError('Original changed before removal')
                for path in self.root.iterdir(): path.unlink()
                self.root.rmdir()
            observed = dict(performed=True)
        self.sequence += 1; after = self.clock()
        self.packet = dict(iosCreateFilesVersion=1, requestId=query['commandId'], runId=RUN, instance='c'*32,
            sequence=self.sequence, processId=42, clockDomain='native-main-create-files',
            clockBefore=dict(epochMs=before, monotonicMs=before-EPOCH),
            clockAfter=dict(epochMs=after, monotonicMs=after-EPOCH), source=observed)
        if self.mutate: self.mutate(self.packet)
        if operation == 'stage' and self.lost_stage: self.missing = True

    def original(self): return '' if self.missing else json.dumps(self.packet)
    def native(self):
        return files.IOSCreateFiles(self.send, self.original, self.clock, lambda: self.live, 42,
                                    monotonic=self.monotonic, sleep=self.sleep)


class CreateFilesTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(); self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name); self.path.chmod(0o700); self.boundary = Boundary(self.path)
        self.lock = ScriptSourceLock(self.path/'script-feature-sources.lock')
        self.store = PrivateFeatureState(self.path/'ios-create-files.json')

    def owner(self): return files.OwnedCreateFiles(self.boundary.native(), self.store, BINDING, RUN, URL, lock=self.lock)

    def test_input_is_original_version3_without_future_texture_and_output_is_independently_read(self):
        with self.lock.held():
            owner = self.owner(); owner.reserve(TICKET); directory = owner.stage()
            actual_input = json.loads((Path(directory)/'entity-import.json').read_bytes())
            self.assertEqual(3, actual_input['DataVersion']); self.assertNotIn('textures', actual_input['Entities'][0])
            self.assertFalse((Path(directory)/'export.json').exists())
            # Separate simulated product writer: no storage action supplies the
            # exported bytes. The actual adapter independently reads this file.
            original_output = json.dumps(document(RUN, URL, TICKET, TICKET)).encode()
            (Path(directory)/'export.json').write_bytes(original_output)
            observed = owner.observe()['source']['files']; exported = base64.b64decode(observed[1]['base64'])
            self.assertEqual(original_output, exported)
            self.assertEqual(hashlib.sha256(original_output).hexdigest(), file_observation(exported, 'create', RUN, TICKET,
                {}, fixture_url=URL, model_ticket=TICKET, texture_ticket=TICKET)['sha256'])
            owner.release(observed); self.assertFalse(self.boundary.root.exists())
            self.assertEqual('retired', self.owner().state['phase']); self.assertIsNotNone(self.store.read())
            self.assertEqual(1, sum(row['operation'] == 'release' for row in self.boundary.requests))

    def test_lost_stage_receipt_retains_responsibility_and_recovers_without_stage_resend(self):
        with self.lock.held():
            owner = self.owner(); owner.reserve(TICKET); self.boundary.lost_stage = True
            with self.assertRaises(NativeUIError): owner.stage()
            self.assertTrue(self.boundary.root.exists()); self.assertEqual('staging', self.owner().state['phase'])
            self.boundary.missing = False; recovered = self.owner(); recovered.recover_stage()
            self.assertEqual(1, sum(row['operation'] == 'stage' for row in self.boundary.requests))
            with self.assertRaises(NativeUIError): recovered.stage()

    def test_file_replacement_between_observation_and_release_does_not_retire_owner(self):
        with self.lock.held():
            owner = self.owner(); owner.reserve(TICKET); owner.stage(); observed = owner.observe()['source']['files']
            path = self.boundary.root/'entity-import.json'; original = path.read_bytes(); path.unlink(); path.write_bytes(original)
            with self.assertRaises(NativeUIError): owner.release(observed)
            self.assertTrue(self.boundary.root.exists()); self.assertEqual('staged', self.owner().state['phase'])

    def test_wrong_native_pid_birth_old_clock_hash_or_file_identity_is_rejected(self):
        for fault in ('pid', 'clock', 'hash', 'identity'):
            boundary = Boundary(self.path/fault); boundary.root.parent.mkdir(mode=0o700)
            native = boundary.native(); token = 'c'*64
            native.request('stage', RUN, token, content=b'{"DataVersion":3}')
            def mutate(value):
                if fault == 'pid': value['processId'] = 43
                elif fault == 'clock': value['clockAfter']['epochMs'] += 5000
                elif fault == 'hash': value['source']['files'][0]['sha256'] = 'f'*64
                else: value['source']['files'][0]['identity']['bytes'] = '0'
            boundary.mutate = mutate
            with self.subTest(fault=fault), self.assertRaises(NativeUIError): native.request('observe', RUN, token)
            self.assertEqual(2, len(boundary.requests))

    def test_missing_export_and_staged_assertion_reference_cannot_pass_file_evidence(self):
        with self.lock.held():
            owner = self.owner(); owner.reserve(TICKET); owner.stage()
            observed = owner.observe()['source']['files']; self.assertFalse(observed[1]['exists'])
            with self.assertRaises(AssertionError):
                file_observation(base64.b64decode(observed[0]['base64']), 'create', RUN, TICKET, {}, fixture_url=URL,
                                 model_ticket=TICKET, texture_ticket=TICKET)

    def test_foreign_binding_or_import_ticket_cannot_reinterpret_existing_owner(self):
        with self.lock.held():
            owner = self.owner(); owner.reserve(TICKET)
            value = self.store.read(); value['binding']['processIdentity'] = '43'
            self.store.write(value, self.store.read())
            with self.assertRaises(NativeUIError): self.owner()
            self.assertEqual([], self.boundary.requests)


if __name__ == '__main__': unittest.main()
