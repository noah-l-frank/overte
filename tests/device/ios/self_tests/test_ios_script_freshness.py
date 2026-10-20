"""Script HTTP/AFC clock joins; native processes, storage and OS are synthetic."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from adapters.normal_ui import NativeUIError
from fixture.serve import FixtureState
from ios.adapters.feature_observation import FeatureObservation
from self_tests.test_native_feature_observation import Boundary as ClockBoundary
from self_tests.test_native_script_files import Boundary as FilesBoundary, RUN
from self_tests.test_native_script_observation import Boundary as EngineBoundary


class ScriptFreshnessTests(unittest.TestCase):
    def boundary(self, kind):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        source = FilesBoundary(Path(temporary.name)) if kind == 'files' else EngineBoundary()
        source.mutate = lambda value: value.update(processId=42)
        clock = ClockBoundary(); clock.mutate = lambda value: value.update(processId=42)
        filename = 'feature-script-files.json' if kind == 'files' else 'feature-script-observation.json'
        action = 'feature-script-files' if kind == 'files' else 'feature-script-observe'
        fixture = FixtureState(); actions = []; reads = []; process = dict(
            bundleId='org.example.overte', pid=42, foreground=True)
        echo = [b'']
        target = dict(platform='ios', physical=True, appId=process['bundleId'],
            probe={'kind': 'ios-documents'}, testBuild=dict(resultsDirectory='owned-results',
                fixtureOrigin='http://controlled.invalid:49121'))
        test = self
        class Client:
            def execute(self, session, operation, values):
                test.assertEqual('test-only', session); test.assertEqual('mobile: pullFile', operation)
                reads.append(values['remotePath'])
                root = '@org.example.overte:documents/owned-results/'
                if values == {'remotePath': root + filename}:
                    raw = source.read() if kind == 'files' else source.original()
                elif values == {'remotePath': root + 'feature-native-observation.json'}:
                    raw = clock.original()
                else: raise AssertionError('Foreign private document')
                return base64.b64encode(raw.encode()).decode()
        class Response:
            status = 200
            def __enter__(self): return self
            def __exit__(self, *_): return False
            def read(self, limit): return echo[0][:limit]
        def post(request, timeout):
            self.assertEqual('http://controlled.invalid:49121/e2e-client-command.json', request.full_url)
            self.assertEqual(5, timeout)
            command = fixture.set_client_command(json.loads(request.data))
            echo[0] = json.dumps(command).encode(); actions.append(command['action'])
            if command['action'] == action: source.send(command)
            elif command['action'] == 'feature-native-observe': clock.send(command)
            else: raise AssertionError('Unexpected native command')
            return Response()
        boundary = patch('ios.adapters.feature_observation.post_request', side_effect=post)
        boundary.start(); self.addCleanup(boundary.stop)
        observer = FeatureObservation(Client(), 'test-only', target, lambda: deepcopy(process),
            monotonic=lambda: source.clock, sleep=source.sleep, epoch_ms=lambda: 9000000)
        reader = observer.script_fixture_files() if kind == 'files' else observer.script_execution_observer()
        def read():
            return reader.request('observe', RUN, 'b' * 64) if kind == 'files' else reader.read(reader.sequence)
        return source, clock, reader, read, actions, reads, process

    def test_original_receipt_is_bracketed_by_separate_native_clocks_despite_host_skew(self):
        for kind in ('files', 'engine'):
            with self.subTest(kind=kind):
                source, clock, reader, read, actions, reads, _ = self.boundary(kind)
                value = read()
                action = 'feature-script-files' if kind == 'files' else 'feature-script-observe'
                self.assertEqual(['feature-native-observe', action, 'feature-native-observe'], actions)
                self.assertEqual(2, len(clock.commands)); self.assertEqual(3, len(reads))
                self.assertEqual(1, reader.sequence)
                if kind == 'engine':
                    self.assertEqual(source.sample, value)
                    self.assertEqual(17000, value['source']['engines'][0]['required']['modules'][0]['capturedEpochMs'])
                else: self.assertEqual({'exists': False, 'files': []}, value)

    def test_current_nonce_cannot_rescue_old_capture_or_precommand_request(self):
        for kind in ('files', 'engine'):
            for requested, captured in ((18000, 18000), (19999, 20000)):
                with self.subTest(kind=kind, requested=requested):
                    source, _, reader, read, _, _, _ = self.boundary(kind)
                    source.mutate = lambda value: value.update(processId=42,
                        requestedEpochMs=requested, capturedEpochMs=captured)
                    with self.assertRaises(NativeUIError): read()
                    self.assertEqual(0, reader.sequence); self.assertEqual(1, len(source.commands))

    def test_independent_clock_failure_or_foreign_process_prevents_script_send(self):
        for kind in ('files', 'engine'):
            for fault in ('ignored', 'foreign-pid'):
                with self.subTest(kind=kind, fault=fault):
                    source, clock, reader, read, _, _, _ = self.boundary(kind)
                    if fault == 'ignored': clock.ignored = True
                    else: clock.mutate = lambda value: value.update(processId=43)
                    with self.assertRaises(NativeUIError): read()
                    self.assertEqual([], source.commands); self.assertEqual(0, reader.sequence)
                    self.assertEqual(1, len(clock.commands)); self.assertLessEqual(source.clock, 5.01)

    def test_final_clock_regression_or_timeout_does_not_commit_history(self):
        for kind in ('files', 'engine'):
            for fault in ('regressed', 'late'):
                with self.subTest(kind=kind, fault=fault):
                    source, clock, reader, read, _, _, _ = self.boundary(kind)
                    read(); old = deepcopy(getattr(reader, 'engines', {})); sequence = reader.sequence
                    def mutate(value):
                        value.update(processId=42)
                        if len(clock.commands) == 4:
                            if fault == 'regressed': value['capturedEpochMs'] = 19800
                            else: source.clock = 6
                    clock.mutate = mutate
                    with self.assertRaises(NativeUIError): read()
                    self.assertEqual(sequence, reader.sequence)
                    self.assertEqual(old, getattr(reader, 'engines', {}))
                    self.assertEqual(2, len(source.commands))

    def test_lost_process_after_receipt_cannot_commit_or_replay(self):
        for kind in ('files', 'engine'):
            with self.subTest(kind=kind):
                source, _, reader, read, _, reads, process = self.boundary(kind)
                def changed(value):
                    value.update(processId=42); process['pid'] = 43
                source.mutate = changed
                with self.assertRaises(NativeUIError): read()
                self.assertEqual(0, reader.sequence); self.assertEqual(1, len(source.commands))
                self.assertEqual(['@org.example.overte:documents/owned-results/feature-native-observation.json'], reads)


if __name__ == '__main__': unittest.main()
