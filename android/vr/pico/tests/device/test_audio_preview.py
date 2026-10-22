"""Actual Pico wrapper/cycle composition with explicit no-device sources."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from functools import partial
import json
from pathlib import Path
import shlex
import sys
import unittest
from unittest.mock import patch

import test_normal_scripts as original

sys.path.insert(0, str(Path(__file__).resolve().parents[5] / 'tests/device'))
from adapters.android.adapter import ANDROID_CONTROL_COMMAND
from adapters.native_feature_observation import NativeFeatureObservation
from adapters.recorded_preview_evidence import RecordedPreviewEvidence, INPUT, SINK
from adapters.normal_ui import NativeUIError
from adapters.audio_preview import AudioPreview
from self_tests.test_audio_preview import Boundary


class PicoPreviewBoundary(Boundary):
    def original(self, identifier, token):
        row = next(row for row in self.capture()['controls'] if row['id'] == identifier)
        if row['token'] != token or not row['enabled'] or not row['inputReady']:
            raise RuntimeError('Synthetic native control is retired')


class PicoAudioPreviewTests(unittest.TestCase):
    def setUp(self):
        self.fixture = original.PicoNormalScriptsTests()
        self.fixture.setUp(); self.addCleanup(self.fixture.doCleanups)
        with patch.object(original, 'AudioBoundary', PicoPreviewBoundary):
            self.boundary, _ = self.fixture.audio_controls()
        self.adapter, self.native = self.fixture.instance, self.fixture.native
        starts = {}
        def started():
            if self.boundary.cycle not in starts:
                starts[self.boundary.cycle] = self.native.epoch_milliseconds(self.native.target) - 10
            return starts[self.boundary.cycle]
        self.boundary.started = started
        read_original = self.native.read_debug_app_file
        write_original = self.native.write_debug_app_file
        native_sample = self.boundary.native.mutate
        def sample(packet):
            native_sample(packet)
            packet['animation'], packet['animationFence'] = {}, {}
            packet.update(requestedEpochMs=self.native.epoch_milliseconds(self.native.target),
                capturedEpochMs=self.native.epoch_milliseconds(self.native.target))
        self.boundary.native.mutate = sample
        def write(target, package, path, raw):
            request = json.loads(raw)
            action = request.get('action')
            if path == ANDROID_CONTROL_COMMAND and action == 'feature-native-observe':
                self.boundary.native.send(request); return
            if path == ANDROID_CONTROL_COMMAND and action.startswith('feature-recorded-audio-'):
                self.boundary.evidence_send(request)
                if 'capturedEpochMs' in (self.boundary.preview_value or {}):
                    self.boundary.preview_value.update(requestedEpochMs=self.native.epoch_milliseconds(target),
                        capturedEpochMs=self.native.epoch_milliseconds(target))
                return
            if path.endswith('navigation-ui-command.json'):
                # The actual adapter must have persisted this exact original
                # token/cycle before the synthetic native boundary sees input.
                owner = self.flow.store.read()
                self.assertIsNotNone(owner['pending'])
                self.assertEqual(request['controlToken'], owner['pending']['inputs'][-1]['token'])
            return write_original(target, package, path, raw)
        def read(target, package, path, **kwargs):
            if path.endswith('feature-native-observation.json'):
                return self.boundary.native.original()
            if path.endswith('recorded-preview-observation.json'):
                return json.dumps(self.boundary.preview_value)
            return read_original(target, package, path, **kwargs)
        def bytes_read(args, *, target, timeout):
            self.assertEqual('exec-out', args[0]); self.assertEqual(self.native.target, target)
            name = shlex.split(args[1])[-1]; self.assertIn(name, (INPUT, SINK))
            raw = self.boundary.files.get(name)
            return b'OVT_PREVIEW_MISSING_V1\n' if raw is None else b'OVT_PREVIEW_BYTES_V1\n' + raw + b'\nOVT_PREVIEW_BYTES_END_V1\n'
        active = type(self.adapter)._native_feature_observer.__wrapped__.__globals__
        for boundary in (patch.object(self.native, 'write_debug_app_file', side_effect=write),
                         patch.object(self.native, 'read_debug_app_file', side_effect=read),
                         patch.object(self.native, 'execute_bytes', side_effect=bytes_read, create=True),
                         patch.dict(active,
                             NativeFeatureObservation=partial(NativeFeatureObservation,
                                 monotonic=lambda: self.boundary.clock, sleep=self.boundary.sleep),
                             RecordedPreviewEvidence=partial(RecordedPreviewEvidence,
                                 monotonic=lambda: self.boundary.clock, sleep=self.boundary.sleep))):
            boundary.start(); self.addCleanup(boundary.stop)
        self.flow = self.adapter._audio_preview(self.native.target, 'a' * 32)

    def test_actual_wrapper_sends_normal_input_once_and_preserves_original_pcm_cycle(self):
        self.flow.claim(); self.flow.act('1' * 32, 'record-start')
        self.boundary.complete()
        packet, raw = self.flow.originals()
        self.assertEqual(1, packet['source']['cycle'])
        self.assertEqual(self.boundary.files[INPUT], raw['input'])
        self.assertEqual(1, len(self.native.inputs))
        self.assertEqual('audio.record', self.native.inputs[0]['controlId'])
        self.assertFalse(any(name.startswith('feature.audio.') for name in self.adapter.capabilities(self.native.target)))
        self.native.digest = 'f' * 64
        commands = list(self.boundary.evidence_commands)
        with self.assertRaises((RuntimeError, ValueError)): self.flow.release_native()
        self.assertEqual(commands, self.boundary.evidence_commands)
        self.assertTrue(self.flow.store.path.exists())


    def test_adapter_teardown_cannot_hide_an_unresolved_audio_owner(self):
        self.flow.claim(); attempts = []
        def unavailable(flow):
            attempts.append(flow.run)
            raise NativeUIError('Synthetic original source unavailable during cleanup')
        with patch.object(AudioPreview, 'release_native', unavailable):
            with self.assertRaises(ValueError): self.fixture.cleanup_instance().cleanup(self.native.target)
        self.assertEqual(['a' * 32], attempts)
        self.assertFalse(self.native.running)
        self.assertTrue(self.flow.store.path.exists())


if __name__ == '__main__': unittest.main()
