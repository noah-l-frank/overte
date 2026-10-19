"""Storage transport/ownership counterexamples; native filesystem is simulated.

Real temporary fixture bytes exercise readback. C++ is deliberately not built.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from adapters.native_script_files import NativeScriptFiles, OwnedScriptFiles, NAMES, command, originals
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from fixture.serve import FixtureState
from self_tests.test_native_feature_observation import probe_source

RUN = 'a' * 32
BINDING = dict(sourceRevision='a' * 40, artifactSha256='b' * 64, processIdentity='31:actual-start',
    sessionId='actual-session', generation=1, targetFingerprint='c' * 64)


class Boundary:
    def __init__(self, path):
        self.path, self.clock, self.sequence = path, 0.0, 0
        self.root = path / ('feature-script-' + RUN)
        self.commands, self.sample, self.mutate, self.fault, self.owner = [], None, None, '', None
        self.okay, self.partial = True, 0

    def send(self, value):
        command(value); self.commands.append(deepcopy(value)); self.sequence += 1
        source = {}
        operation = value['operation']
        if operation == 'stage':
            self.owner = value['ownerToken']
            if self.fault != 'ack-only':
                self.root.mkdir(mode=0o700); (self.root / 'script-bundle').mkdir(mode=0o700)
                for name, encoded in value['files'].items():
                    with (self.root / name).open('xb') as stream: stream.write(base64.b64decode(encoded, validate=True))
            source = dict(performed=True)
        elif self.owner not in (None, value['ownerToken']):
            source = {}
        elif operation == 'release':
            if self.fault != 'ignored-release':
                for name in reversed(NAMES): (self.root / name).unlink(missing_ok=True)
                if self.root.exists(): (self.root / 'script-bundle').rmdir(); self.root.rmdir()
            source = dict(performed=True)
        elif not self.root.exists(): source = dict(exists=False, files=[])
        else:
            if self.fault == 'changed-byte': (self.root / 'companion.js').write_bytes(b'module.exports={delta:0};')
            if self.fault == 'missing': (self.root / 'script-bundle/companion.js').unlink(missing_ok=True)
            files = []
            for name in NAMES:
                if not (self.root / name).exists(): files.append(dict(name=name, exists=False)); continue
                raw = (self.root / name).read_bytes()
                files.append(dict(name=name, exists=True, bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest(),
                                  base64=base64.b64encode(raw).decode()))
            source = dict(exists=True, directory=self.root.as_uri(), files=files)
        self.sample = dict(schemaVersion=1, requestId=value['commandId'], instance='d' * 32,
            sequence=self.sequence, requestedEpochMs=20000, capturedEpochMs=20000,
            processId=31, runId=value['runId'], operation=operation, source=source)
        if self.mutate: self.mutate(self.sample)

    def read(self):
        if self.partial: self.partial -= 1; return '{'
        return json.dumps(self.sample)
    def sleep(self, value): self.clock += value
    def native(self, **kwargs):
        return NativeScriptFiles(self.send, self.read, lambda: 20000, lambda: self.okay, 31,
                                 monotonic=lambda: self.clock, sleep=self.sleep, **kwargs)


class ScriptFilesTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name); os.chmod(self.path, 0o700)
        self.boundary = Boundary(self.path)
        self.store = PrivateFeatureState(self.path / 'intent.json')
        self.files = OwnedScriptFiles(self.boundary.native(), self.store, BINDING)

    def test_original_bytes_are_separately_read_after_stage_and_absence_after_release(self):
        self.assertEqual(self.boundary.root.as_uri(), self.files.stage(RUN))
        self.assertEqual(['stage', 'observe'], [c['operation'] for c in self.boundary.commands])
        for name, raw in originals(RUN).items(): self.assertEqual(raw, (self.boundary.root / name).read_bytes())
        self.assertEqual({'performed':True}, self.files.release())
        self.assertFalse(self.boundary.root.exists()); self.assertIsNone(self.store.read())
        self.assertEqual(['stage', 'observe', 'release', 'observe'], [c['operation'] for c in self.boundary.commands])

    def test_ack_only_changed_original_and_missing_companion_retain_cleanup_intent(self):
        for fault in ('ack-only', 'changed-byte', 'missing'):
            with self.subTest(fault=fault):
                with tempfile.TemporaryDirectory(dir=self.path) as directory:
                    boundary = Boundary(Path(directory)); boundary.fault = fault
                    store = PrivateFeatureState(Path(directory) / 'intent.json')
                    files = OwnedScriptFiles(boundary.native(), store, BINDING)
                    with self.assertRaises(NativeUIError): files.stage(RUN)
                    self.assertTrue(store.read()['ownerToken'])
                    self.assertEqual(1, sum(c['operation'] == 'stage' for c in boundary.commands))

    def test_ignored_cleanup_ack_never_discards_ownership(self):
        self.files.stage(RUN); self.boundary.fault = 'ignored-release'
        before = self.store.read()
        with self.assertRaises(NativeUIError): self.files.release()
        self.assertEqual(before, self.store.read()); self.assertTrue(self.boundary.root.exists())
        self.boundary.fault = ''; self.files.release(); self.assertIsNone(self.store.read())

    def test_persisted_intent_exists_before_any_native_mutation_and_second_stage_is_refused(self):
        original = self.boundary.send
        def send(value):
            self.assertEqual(value['ownerToken'], self.store.read()['ownerToken'])
            return original(value)
        self.files.native.send = send
        self.files.stage(RUN); before = len(self.boundary.commands)
        with self.assertRaises(NativeUIError): self.files.stage(RUN)
        self.assertEqual(before, len(self.boundary.commands))

    def test_context_or_manifest_substitution_cannot_adopt_cleanup(self):
        self.files.stage(RUN); before = len(self.boundary.commands)
        foreign = OwnedScriptFiles(self.boundary.native(), self.store, BINDING | {'processIdentity':'32:foreign'})
        with self.assertRaises(NativeUIError): foreign.release()
        self.assertEqual(before, len(self.boundary.commands))
        value = self.store.read(); changed = deepcopy(value); changed['hashes']['script.js'] = 'e' * 64
        self.store.write(changed, value)
        with self.assertRaises(NativeUIError): self.files.release()
        self.assertEqual(before, len(self.boundary.commands)); self.assertTrue(self.boundary.root.exists())

    def test_wrong_request_run_process_instance_stale_or_missing_results_cannot_qualify(self):
        for fault in ('nonce', 'run', 'pid', 'instance', 'time', 'source', 'cursor', 'extra', 'wrong-hash', 'wrong-directory'):
            with self.subTest(fault=fault):
                def mutate(value):
                    if value['operation'] != 'observe': return
                    if fault == 'nonce': value['requestId'] = 'f' * 32
                    elif fault == 'run': value['runId'] = 'e' * 32
                    elif fault == 'pid': value['processId'] = 32
                    elif fault == 'instance': value['instance'] = 'e' * 32
                    elif fault == 'time': value['capturedEpochMs'] = 10000
                    elif fault == 'source': value['source'] = {'performed':True}
                    elif fault == 'cursor': value['sequence'] = 1
                    elif fault == 'extra': value['source']['loaded'] = True
                    elif fault == 'wrong-hash': value['source']['files'][0]['sha256'] = 'e' * 64
                    else: value['source']['directory'] = self.boundary.root.parent.as_uri() + '/feature-script-' + 'e' * 32
                self.boundary.mutate = mutate
                with self.assertRaises(NativeUIError): self.files.stage(RUN)
                self.assertTrue(self.store.read()); self.store.discard(self.store.read())
                self.boundary.mutate = None
                for name in reversed(NAMES): (self.boundary.root / name).unlink()
                (self.boundary.root / 'script-bundle').rmdir(); self.boundary.root.rmdir()
                self.boundary.clock = 0; self.files.native = self.boundary.native()

    def test_partial_receipt_only_retries_reads_and_lost_guard_keeps_intent(self):
        self.boundary.partial = 2; self.files.stage(RUN)
        self.assertEqual(1, sum(c['operation'] == 'stage' for c in self.boundary.commands))
        before = len(self.boundary.commands); self.boundary.okay = False
        with self.assertRaises(NativeUIError): self.files.release()
        self.assertEqual(before, len(self.boundary.commands)); self.assertIsNotNone(self.store.read())

    def test_closed_fixture_transport_rejects_unowned_paths_types_and_desired_results(self):
        value = dict(schemaVersion=1, commandId='ios-' + 'b' * 32, action='feature-script-files',
            operation='stage', runId=RUN, ownerToken='c' * 64,
            files={name:base64.b64encode(raw).decode() for name,raw in originals(RUN).items()})
        self.assertEqual(value, FixtureState().set_client_command(value))
        for change in ({'operation':'load'}, {'runId':'../foreign'}, {'expected':'loaded'}, {'schemaVersion':True},
                       {'files':{'../main.js':'YQ=='}}, {'files':dict(value['files'], **{'script.js':True})}):
            with self.subTest(change=str(change)[:40]), self.assertRaises((ValueError, NativeUIError)):
                FixtureState().set_client_command(value | change)

    def test_actual_js_dispatch_preserves_original_native_result_and_never_replays_stage(self):
        source = probe_source()
        javascript = '''
const assert=require('assert'); let calls=[],saved=[];
const Uuid={generate:()=>'{aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa}'};
const Test={featureScriptFiles:c=>{calls.push(c);return {requestId:c.commandId,source:{performed:true}};},
 saveObject:(v,n)=>saved.push({v,n})};
function objectKeysMatch(v,keys){return JSON.stringify(Object.keys(v).sort())===JSON.stringify(keys.sort());}
''' + source + '''
const c={schemaVersion:1,commandId:'b'.repeat(32),action:'feature-script-files',operation:'observe',
 runId:'a'.repeat(32),ownerToken:'c'.repeat(64)};
applyAndroidControlCommand(c);applyAndroidControlCommand(c);
assert.equal(calls.length,1);assert.equal(saved[0].n,'feature-script-files.json');
assert.deepEqual(saved[0].v,{requestId:c.commandId,source:{performed:true}});
applyAndroidControlCommand({...c,commandId:'d'.repeat(32),expected:'loaded'});
assert.equal(calls.length,1);
'''
        result = subprocess.run(['node', '-e', javascript], capture_output=True, text=True, timeout=10)
        self.assertEqual(0, result.returncode, result.stderr)


if __name__ == '__main__': unittest.main()
