"""Actual host transport/validators, with only AFC/process/HTTP boundaries synthetic."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
import copy
import json
from pathlib import Path
import sys
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from adapters.normal_ui import NativeUIError
from ios.adapters import normal_input


class Boundary:
    def __init__(self, mutation=None):
        self.mutation, self.requests = mutation, []
        self.pid, self.sequence, self.clock = 42, 0, 0.0
        self.instance = '11111111-2222-3333-4444-555555555555'
        self.token = '11111111-2222-3333-4444-666666666666'
        self.target = {'appId': 'org.example.client', 'nativeUiObservation': {'kind': 'uikit-documents', 'version': 1},
            'testBuild': {'fixtureOrigin': 'http://controlled.invalid:49121', 'resultsDirectory': 'owned-results'}}

    def process(self):
        return {'bundleId': self.target['appId'], 'pid': self.pid, 'foreground': True}

    def tick(self):
        self.clock += 0.1
        return self.clock

    def observed(self):
        return {'schemaVersion': 1, 'instance': self.instance, 'frameSpace': 'qt-window-logical',
            'processId': 42, 'sampleEpochMs': time.time() * 1000, 'elapsedMs': 100,
            'lastSequence': self.sequence, 'tabletShown': False, 'ready': True,
            'controls': [{'id': 'address.field', 'token': self.token, 'enabled': True, 'focused': True,
                'frame': {'x': 10, 'y': 20, 'width': 430, 'height': 60}}]}

    def post(self, request, timeout):
        payload = json.loads(request.data)
        self.requests.append(payload)
        key = 'observation' if payload['operation'] == 'observe' else 'status'
        if key == 'observation':
            value = self.observed()
            if self.mutation == 'unfocused': value['controls'][0]['focused'] = False
            if self.mutation == 'stale': value['sampleEpochMs'] -= 10000
            if self.mutation == 'foreign-instance' and len(self.requests) > 1:
                value['instance'] = '11111111-2222-3333-4444-777777777777'
        else:
            native = payload['input']
            self.sequence = native['sequence']
            value = {'schemaVersion': 1, 'commandId': native['commandId'], 'instance': self.instance,
                'sequence': self.sequence, 'performed': True, 'processId': 42, 'sampleEpochMs': time.time() * 1000}
            if self.mutation == 'not-delivered': value['performed'] = False
            if self.mutation == 'ack-only': value = {'performed': True}
            if self.mutation == 'replay': value['sequence'] -= 1
            if self.mutation == 'cross-process': self.pid = 43
            if self.mutation == 'status-extra': value['navigationPassed'] = True
        self.receipt = {'schemaVersion': 1, 'commandId': payload['commandId'], key: value}
        if self.mutation == 'foreign-nonce': self.receipt['commandId'] = 'ios-' + 'f' * 32
        if self.mutation == 'receipt-extra': self.receipt['featurePassed'] = True
        self.response = json.dumps(payload).encode()
        return self

    status = 200
    def __enter__(self): return self
    def __exit__(self, *_): return False
    def read(self, size): return self.response[:size]

    def execute(self, session, operation, arguments):
        assert operation == 'mobile: pullFile'
        assert arguments['remotePath'] == '@org.example.client:documents/owned-results/ios-normal-ui-request-result.json'
        return base64.b64encode(json.dumps(self.receipt).encode()).decode()

    def input(self):
        return normal_input.NativeInput(self, 'owned-session', self.target, self.process,
            monotonic=self.tick, sleep=lambda _: None)


class NativeInputTransport(unittest.TestCase):
    def test_actual_transport_joins_distinct_native_and_outer_nonces_without_feature_claim(self):
        boundary = Boundary()
        with patch.object(normal_input, 'urlopen', boundary.post):
            native = boundary.input()
            self.assertEqual(native.edit('replace', 'Grüße 🌍'), {'performed': True})
            self.assertEqual(native.edit('submit'), {'performed': True})
        self.assertEqual([v['operation'] for v in boundary.requests], ['observe', 'edit', 'observe', 'edit'])
        for payload in (boundary.requests[1], boundary.requests[3]):
            self.assertNotEqual(payload['commandId'], payload['input']['commandId'])
            self.assertNotIn('featurePassed', payload)
        self.assertEqual(boundary.requests[1]['input']['sequence'], 1)
        self.assertEqual(boundary.requests[3]['input']['sequence'], 2)
        self.assertEqual(boundary.requests[1]['input']['text'], 'Grüße 🌍')
        self.assertNotIn('text', boundary.requests[3]['input'])

    def test_failed_stale_foreign_ack_only_or_replayed_input_never_qualifies(self):
        for mutation in ('not-delivered', 'ack-only', 'replay', 'cross-process', 'status-extra',
                         'unfocused', 'stale', 'foreign-nonce', 'receipt-extra'):
            boundary = Boundary(mutation)
            with self.subTest(mutation=mutation), patch.object(normal_input, 'urlopen', boundary.post):
                with self.assertRaises(NativeUIError):
                    boundary.input().edit('replace', 'ordinary input')
            self.assertLessEqual(len(boundary.requests), 2, 'mutating inputs are never retried')

    def test_process_owned_native_instance_cannot_change_between_reads(self):
        boundary = Boundary('foreign-instance')
        with patch.object(normal_input, 'urlopen', boundary.post):
            native = boundary.input()
            native.capture()
            with self.assertRaisesRegex(NativeUIError, 'instance changed'):
                native.capture()

    def test_literal_text_is_validated_before_any_transport(self):
        for text in ('x\ncommand', '\ud800', 'x' * 4097, False, None):
            boundary = Boundary()
            with self.subTest(text=repr(text)[:20]), patch.object(normal_input, 'urlopen', boundary.post):
                with self.assertRaises(NativeUIError):
                    boundary.input().edit('replace', text)
            self.assertEqual(boundary.requests, [])

    def test_observer_rejects_unknown_duplicate_unfocused_schema_and_geometry_facts(self):
        baseline = Boundary().observed()
        for mutation in ('process', 'schema', 'ready', 'extra', 'unknown', 'duplicate', 'token', 'frame'):
            value = copy.deepcopy(baseline)
            if mutation == 'process': value['processId'] = 43
            elif mutation == 'schema': value['schemaVersion'] = True
            elif mutation == 'ready': value['ready'] = False
            elif mutation == 'extra': value['featurePassed'] = True
            elif mutation == 'unknown': value['controls'][0]['id'] = 'navigation.inject'
            elif mutation == 'duplicate': value['controls'].append(copy.deepcopy(value['controls'][0]))
            elif mutation == 'token': value['controls'][0]['token'] = 'foreign'
            else: value['controls'][0]['frame']['width'] = float('nan')
            with self.subTest(mutation=mutation), self.assertRaises(NativeUIError):
                normal_input.observation(value, 42)


if __name__ == '__main__':
    unittest.main()
