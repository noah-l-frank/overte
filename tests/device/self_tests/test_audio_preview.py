"""Execute the real preview/UI/readers against explicit independent boundaries.

No client, Qt, real PCM device, ADB, OpenXR or acoustic source runs here.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from adapters.audio_preview import AudioPreview
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.recorded_preview_evidence import RecordedPreviewEvidence, INPUT, SINK
from adapters.script_journey.lock import ScriptSourceLock
from adapters.token_audio_ui import TokenAudioUI
from self_tests.test_token_audio_ui import AudioBoundary
from self_tests.test_native_feature_observation import Boundary as NativeBoundary

BINDING = dict(sourceRevision='1' * 40, artifactSha256='2' * 64, processIdentity='123:456',
    sessionId='pico-test-session', generation=1, targetFingerprint='3' * 64)


class Boundary(AudioBoundary):
    def __init__(self):
        super().__init__()
        self.hmd, self.mode, self.position = True, 1, .6
        self.events, self.files, self.preview_sequence = [], {}, 0
        self.guard_okay, self.preview_value = True, None
        self.evidence_commands, self.fail_release, self.retain_files = [], False, False
        self.native = NativeBoundary()
        self.native.mutate = self.native_sample
        self.input_fault, self.auto_complete = '', False

    def guard(self): return self.guard_okay

    def native_sample(self, packet):
        active = self.phase in ('capturing', 'playing', 'draining')
        packet['audio'] = dict(recording=False, muted=self.muted, recordedVoice=dict(
            active=active, capturedBytes=self.events[-1]['capturedBytes'] if active else 0,
            playedBytes=self.events[-1]['playedBytes'] if active else 0, frameBytes=2,
            sampleRate=8000, channels=1, event=deepcopy(self.events[-1]) if self.events else {},
            historyVersion=1, cycle=self.cycle, startedEpochMs=self.started() if self.cycle else 0,
            captureSampleRate=8000 if self.cycle else 0, captureChannels=1 if self.cycle else 0,
            historyComplete=True, events=deepcopy(self.events)))

    def started(self): return 18500 + self.cycle * 200

    def publish(self, phase, captured=0, played=0, error=''):
        sequence = self.events[-1]['eventSequence'] + 1 if self.events else self.cycle * 10
        self.events.append(dict(schemaVersion=1, eventSequence=sequence, publishedEpochMs=self.started() + 1 + len(self.events),
            phase=phase, error=error, capturedBytes=captured, playedBytes=played,
            totalBytes=0 if phase == 'error' else 48000))
        self.phase, self.active = phase, phase in ('capturing', 'playing', 'draining')

    def activate(self, identifier, **kwargs):
        old_phase = self.phase
        super().activate(identifier, **kwargs)
        if identifier == 'audio.record' and self.phase != old_phase:
            if self.phase in ('capturing', 'error'):
                self.events = []
                self.publish(self.phase, 16000 if self.phase == 'capturing' else 0,
                    error='microphone-muted' if self.phase == 'error' else '')
                self.files = {INPUT: b'\x20\0' * (8000 if self.phase == 'capturing' else 0), SINK: b''}
            elif self.phase == 'cancelled':
                self.publish('cancelled', self.events[-1]['capturedBytes'])
        elif identifier == 'audio.mute' and old_phase == 'capturing' and self.muted:
            self.publish('cancelled', self.events[-1]['capturedBytes'], error='microphone-muted')
        if self.input_fault == 'lost-result':
            self.transform = lambda value: None
            raise NativeUIError('Simulated lost result after actual normal input')

    def sleep(self, seconds):
        super().sleep(seconds)
        if self.auto_complete and self.phase == 'capturing' and self.clock >= 1:
            self.complete()

    def complete(self):
        self.publish('playing', 48000, 0)
        self.publish('draining', 48000, 48000)
        self.publish('completed', 48000, 48000)
        self.files = {INPUT: b'\x20\0' * 24000, SINK: b'\x40\0' * 24000}

    def evidence_send(self, command):
        self.evidence_commands.append(command)
        if command['action'].endswith('release'):
            if not self.retain_files: self.files.clear()
            if self.fail_release:
                self.preview_value = None
                return
            self.preview_value = dict(schemaVersion=1, requestId=command['commandId'], released=True)
            return
        self.preview_sequence += 1
        value = dict(schemaVersion=1, requestId=command['commandId'], instance='a' * 32,
            sequence=self.preview_sequence, requestedEpochMs=20000, capturedEpochMs=20000, processId=123)
        if command['action'].endswith('files'):
            value.update(memoryEmpty=not self.files, files=[dict(name=n, exists=n in self.files) for n in (INPUT, SINK)])
        else:
            def artifact(name, tap):
                raw = self.files[name]
                return dict(name=name, tap=tap, bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
            value['source'] = dict(cycle=self.cycle, startedEpochMs=self.started(), sampleRate=8000, channels=1,
                inputLastEpochMs=self.started() + 50 if self.files[INPUT] else 0,
                sinkLastEpochMs=self.started() + 100 if self.files[SINK] else 0, events=deepcopy(self.events),
                input=artifact(INPUT, 'capture-before-normalization'), sink=artifact(SINK, 'loopback-device-accepted-write'))
        self.preview_value = value

    def flow(self, path, binding=None, run='a' * 32):
        native = self.native.reader()
        native.monotonic, native.sleep = lambda: self.clock, self.sleep
        native.guard = self.guard
        evidence = RecordedPreviewEvidence(self.evidence_send, lambda: json.dumps(self.preview_value),
            self.files_get, lambda: 20000, self.guard, 123,
            monotonic=lambda: self.clock, sleep=self.sleep)
        return AudioPreview(PrivateFeatureState(path), binding or BINDING, run,
            lambda intent: TokenAudioUI(self, lambda *args: (intent(*args), self.intent(*args)),
                monotonic=lambda: self.clock, sleep=self.sleep),
            native, evidence, self.guard, ScriptSourceLock(path.with_suffix('.lock')),
            monotonic=lambda: self.clock, sleep=self.sleep)

    def files_get(self, name): return self.files.get(name)


class AudioPreviewTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(); self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / 'owner.json'
        self.boundary = Boundary(); self.flow = self.boundary.flow(self.path)

    def start(self):
        self.flow.claim()
        return self.flow.act('1' * 32, 'record-start')

    def test_normal_capture_complete_original_pcm_and_verified_native_release_keep_history_owner(self):
        self.start(); self.boundary.auto_complete = True
        packet = self.flow.await_terminal()
        self.assertEqual('completed', packet['audio']['recordedVoice']['event']['phase'])
        original, raw = self.flow.originals()
        self.assertEqual(self.boundary.files[INPUT], raw['input'])
        self.assertEqual(self.boundary.files[SINK], raw['sink'])
        self.assertNotEqual(raw['input'], raw['sink'])
        self.assertEqual(1, original['source']['cycle'])
        self.flow.release_native()
        owner = self.flow.owned()
        self.assertEqual('verified', owner['releaseState'])
        self.assertEqual('completed', owner['history']['event']['phase'])
        self.assertTrue(self.path.exists())
        self.assertEqual({}, self.boundary.files)
        self.assertGreaterEqual(self.boundary.clock, 7)
        with self.assertRaises(NativeUIError): self.flow.act('2' * 32, 'record-start')

    def test_normal_cancel_then_muted_start_rejection_and_unmute_recovery(self):
        self.start()
        actual = self.flow.act('2' * 32, 'record-cancel')
        self.assertEqual('cancelled', actual['audio']['recordedVoice']['event']['phase'])
        self.flow.act('3' * 32, 'mute', enabled=True)
        actual = self.flow.act('4' * 32, 'record-start')
        self.assertEqual('microphone-muted', actual['audio']['recordedVoice']['event']['error'])
        self.assertFalse(actual['audio']['recordedVoice']['active'])
        self.flow.act('5' * 32, 'mute', enabled=False)
        actual = self.flow.act('6' * 32, 'record-start')
        self.assertEqual(3, actual['audio']['recordedVoice']['cycle'])
        self.assertTrue(actual['audio']['recordedVoice']['active'])

    def test_original_terminal_cycles_and_pcm_provenance_survive_the_next_normal_start(self):
        self.start(); self.boundary.complete(); first, _ = self.flow.originals()
        self.flow.act('2' * 32, 'record-start'); self.boundary.complete()
        second, _ = self.flow.originals(); owner = self.flow.owned()
        self.assertEqual(2, second['source']['cycle'])
        self.assertEqual(1, owner['cycles'][0]['history']['cycle'])
        self.assertEqual(first, owner['cycles'][0]['original'])
        self.assertEqual('completed', owner['cycles'][0]['history']['event']['phase'])

    def test_mute_of_capture_is_measured_cancellation_with_actual_error_and_zero_live_buffers(self):
        self.start(); actual = self.flow.act('2' * 32, 'mute', enabled=True)
        self.assertFalse(actual['audio']['recordedVoice']['active'])
        self.assertEqual(0, actual['audio']['recordedVoice']['capturedBytes'])
        self.assertEqual('microphone-muted', actual['audio']['recordedVoice']['event']['error'])
        self.assertEqual('cancelled', actual['audio']['recordedVoice']['event']['phase'])
        self.flow.act('3' * 32, 'mute', enabled=False)
        self.assertTrue(self.flow.act('4' * 32, 'record-start')['audio']['recordedVoice']['active'])

    def test_read_retries_independent_sources_straddling_real_completion_without_input(self):
        self.start(); original = self.boundary.capture; once = [False]
        def capture():
            if not once[0]: self.boundary.complete(); once[0] = True
            return original()
        self.boundary.capture = capture; before = list(self.boundary.actions)
        self.assertEqual('completed', self.flow.read()['audio']['recordedVoice']['event']['phase'])
        self.assertEqual(before, self.boundary.actions)

    def test_process_restart_recovery_reads_lost_delivered_start_without_resending(self):
        self.flow.claim(); self.boundary.input_fault = 'lost-result'
        with self.assertRaises(NativeUIError): self.flow.act('1' * 32, 'record-start')
        self.assertIsNotNone(self.flow.owned()['pending'])
        before = list(self.boundary.actions)
        self.boundary.transform = lambda value: value
        restarted = self.boundary.flow(self.path)
        actual = restarted.reconcile()
        self.assertEqual(1, actual['audio']['recordedVoice']['cycle'])
        self.assertEqual(before, self.boundary.actions)
        with self.assertRaises(NativeUIError): restarted.act('1' * 32, 'record-start')
        self.assertIsNone(restarted.owned()['pending'])

    def test_ignored_start_retains_unresolved_input_and_blocks_cleanup_and_replay(self):
        self.flow.claim(); self.boundary.fault = 'record'
        with self.assertRaises(NativeUIError): self.flow.act('1' * 32, 'record-start')
        before = list(self.boundary.actions)
        for call in (self.flow.reconcile, self.flow.release_native,
                     lambda: self.flow.act('2' * 32, 'record-start')):
            with self.assertRaises(NativeUIError): call()
        self.assertEqual(before, self.boundary.actions)
        self.assertEqual(1, self.boundary.actions.count('audio.record'))
        self.assertIsNotNone(self.flow.owned()['pending'])

    def test_ignored_cancel_cannot_be_relabelled_completed_and_never_replayed(self):
        self.start(); self.boundary.fault = 'record'
        with self.assertRaises(NativeUIError): self.flow.act('2' * 32, 'record-cancel')
        self.boundary.complete()
        with self.assertRaises(NativeUIError): self.flow.reconcile()
        self.assertIsNotNone(self.flow.owned()['pending'])
        self.assertEqual(2, self.boundary.actions.count('audio.record'))

    def test_release_after_missing_ack_inspects_actual_absence_without_resend(self):
        self.start(); self.boundary.complete(); self.flow.originals()
        self.boundary.fail_release = True
        with self.assertRaises(NativeUIError): self.flow.release_native()
        self.assertEqual('requested', self.flow.owned()['releaseState'])
        self.boundary.fail_release = False
        restarted = self.boundary.flow(self.path); restarted.release_native()
        self.assertEqual('verified', restarted.owned()['releaseState'])
        self.assertEqual(1, sum(c['action'].endswith('release') for c in self.boundary.evidence_commands))
        self.assertTrue(self.path.exists())

    def test_ack_with_retained_files_never_verifies_or_retires_owner(self):
        self.start(); self.boundary.complete(); self.boundary.retain_files = True
        with self.assertRaises(NativeUIError): self.flow.release_native()
        self.assertEqual('requested', self.flow.owned()['releaseState'])
        with self.assertRaises(NativeUIError): self.flow.release_native()
        self.assertEqual(1, sum(c['action'].endswith('release') for c in self.boundary.evidence_commands))
        self.assertTrue(self.path.exists())

    def test_active_cleanup_uses_normal_cancel_and_restores_original_mute(self):
        self.boundary.muted = True
        self.flow.claim(); self.flow.act('1' * 32, 'mute', enabled=False)
        self.flow.act('2' * 32, 'record-start'); self.flow.release_native()
        self.assertTrue(self.boundary.muted)
        self.assertEqual('cancelled', self.flow.owned()['history']['event']['phase'])
        self.assertEqual(2, self.boundary.actions.count('audio.record'))
        self.assertEqual(2, self.boundary.actions.count('audio.mute'))

    def test_foreign_run_candidate_native_cycle_or_lost_process_cannot_take_over(self):
        self.start()
        for flow in (self.boundary.flow(self.path, run='b' * 32),
                     self.boundary.flow(self.path, binding=BINDING | {'artifactSha256': '4' * 64})):
            with self.assertRaises(NativeUIError): flow.read()
        self.boundary.cycle += 1
        with self.assertRaises(NativeUIError): self.flow.read()
        self.boundary.cycle -= 1; self.boundary.guard_okay = False
        with self.assertRaises(NativeUIError): self.flow.release_native()
        self.assertTrue(self.path.exists())

    def test_preexisting_native_pcm_files_are_refused_before_claim_or_any_product_input(self):
        self.boundary.files = {INPUT: b'unowned original'}
        with self.assertRaises(NativeUIError): self.flow.claim()
        self.assertFalse(self.path.exists())
        self.assertEqual([], self.boundary.actions)
        self.assertEqual(b'unowned original', self.boundary.files[INPUT])

    def test_existing_unowned_history_and_foreign_mode_never_become_idle_baselines(self):
        self.boundary.cycle = 1; self.boundary.publish('error', error='microphone-muted')
        with self.assertRaises(NativeUIError): self.flow.claim()
        self.assertFalse(self.path.exists())
        self.boundary.cycle = 0; self.boundary.events = []; self.boundary.mode = 0
        with self.assertRaises(NativeUIError): self.flow.claim()
        self.assertFalse(self.path.exists())
        self.assertEqual([], self.boundary.actions)

    def test_durable_native_prefix_prevents_rewritten_history_across_host_invocations(self):
        self.start(); self.boundary.complete(); self.flow.read()
        self.boundary.events[0]['publishedEpochMs'] += 1
        with self.assertRaises(NativeUIError): self.boundary.flow(self.path).read()
        self.assertTrue(self.path.exists())

    def test_reconstructed_owner_revalidates_original_source_and_release_metadata(self):
        self.start(); self.boundary.complete(); self.flow.originals(); self.flow.release_native()
        before = self.flow.owned()
        for fault in ('original-cycle', 'original-instance', 'release-process', 'release-file'):
            with self.subTest(fault=fault):
                value = deepcopy(before)
                if fault == 'original-cycle': value['original']['source']['cycle'] += 1
                elif fault == 'original-instance': value['original']['instance'] = 'f' * 32
                elif fault == 'release-process': value['releaseObservation']['processId'] += 1
                else: value['releaseObservation']['files'][0]['exists'] = True
                self.flow.store.write(value, self.flow.store.read())
                with self.assertRaises(NativeUIError): self.boundary.flow(self.path).read()
                self.flow.store.write(before, value)

    def test_mismatched_native_pcm_cycle_is_refused_without_releasing_originals(self):
        self.start(); self.boundary.complete()
        original = self.boundary.evidence_send
        def send(command):
            original(command)
            if 'source' in (self.boundary.preview_value or {}):
                self.boundary.preview_value['source']['cycle'] += 1
        self.boundary.evidence_send = send
        restarted = self.boundary.flow(self.path)
        with self.assertRaises(NativeUIError): restarted.originals()
        self.assertIn(INPUT, self.boundary.files)
        self.assertEqual({}, restarted.owned()['original'])


if __name__ == '__main__': unittest.main()
