"""Real Pico candidate wrapper and observation transport; native boundaries only."""
# SPDX-License-Identifier: Apache-2.0
from functools import partial
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import test_native_execution_binding as existing

sys.path.insert(0, str(Path(__file__).resolve().parents[5] / 'tests/device'))
from adapters.normal_script_manager import read_native_diagnostic
from adapters.pico4 import feature_observation
from adapters.android.adapter import ANDROID_CONTROL_COMMAND


class FeatureObservationTests(unittest.TestCase):
    def setUp(self):
        self.fixture = existing.NativeExecutionBindingTest()
        self.fixture.setUp(); self.addCleanup(self.fixture.doCleanups)
        self.fixture.navigation_setup()
        self.native = self.fixture.fake
        self.clock = 0.0
        self.response = None
        self.sequence = 0
        self.mutation = None
        self.commands = []
        read_original = self.native.read_debug_app_file
        write_original = self.native.write_debug_app_file

        def write(target, package, path, raw):
            if path != ANDROID_CONTROL_COMMAND:
                return write_original(target, package, path, raw)
            command = json.loads(raw)
            self.commands.append(command)
            self.sequence += 1
            self.response = dict(schemaVersion=1, requestId=command['commandId'], instance='a' * 32,
                sampleSequence=self.sequence, sampleEpochMs=self.native.epoch_milliseconds(target),
                complete=True, scripts=[dict(url='http://native.actual/owned.js', path='native.actual/owned.js')])
            if command['includeAvatarEntities']:
                self.response.update(entitiesComplete=True, avatarEntities=[dict(
                    id='{11111111-1111-1111-1111-111111111111}', name='actual-native-name', type='Box')])
            if self.mutation:
                self.mutation(self.response)

        def read(target, package, path, **kwargs):
            if path == 'files/overte-e2e/normal-feature-observation.json':
                return json.dumps(self.response)
            return read_original(target, package, path, **kwargs)

        def sleep(seconds): self.clock += seconds
        for boundary in (patch.object(self.native, 'write_debug_app_file', side_effect=write),
                         patch.object(self.native, 'read_debug_app_file', side_effect=read),
                         patch.object(feature_observation, 'read_native_diagnostic',
                            partial(read_native_diagnostic, monotonic=lambda: self.clock, sleep=sleep))):
            boundary.start(); self.addCleanup(boundary.stop)
        self.adapter = self.fixture.instance()
        self.observer = self.adapter._feature_observer(self.native.target)

    def test_actual_request_original_rows_and_advancing_source_metadata_are_preserved(self):
        first = self.observer.read(0)
        second = self.observer.read(first['sampleSequence'], include_avatar_entities=True)
        self.assertEqual('http://native.actual/owned.js', first['scripts'][0]['url'])
        self.assertEqual(self.commands[1]['commandId'], second['requestId'])
        self.assertEqual('actual-native-name', second['avatarEntities'][0]['name'])
        self.assertGreater(second['sampleSequence'], first['sampleSequence'])
        self.assertEqual([], self.native.inputs)
        self.assertEqual([], self.native.controllers)
        self.assertFalse(any(value.startswith('feature.') for value in self.adapter.capabilities(self.native.target)))

    def test_ignored_foreign_stale_or_incomplete_native_observations_cannot_succeed(self):
        for changes in ({'requestId': 'f' * 32}, {'sampleEpochMs': 1}, {'complete': False},
                        {'sampleSequence': 0}, {'entitiesComplete': False}):
            with self.subTest(changes=changes):
                self.mutation = lambda value: value.update(changes)
                with self.assertRaisesRegex(RuntimeError, '^OVT_PICO_FEATURE_OBSERVATION_REJECTED$'):
                    self.observer.read(self.observer.sequence, include_avatar_entities=True)

    def test_probe_instance_change_and_regressed_request_sequence_are_rejected(self):
        first = self.observer.read(0)
        self.mutation = lambda value: value.update(instance='b' * 32)
        with self.assertRaises(RuntimeError): self.observer.read(first['sampleSequence'])
        self.mutation = None
        with self.assertRaises(RuntimeError): self.observer.read(0)

    def test_candidate_change_before_read_cannot_deliver_even_observation_input(self):
        self.native.digest = 'f' * 64
        with self.assertRaises(RuntimeError): self.observer.read(0)
        self.assertEqual([], self.commands)

    def test_candidate_change_after_capture_rejects_original_measurement(self):
        self.mutation = lambda value: setattr(self.native, 'digest', 'f' * 64)
        with self.assertRaises(RuntimeError): self.observer.read(0)
        self.assertEqual(0, self.observer.sequence)

    def test_process_or_foreground_loss_prevents_capture_and_redacts_native_details(self):
        self.native.identity = '999:foreign'
        with self.assertRaisesRegex(RuntimeError, '^OVT_PICO_FEATURE_OBSERVATION_REJECTED$'):
            self.observer.read(0)
        self.assertEqual([], self.commands)

    def test_unavailable_avatar_query_is_not_an_empty_world(self):
        self.mutation = lambda value: value.pop('entitiesComplete')
        with self.assertRaises(RuntimeError): self.observer.read(0, include_avatar_entities=True)


if __name__ == '__main__': unittest.main()
