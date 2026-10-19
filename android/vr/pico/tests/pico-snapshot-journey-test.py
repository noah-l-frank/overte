#!/usr/bin/env python3
"""Original Pico CLI/candidate binding and independent SNAP byte oracle.

Only native UI/OpenXR/SDK/render/time boundaries are synthetic. No package is
built or installed, no target is discovered, and no device acceptance is emitted.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[4]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


binding = load('_overte_pico_snapshot_original_binding_fixture',
               Path(__file__).parent / 'device/test_native_execution_binding.py')
images = load('_overte_pico_snapshot_original_image_fixture',
              ROOT / 'tests/device/self_tests/test_snapshot_journey.py')
from execution_identity import ExecutionIdentity
from snapshot_journey import snapshot_journey


class BoundPicoSnapshotJourney(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Synthetic renderer output remains explicitly a test boundary. Actual
        # native UI/pointer tests are registered separately by the same owner.
        images.SnapshotJourneyTests.setUpClass()
        cls.fixtures = images.SnapshotJourneyTests.fixtures

    def setUp(self):
        self.owner = binding.NativeExecutionBindingTest(
            'test_build_receipt_bytes_frozen_and_missing_evidence_precedes_device')
        self.owner.setUp()
        self.addCleanup(self.owner.doCleanups)

    def native(self, mutation=''):
        self.owner.snapshot_setup(mutation=mutation, images=self.fixtures)
        native = self.owner.fake
        identity = ExecutionIdentity(self.owner.fixture.apk,
            self.owner.fixture.record['sourceRevision'], self.owner.fixture.record['artifactSha256'])
        def run():
            return snapshot_journey('0123456789abcdef', invoke=self.owner.snapshot_invoke,
                read_artifact=lambda name: (native.artifacts / name).read_bytes(),
                assert_session=lambda _phase: identity.verify_description(self.owner.invoke('describe')),
                monotonic=lambda: native.clock, sleep=native.sleep, report=native.reports.append)
        native.run = run
        return native

    def test_all_five_normal_modes_use_original_files_and_the_original_independent_decoder(self):
        native = self.native()
        rows = native.run()
        self.assertEqual(['still-png', 'still-jpg', 'animated', 'panorama', 'cubemap'],
                         [row['case'] for row in rows])
        self.assertEqual(6, sum(len(row['outputs']) for row in rows))
        self.assertEqual(5, native.captures)
        self.assertTrue(native.reports[0]['outputSequenceCompleted'])
        self.assertFalse(native.reports[0]['deviceAcceptance'])
        self.assertEqual((native.mode, native.format), ('animated', 'webp'))
        self.assertFalse(native.opened)
        self.assertEqual([], list(self.owner.state_root.glob('normal-snapshot-*.json')))
        for row in rows:
            for output in row['outputs']:
                self.assertEqual((native.files / output['basename']).read_bytes(),
                                 (native.artifacts / output['artifact']).read_bytes())

    def test_acknowledged_but_ignored_capture_fails_actual_output_observation(self):
        native = self.native('ack-only')
        with self.assertRaisesRegex(AssertionError, 'complete fresh output'): native.run()
        self.assertFalse(native.reports[0]['outputSequenceCompleted'])
        self.assertTrue(native.reports[0]['normalCloseSucceeded'])
        self.assertEqual(1, native.captures)
        self.assertEqual((native.mode, native.format), ('animated', 'webp'))

    def test_missing_gif_companion_retains_partial_cases_and_never_passes(self):
        native = self.native('missing-gif')
        with self.assertRaisesRegex(AssertionError, 'Normal SNAP animated'): native.run()
        self.assertEqual(2, len(native.reports[0]['cases']))
        self.assertFalse(native.reports[0]['outputSequenceCompleted'])
        self.assertTrue(native.reports[0]['normalCloseSucceeded'])

    def test_slow_original_candidate_verification_happens_before_fresh_native_input(self):
        native = self.native()
        native.installation_delay_ms = 2000
        self.assertEqual(5, len(native.run()))
        self.assertTrue(native.input_ages)
        self.assertTrue(all(0 <= age <= 5000 for age in native.input_ages))
        self.assertTrue(native.reports[0]['outputSequenceCompleted'])
        self.assertEqual(5, native.captures)


if __name__ == '__main__':
    unittest.main()
