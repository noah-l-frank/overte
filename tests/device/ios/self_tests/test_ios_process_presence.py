"""Original iOS source/HTTP/AFC joins; kernel, process and transport synthetic."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
from functools import partial
import hashlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from adapters.ios import binding
from fixture.serve import FixtureState
from ios.adapters import adapter as component
from ios.adapters.feature_observation import FeatureObservation
from self_tests.test_native_feature_observation import Boundary as ClockBoundary
from self_tests.test_native_process_presence import Boundary


class IOSProcessPresenceTests(unittest.TestCase):
    def setUp(self):
        self.source = Boundary(pid=42); self.clock = ClockBoundary()
        self.clock.mutate = lambda value: value.update(processId=42)
        self.process = dict(bundleId='org.example.overte', pid=42, foreground=True)
        self.target = dict(platform='ios', physical=True, probe={'kind': 'ios-documents'},
            appId=self.process['bundleId'], testBuild=dict(resultsDirectory='owned-results',
                fixtureOrigin='http://controlled.invalid:49121'))
        fingerprint = hashlib.sha256(json.dumps(self.target, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        self.state = dict(sessionId='test-only', generation=1, processIdentity='42', targetFingerprint=fingerprint)
        self.actions = []; self.reads = []; self.echo = b''; self.scope_checks = 0
        self.fixture = FixtureState(); test = self
        class Client:
            def execute(self, session, operation, values):
                test.assertEqual('test-only', session); test.assertEqual('mobile: pullFile', operation)
                path = values['remotePath']; test.reads.append(path)
                if path == '@org.example.overte:documents/owned-results/feature-process-presence.json':
                    raw = test.source.original()
                elif path == '@org.example.overte:documents/owned-results/feature-native-observation.json':
                    raw = test.clock.original()
                else: raise AssertionError('Foreign original document')
                return base64.b64encode(raw.encode()).decode()
        class Response:
            status = 200
            def __enter__(self): return self
            def __exit__(self, *_): return False
            def read(self, limit): return test.echo[:limit]
        def post(request, timeout):
            self.assertEqual(5, timeout)
            self.assertEqual('http://controlled.invalid:49121/e2e-client-command.json', request.full_url)
            command = self.fixture.set_client_command(json.loads(request.data))
            self.echo = json.dumps(command).encode(); self.actions.append(command['action'])
            if command['action'] == 'feature-process-presence': self.source.send(command)
            elif command['action'] == 'feature-native-observe': self.clock.send(command)
            else: raise AssertionError('Unexpected native operation')
            return Response()
        for boundary in (patch('ios.adapters.feature_observation.post_request', side_effect=post),
                patch.object(component, 'FeatureObservation', partial(FeatureObservation,
                    monotonic=lambda: self.source.clock, sleep=self.source.sleep, epoch_ms=lambda: 9000000))):
            boundary.start(); self.addCleanup(boundary.stop)
        self.adapter = component.IOSAdapter.__new__(component.IOSAdapter)
        self.adapter.target = lambda _selector: self.target
        self.adapter.ensure_session = lambda _selector: (Client(), 'test-only', self.state)
        self.adapter.read_session = lambda _selector: deepcopy(self.state)
        def process_guard(*_args):
            self.scope_checks += 1
            if not self.process['foreground'] or str(self.process['pid']) != self.state['processIdentity']:
                raise RuntimeError('Synthetic original process guard rejected')
        self.adapter.assert_ios_process_identity = process_guard
        self.adapter.native_process = lambda *_args: deepcopy(self.process)
        self.adapter._scripts = lambda *_args: (_ for _ in ()).throw(AssertionError('Kernel query must not open Scripts'))

    def test_original_factory_preserves_kernel_result_and_brackets_it_with_native_clocks(self):
        reader = self.adapter._process_presence('owned'); self.source.presence = 'absent'
        actual = reader.require_absent(29)
        self.assertEqual(self.source.value, actual)
        self.assertEqual(['feature-native-observe', 'feature-process-presence', 'feature-native-observe'], self.actions)
        self.assertEqual(20000, actual['capturedEpochMs']); self.assertGreater(self.scope_checks, 3)
        self.assertNotIn('normalScripts', self.target)
        self.source.presence = 'unknown'
        with self.assertRaises(RuntimeError): reader.require_absent(29)
        self.assertEqual('EPERM', reader.last['errorSymbol'])

    def test_current_nonce_stale_receipt_or_foreign_clock_cannot_prove_exit(self):
        reader = self.adapter._process_presence('owned'); self.source.presence = 'absent'
        self.source.edit = lambda value: value.update(requestedEpochMs=18000, capturedEpochMs=18000)
        with self.assertRaises(RuntimeError): reader.require_absent(29)
        self.assertIsNone(reader.last)
        self.source.edit = None; before = len(self.source.commands)
        self.clock.mutate = lambda value: value.update(processId=43)
        with self.assertRaises(RuntimeError): reader.require_absent(29)
        self.assertEqual(before, len(self.source.commands)); self.assertIsNone(reader.last)

    def test_missing_query_and_late_final_native_clock_never_commit_an_absence(self):
        reader = self.adapter._process_presence('owned'); self.source.ignored = True; self.source.presence = 'absent'
        with self.assertRaises(RuntimeError): reader.require_absent(29)
        self.assertEqual(1, len(self.source.commands)); self.assertIsNone(reader.last)
        self.assertLessEqual(self.source.clock, 5.01)
        self.source.ignored = False
        clock_before = len(self.clock.commands)
        def late(value):
            value.update(processId=42)
            if len(self.clock.commands) == clock_before + 2: self.source.clock += 6
        self.clock.mutate = late
        with self.assertRaises(RuntimeError): reader.require_absent(29)
        self.assertIsNone(reader.last); self.assertEqual(2, len(self.source.commands))

    def test_changed_session_target_or_process_blocks_before_native_command(self):
        reader = self.adapter._process_presence('owned'); before = len(self.actions)
        self.state['generation'] += 1
        with self.assertRaises(RuntimeError): reader.read(29)
        self.assertEqual(before, len(self.actions)); self.state['generation'] -= 1
        self.target['changed'] = 'different target'
        with self.assertRaises(RuntimeError): reader.read(29)
        self.assertEqual(before, len(self.actions)); del self.target['changed']
        self.process['pid'] = 43
        with self.assertRaises(RuntimeError): reader.read(29)
        self.assertEqual(before, len(self.actions))

    def test_unbound_canonical_source_refuses_before_target_or_transport(self):
        with patch.object(component.AppiumAdapter, 'load_targets', return_value={}):
            adapter = binding.create_adapter(SimpleNamespace(platform='ios', action='cleanup'), component.AppiumAdapter)
        adapter.target = lambda *_args: (_ for _ in ()).throw(AssertionError('Unbound target lookup'))
        with self.assertRaisesRegex(ValueError, 'INSTALLED_CODE_BINDING_UNAVAILABLE'):
            adapter._process_presence('private-selector')
        self.assertEqual([], self.actions)


if __name__ == '__main__': unittest.main()
