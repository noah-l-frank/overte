"""Native Audio history/projection counterexamples; no PCM or product proof."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from adapters.normal_ui import NativeUIError
from adapters.recorded_preview_history import measured_state, FIELDS
from self_tests.test_native_feature_observation import Boundary


def event(sequence, phase, captured=0, played=0, epoch=19000, error=''):
    return dict(schemaVersion=1, eventSequence=sequence, publishedEpochMs=epoch,
        phase=phase, error=error, capturedBytes=captured, playedBytes=played,
        totalBytes=0 if phase == 'error' and captured == 0 else 576000)


def voice(events=None, *, cycle=1, started=18900):
    events = [event(1, 'capturing', 96000)] if events is None else deepcopy(events)
    active = bool(events) and events[-1]['phase'] in ('capturing', 'playing', 'draining')
    return dict(active=active, capturedBytes=events[-1]['capturedBytes'] if active else 0,
        playedBytes=events[-1]['playedBytes'] if active else 0, frameBytes=4, sampleRate=48000,
        channels=2, event=deepcopy(events[-1]) if events else {}, historyVersion=1,
        cycle=cycle, startedEpochMs=started, captureSampleRate=48000 if cycle else 0,
        captureChannels=2 if cycle else 0, historyComplete=True, events=events)


def complete():
    return voice([event(1, 'capturing', 96000), event(2, 'capturing', 192000, epoch=19100),
        event(3, 'playing', 576000, 96000, 19200), event(4, 'draining', 576000, 576000, 19300),
        event(5, 'completed', 576000, 576000, 19400)])


class PreviewHistoryTests(unittest.TestCase):
    def setUp(self):
        self.boundary = Boundary(); self.recorded = voice()
        self.boundary.mutate = lambda packet: packet['audio'].update(recordedVoice=deepcopy(self.recorded))
        self.reader = self.boundary.reader()

    def read(self): return self.reader.read(self.reader.sequence, require_recorded_history=True)

    def test_initial_source_is_explicitly_cycle_zero_not_a_missing_hook(self):
        self.recorded = voice([], cycle=0, started=0)
        actual = measured_state(self.read())
        self.assertEqual('idle', actual['phase']); self.assertEqual([], actual['history'])
        self.assertEqual(0, actual['recordedFrames']); self.assertEqual(0, actual['bufferedFrames'])
        self.assertTrue(actual['muted'])  # Source fact, not a forced baseline value.

    def test_actual_voice_capture_is_distinct_from_file_recording_and_uses_original_frames(self):
        packet = self.read(); self.assertFalse(packet['audio']['recording'])
        actual = measured_state(packet)
        self.assertTrue(actual['recording']); self.assertFalse(actual['preview'])
        self.assertEqual(24000, actual['recordedFrames']); self.assertEqual(24000, actual['bufferedFrames'])
        self.assertEqual(['capturing'], actual['history'])

    def test_completed_native_history_preserves_recorded_frames_after_live_buffers_are_empty(self):
        self.recorded = complete(); packet = self.read(); actual = measured_state(packet)
        self.assertEqual(0, packet['audio']['recordedVoice']['capturedBytes'])
        self.assertEqual(144000, actual['recordedFrames']); self.assertEqual(144000, actual['playedFrames'])
        self.assertEqual(0, actual['bufferedFrames']); self.assertFalse(actual['recording'])
        self.assertEqual(['capturing', 'playing', 'draining', 'completed'], actual['history'])
        again = self.read(); self.assertEqual(actual, measured_state(again))
        self.assertEqual(19400, again['audio']['recordedVoice']['events'][-1]['publishedEpochMs'])

    def test_missing_history_source_cannot_be_replaced_by_old_voice_status(self):
        self.recorded = {key:value for key,value in self.recorded.items() if key not in FIELDS}
        with self.assertRaises(NativeUIError): self.read()
        self.assertEqual(0, self.reader.sequence)
        self.assertTrue(self.boundary.reader().read(0, require_recorded_voice=True)['audio']['recordedVoice']['active'])

    def test_retouched_old_events_and_disappearing_prefix_fail_without_retiming(self):
        for fault in ('retime', 'drop', 'replace', 'extension'):
            with self.subTest(fault=fault):
                self.recorded = complete(); self.reader = self.boundary.reader(); first = self.read()
                if fault == 'retime': self.recorded['events'][0]['publishedEpochMs'] += 10
                elif fault == 'drop': self.recorded['events'] = self.recorded['events'][1:]
                elif fault == 'replace': self.recorded['events'][0]['capturedBytes'] += 4
                else: self.recorded = {key:value for key,value in self.recorded.items() if key not in FIELDS}
                with self.assertRaises(NativeUIError): self.read()
                self.assertEqual(first['sequence'], self.reader.sequence)

    def test_consumer_cannot_mutate_the_independent_previous_event_copy(self):
        first = self.read(); first['audio']['recordedVoice']['events'][0]['publishedEpochMs'] = 19100
        second = self.read()
        self.assertEqual(19000, second['audio']['recordedVoice']['events'][0]['publishedEpochMs'])

    def test_new_actual_start_resets_history_with_advancing_cycle_and_global_event_sequence(self):
        self.read()
        self.recorded = voice([event(2, 'error', epoch=19100, error='microphone-muted')], cycle=2, started=19050)
        actual = measured_state(self.read()); self.assertEqual('error', actual['phase'])
        self.assertEqual(['error'], actual['history']); self.assertEqual(0, actual['recordedFrames'])
        self.recorded = voice([], cycle=0, started=0)
        with self.assertRaises(NativeUIError): self.read()

    def test_gap_in_phase_or_event_sequence_incomplete_history_and_leftover_buffers_fail(self):
        for fault in ('gap', 'phase', 'incomplete', 'buffer', 'active', 'fraction', 'format'):
            with self.subTest(fault=fault):
                self.reader = self.boundary.reader(); self.recorded = complete()
                if fault == 'gap': self.recorded['events'][1]['eventSequence'] += 1
                elif fault == 'phase': self.recorded['events'] = [self.recorded['events'][0], self.recorded['events'][-1]]
                elif fault == 'incomplete': self.recorded['historyComplete'] = False
                elif fault == 'buffer': self.recorded['capturedBytes'] = 4
                elif fault == 'active': self.recorded['active'] = True
                elif fault == 'fraction': self.recorded['events'][0]['capturedBytes'] += 1
                else: self.recorded = voice(); self.recorded['sampleRate'] = 16000
                with self.assertRaises(NativeUIError): self.read()

    def test_live_and_terminal_bytes_cannot_regress_behind_a_freshly_observed_capture(self):
        for terminal in (False, True):
            with self.subTest(terminal=terminal):
                self.reader = self.boundary.reader(); self.recorded = voice()
                self.recorded['capturedBytes'] = 192000
                first = self.read()
                if terminal:
                    self.recorded = voice([event(1, 'capturing', 96000),
                        event(2, 'cancelled', 96000, epoch=19100)])
                else: self.recorded['capturedBytes'] = 96000
                with self.assertRaises(NativeUIError): self.read()
                self.assertEqual(first['sequence'], self.reader.sequence)

    def test_terminal_history_uses_original_format_after_the_current_output_device_changes(self):
        self.recorded = complete(); self.recorded.update(sampleRate=16000, channels=1, frameBytes=2)
        actual = measured_state(self.read()); self.assertEqual(144000, actual['recordedFrames'])
        self.assertEqual(144000, actual['playedFrames']); self.assertEqual(0, actual['bufferedFrames'])

    def test_releasing_pcm_cannot_turn_retained_product_status_into_a_fresh_idle_baseline(self):
        self.recorded = complete(); self.read()
        self.recorded['event'] = {}  # An invented reset is inconsistent with the actual retained history.
        with self.assertRaises(NativeUIError): self.read()
        self.recorded = complete(); self.assertEqual('completed', measured_state(self.read())['phase'])


if __name__ == '__main__': unittest.main()
