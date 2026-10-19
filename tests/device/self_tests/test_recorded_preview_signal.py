"""Complete short acoustic challenges for the actual three-second preview."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import array
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest
import wave

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from voice_peer import voice_signal as signal
from feature_journeys.fixtures import payload

CHALLENGE = 'a' * 32


class RecordedPreviewSignalTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / 'actual-capture.wav'

    def write(self, samples, rate=24000):
        data = array.array('h', samples)
        if sys.byteorder != 'little': data.byteswap()
        with wave.open(str(self.path), 'wb') as output:
            output.setparams((1, 2, rate, 0, 'NONE', 'not compressed'))
            output.writeframes(data.tobytes())

    def analyze(self, challenge=CHALLENGE, expected='present'):
        return signal.analyze(self.path, challenge, expected, profile=signal.PREVIEW_PROFILE)

    def test_all_twelve_actual_symbols_fit_three_seconds_at_each_supported_rate(self):
        for rate in (8000, 16000, 24000, 44100, 48000):
            with self.subTest(rate=rate):
                pcm = signal.samples(CHALLENGE, rate, profile=signal.PREVIEW_PROFILE)
                self.assertEqual(rate * 3, len(pcm))
                self.write(pcm, rate)
                result = self.analyze()
                self.assertTrue(result['passed'], result)
                self.assertEqual(12, len(result['symbolCoverage']))
                self.assertGreaterEqual(min(result['symbolCoverage']), 0.65)
                self.assertEqual(signal.PREVIEW_PROFILE, result['signalProfile'])

    def test_wrong_run_profile_missing_final_symbol_and_reversed_capture_fail(self):
        pcm = signal.samples(CHALLENGE, profile=signal.PREVIEW_PROFILE)
        self.write(pcm)
        self.assertFalse(self.analyze('b' * 32)['passed'])
        self.assertFalse(signal.analyze(self.path, CHALLENGE)['passed'])
        self.write(reversed(pcm))
        self.assertFalse(self.analyze()['passed'])
        incomplete = array.array('h', pcm)
        last_start = round((0.2 + 11 * 0.16) * 24000)
        incomplete[last_start:] = array.array('h', [0]) * (len(incomplete) - last_start)
        self.write(incomplete)
        self.assertFalse(self.analyze()['passed'])

    def test_quiet_negative_requires_three_full_seconds_and_rejects_actual_signal(self):
        self.write([0] * (24000 * 3))
        self.assertTrue(self.analyze(expected='absent')['passed'])
        self.write([0] * (24000 * 2))
        self.assertFalse(self.analyze(expected='absent')['passed'])
        self.write(signal.samples(CHALLENGE, profile=signal.PREVIEW_PROFILE))
        self.assertFalse(self.analyze(expected='absent')['passed'])

    def test_fixture_serves_separate_profile_without_changing_legacy_roundtrip_bytes(self):
        run, ticket = 'a' * 32, 'b' * 32
        mime, preview = payload('preview-challenge.v1.wav', run, ticket)
        _mime, legacy = payload('challenge.wav', run, ticket)
        self.assertEqual('audio/wav', mime)
        self.assertEqual(44 + 24000 * 3 * 2, len(preview))
        self.assertEqual(44 + round(24000 * signal.DURATION) * 2, len(legacy))
        self.assertNotEqual(hashlib.sha256(preview).digest(), hashlib.sha256(legacy).digest())
        for profile in ('', 'shorter', None, {}, True):
            with self.subTest(profile=profile), self.assertRaises(ValueError):
                signal.samples(CHALLENGE, profile=profile)


if __name__ == '__main__': unittest.main()
