"""No-build original-probe tests and synthetic native storage counterexamples.

The Qt/POSIX native implementation is source-reviewed and remains uncompiled.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from adapters.native_location_bookmarks import NativeLocationBookmarks, command, validate, FILE
from adapters.normal_ui import NativeUIError
from fixture.serve import FixtureState
from self_tests.test_native_feature_observation import probe_source

RUN = 'a' * 32
EMPTY = hashlib.sha256(b'{}').hexdigest()


class Boundary:
    def __init__(self):
        self.clock = 0.
        self.sequence = 0
        self.commands = []
        self.request = None
        self.sample = None
        self.ignored = False
        self.alive = True
        self.edit = None
        self.storage = dict(count=0, mapSha256=EMPTY, unownedCount=0, unownedSha256=EMPTY,
                            owned=[], storageMatches=True, file=None)

    def epoch(self):
        return 20000 + round(self.clock * 1000)

    def send(self, request):
        self.request = deepcopy(request)
        self.commands.append(deepcopy(request))
        if self.ignored:
            return
        self.sequence += 1
        self.sample = dict(bookmarkObservationVersion=1, commandId=request['commandId'], runId=request['runId'],
            instance='f' * 32, sequence=self.sequence, processId=123, requestedEpochMs=self.epoch(),
            capturedEpochMs=self.epoch(), storage=deepcopy(self.storage))
        if self.edit:
            self.edit(self.sample)

    def original(self):
        return json.dumps(self.sample) if self.sample is not None else ''

    def sleep(self, seconds):
        self.clock += seconds

    def reader(self):
        return NativeLocationBookmarks(self.send, self.original, self.epoch, lambda: self.alive, 123,
                                       monotonic=lambda: self.clock, sleep=self.sleep)

    def persisted(self):
        # Explicit synthetic native boundary; these are not native filesystem
        # observations. Keep one private unowned bookmark and both owned names.
        self.storage = dict(count=3, mapSha256='1' * 64, unownedCount=1, unownedSha256='2' * 64,
            owned=[dict(name='e2e-' + RUN, addressSha256='3' * 64),
                   dict(name='renamed-' + RUN, addressSha256='4' * 64)],
            storageMatches=True, file=dict(bytes=200, sha256='5' * 64, revisionSha256='6' * 64))


class NativeLocationBookmarkTests(unittest.TestCase):
    def test_original_empty_and_persisted_sources_are_distinct_and_caller_cannot_mutate_cursor(self):
        source = Boundary()
        reader = source.reader()
        first = reader.read(RUN)
        self.assertIsNone(first['storage']['file'])
        first['sequence'] = 4096
        first['storage']['count'] = 99
        source.persisted()
        second = reader.read(RUN)
        self.assertEqual(source.storage, second['storage'])
        self.assertEqual(2, second['sequence'])
        self.assertNotIn('state', second)
        self.assertNotIn('bookmark', second)
        self.assertNotIn('path', json.dumps(second))

    def test_actual_file_revision_and_bytes_are_preserved_even_when_map_is_unchanged(self):
        source = Boundary()
        source.persisted()
        reader = source.reader()
        before = reader.read(RUN)
        source.clock += .1
        source.storage['file']['revisionSha256'] = '7' * 64
        after = reader.read(RUN)
        self.assertEqual(before['storage']['mapSha256'], after['storage']['mapSha256'])
        self.assertNotEqual(before['storage']['file'], after['storage']['file'])
        self.assertEqual('6' * 64, before['storage']['file']['revisionSha256'])
        # Sampler exposes an unexpected rewrite. It never labels a requested
        # cancellation successful or substitutes a map-only persistence check.

    def test_unpersisted_or_missing_file_and_malformed_native_storage_cannot_be_success(self):
        edits = [lambda v: v['storage'].update(storageMatches=False),
            lambda v: v['storage'].update(storageMatches=1),
            lambda v: v['storage'].update(file=None),
            lambda v: v['storage'].update(count=2),
            lambda v: v['storage'].update(unownedCount=True),
            lambda v: v['storage']['file'].update(bytes=4 * 1024 * 1024 + 1),
            lambda v: v['storage']['file'].update(bytes=0),
            lambda v: v['storage']['file'].update(revisionSha256=''),
            lambda v: v['storage']['file'].update(filename='/private/bookmarks.json'),
            lambda v: v['storage']['owned'][0].update(name='Home'),
            lambda v: v['storage']['owned'][0].update(name='e2e-' + 'b' * 32),
            lambda v: v['storage']['owned'][0].update(addressSha256='http://private.invalid'),
            lambda v: v['storage']['owned'].reverse(),
            lambda v: v['storage']['owned'].__setitem__(1, deepcopy(v['storage']['owned'][0])),
            lambda v: v['storage'].update(bookmark=True)]
        for edit in edits:
            source = Boundary()
            source.persisted()
            source.edit = edit
            with self.subTest(edit=edit), self.assertRaises(NativeUIError):
                source.reader().read(RUN)
            self.assertEqual(1, len(source.commands))

    def test_old_foreign_replayed_pid_nonce_or_birth_cannot_replace_an_original_read(self):
        for edit in (lambda v: v.update(sequence=1), lambda v: v.update(instance='1' * 32),
                     lambda v: v.update(processId=124), lambda v: v.update(runId='1' * 32),
                     lambda v: v.update(capturedEpochMs=18000, requestedEpochMs=18000),
                     lambda v: v.update(requestedEpochMs=19999),
                     lambda v: v.update(bookmarkObservationVersion=True),
                     lambda v: v.update(expected='saved')):
            source = Boundary()
            reader = source.reader()
            reader.read(RUN)
            source.edit = edit
            with self.subTest(edit=edit), self.assertRaises(NativeUIError):
                reader.read(RUN)
        for fault in ('ignored', 'foreign-nonce', 'missing-hook', 'invalid-json'):
            source = Boundary()
            if fault == 'ignored':
                source.ignored = True
            elif fault == 'foreign-nonce':
                source.edit = lambda v: v.update(commandId='0' * 32)
            elif fault == 'missing-hook':
                source.edit = lambda v: (v.clear(), v.update(commandId=source.request['commandId'], status='unavailable'))
            else:
                source.original = lambda: '{"commandId":"x","commandId":"x"}'
            with self.subTest(fault=fault), self.assertRaises(NativeUIError):
                source.reader().read(RUN)
            self.assertEqual(1, len(source.commands))
            self.assertLessEqual(source.clock, 5.01)

    def test_native_read_cannot_outlive_guard_or_budget_or_rewind_local_time(self):
        for fault in ('guard', 'late', 'rewind'):
            source = Boundary()
            original = source.original
            def changed():
                raw = original()
                if fault == 'guard':
                    source.alive = False
                else:
                    source.clock = 6 if fault == 'late' else -1
                return raw
            source.original = changed
            with self.subTest(fault=fault), self.assertRaises(NativeUIError):
                source.reader().read(RUN)
            self.assertEqual(1, len(source.commands))

    def test_foreign_private_selectors_expected_results_and_ios_alias_are_not_inputs(self):
        valid = dict(schemaVersion=1, commandId='b' * 32, action='feature-location-bookmarks', runId=RUN)
        fixture = FixtureState()
        fixture.set_client_command(valid)
        for edit in ({'schemaVersion': True}, {'commandId': 'ios-' + 'b' * 32}, {'runId': RUN + '\n'},
                     {'path': '/private/bookmarks.json'}, {'names': ['Home']}, {'expected': 'saved'},
                     {'commandId': 'b' * 32 + '\n'}):
            with self.subTest(edit=edit), self.assertRaises((NativeUIError, ValueError)):
                command(valid | edit)
            with self.assertRaises(ValueError):
                fixture.set_client_command(valid | edit)

    def test_actual_original_probe_and_android_dispatch_preserve_native_packet_and_fixed_file(self):
        program = r'''
const Uuid={generate:()=>"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"};
const objectKeysMatch=(v,k)=>JSON.stringify(Object.keys(v).sort())===JSON.stringify(k.sort());
let calls=0,files=[];
const Test={featureLocationBookmarks:c=>{calls++;return {commandId:c.commandId,original:true};},saveObject:(v,name)=>files.push({v,name})};
SOURCE
const c={schemaVersion:1,commandId:'b'.repeat(32),action:'feature-location-bookmarks',runId:'a'.repeat(32)};
applyAndroidControlCommand(c);
if(calls!==1||!files[0].v.original||files[0].name!=='feature-location-bookmarks.json')throw Error('original native dispatch absent');
for(const edit of [{path:'/private/bookmarks.json'},{expected:'saved'},{schemaVersion:true},{commandId:'ios-'+c.commandId},{runId:c.runId+'\n'}])applyClientCommand({...c,...edit});
if(calls!==1)throw Error('unsafe selector accepted');
delete Test.featureLocationBookmarks;applyClientCommand({...c,commandId:'c'.repeat(32)});
if(files[1].v.status!=='unavailable')throw Error('missing hook became empty success');
'''.replace('SOURCE', probe_source())
        result = subprocess.run(['node', '-e', program], capture_output=True, text=True, timeout=5)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual('feature-location-bookmarks.json', FILE)

    def test_actual_pico_factory_keeps_bound_guard_and_reads_only_its_fixed_private_file(self):
        # Existing mock-APK fixture produces ZIP/JSON/tool output, never a build
        # or device access. Import the module, not its discovered TestCase class.
        root = Path(__file__).resolve().parents[3]
        sys.path.insert(0, str(root / 'android/vr/pico/tests/device'))
        import test_native_execution_binding as native_fixture
        fixture = native_fixture.NativeExecutionBindingTest()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        adapter = fixture.instance()
        source = Boundary()
        native = source.reader()
        guards = []
        native.guard = lambda: (guards.append(True), source.alive)[1]
        adapter._native_feature_observer = lambda target: native if target == 'owned' else None
        files = []
        def original(target, package, path, *, attempts):
            files.append((target, package, path, attempts))
            return source.original()
        adapter.adb.read_debug_app_file = original
        reader = adapter._location_bookmarks('owned')
        self.assertEqual(0, reader.read(RUN)['storage']['count'])
        self.assertEqual([('owned', 'org.overte.pico', 'files/overte-e2e/' + FILE, 1)], files)
        source.alive = False
        with self.assertRaises(NativeUIError):
            reader.read(RUN)
        self.assertEqual(1, len(source.commands))
        self.assertGreaterEqual(len(guards), 4)


if __name__ == '__main__':
    unittest.main()
