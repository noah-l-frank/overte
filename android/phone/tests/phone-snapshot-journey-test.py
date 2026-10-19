#!/usr/bin/env python3
"""Original Phone binding and Snapshot byte oracle at synthetic native seams."""
# SPDX-License-Identifier: Apache-2.0
import importlib.util
import os
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[3]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


identity = load('_overte_phone_snapshot_identity_fixture',
                Path(__file__).parent / 'device/test_installed_identity.py')
images = load('_overte_phone_snapshot_original_byte_fixture',
              ROOT / 'tests/device/self_tests/test_snapshot_journey.py')
from snapshot_journey import snapshot_journey


@unittest.skipIf(os.name == 'nt', 'POSIX host fixture for actual Android private file scripts')
class BoundPhoneSnapshotJourney(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # These generated pictures substitute the native renderer boundary only.
        # They are never recorded as app capture or real device evidence.
        images.SnapshotJourneyTests.setUpClass()
        cls.fixtures = images.SnapshotJourneyTests.fixtures

    def setUp(self):
        self.owner = identity.InstalledIdentityTests('test_appium_description_uses_same_real_installed_binding')
        self.owner.setUp()
        self.addCleanup(self.owner.doCleanups)

    def native(self, mutation=''):
        instance, target, native, path = identity.snapshot_boundary.attach(
            self.owner, identity.appium, mutation=mutation, fixtures=self.fixtures)
        native.clock_scale = 1 if mutation == 'delayed-popup' else 20
        def run():
            return snapshot_journey('0123456789abcdef', invoke=native.invoke,
                read_artifact=lambda name: (native.artifacts / name).read_bytes(),
                assert_session=lambda _phase: identity.ExecutionIdentity(
                    self.owner.args.artifact, self.owner.args.expected_source_sha, self.owner.sha
                    ).verify_description(instance.describe(identity.snapshot_boundary.SELECTOR)),
                monotonic=lambda: native.clock, sleep=native.sleep, report=native.reports.append)
        native.run = run
        return instance, native

    def test_all_five_modes_use_normal_inputs_original_files_and_the_independent_decoder(self):
        instance, native = self.native()
        results = native.run()
        self.assertEqual(['still-png', 'still-jpg', 'animated', 'panorama', 'cubemap'],
                         [row['case'] for row in results])
        self.assertEqual(6, sum(len(row['outputs']) for row in results))
        self.assertTrue(native.reports[0]['outputSequenceCompleted'])
        self.assertFalse(native.reports[0]['deviceAcceptance'])
        self.assertEqual((native.mode, native.format), ('animated', 'webp'))
        self.assertEqual(5, native.captures)
        self.assertIsNone(native.screen)
        self.assertIsNone(instance.snapshot_store(identity.snapshot_boundary.SELECTOR).read())
        self.assertEqual(1, native.releases)
        self.assertIn('tabletPage.2', native.inputs)
        for row in results:
            for output in row['outputs']:
                self.assertEqual((native.files / output['basename']).read_bytes(),
                                 (native.artifacts / output['artifact']).read_bytes())

    def test_actual_capture_can_leave_review_visible_without_repeating_the_capture(self):
        _instance, native = self.native('keep-review-open')
        self.assertEqual(5, len(native.run()))
        self.assertEqual(5, native.captures)
        self.assertEqual((native.mode, native.format), ('animated', 'webp'))
        self.assertTrue(native.reports[0]['normalCloseSucceeded'])

    def test_current_phone_tablet_reopens_home_and_reenters_snap_normally(self):
        _instance, native = self.native('reopen-home')
        self.assertEqual(5, len(native.run()))
        self.assertEqual(5, native.captures)
        self.assertEqual((native.mode, native.format), ('animated', 'webp'))
        self.assertIsNone(native.screen)

    def test_late_native_popup_frame_retries_reads_without_replaying_input(self):
        _instance, native = self.native('delayed-popup')
        self.assertEqual(5, len(native.run()))
        self.assertEqual(5, native.captures)
        self.assertTrue(native.reports[0]['outputSequenceCompleted'])
        self.assertTrue(native.reports[0]['normalCloseSucceeded'])

    def test_acknowledged_but_ignored_capture_never_satisfies_the_output_oracle(self):
        _instance, native = self.native('ack-only')
        with self.assertRaisesRegex(AssertionError, 'complete fresh output'): native.run()
        self.assertFalse(native.reports[0]['outputSequenceCompleted'])
        self.assertTrue(native.reports[0]['normalCloseSucceeded'])
        self.assertEqual(1, native.captures)
        self.assertEqual((native.mode, native.format), ('animated', 'webp'))

    def test_missing_gif_companion_preserves_partial_progress_and_fails(self):
        _instance, native = self.native('missing-gif')
        with self.assertRaisesRegex(AssertionError, 'Normal SNAP animated'): native.run()
        self.assertEqual(2, len(native.reports[0]['cases']))
        self.assertFalse(native.reports[0]['outputSequenceCompleted'])
        self.assertTrue(native.reports[0]['normalCloseSucceeded'])

    def test_different_still_and_gif_tickets_fail_the_original_oracle(self):
        _instance, native = self.native('wrong-ticket')
        with self.assertRaisesRegex(AssertionError, 'different capture tickets'): native.run()
        self.assertFalse(native.reports[0]['outputSequenceCompleted'])
        self.assertTrue(native.reports[0]['normalCloseSucceeded'])

    def test_corrupt_original_bytes_cannot_be_qualified_by_successful_ui_input(self):
        _instance, native = self.native('corrupt')
        with self.assertRaisesRegex(AssertionError, 'complete fresh output'): native.run()
        self.assertEqual(0, len(native.reports[0]['cases']))
        self.assertTrue(native.reports[0]['normalCloseSucceeded'])

    def test_ignored_name_input_cannot_relabel_foreign_originals(self):
        _instance, native = self.native('name-ignored')
        with self.assertRaisesRegex(AssertionError, 'complete fresh output'): native.run()
        self.assertTrue(list(native.files.iterdir()))
        self.assertEqual([], list(native.artifacts.iterdir()))
        self.assertFalse(native.reports[0]['outputSequenceCompleted'])

    def test_ignored_mode_selection_is_observed_before_any_capture(self):
        _instance, native = self.native('mode-ignored')
        with self.assertRaisesRegex(RuntimeError, 'choice was not applied'): native.run()
        self.assertEqual(0, native.captures)
        self.assertTrue(native.reports[0]['normalCloseSucceeded'])

    def test_ignored_format_selection_is_observed_before_any_capture(self):
        _instance, native = self.native('format-ignored')
        with self.assertRaisesRegex(RuntimeError, 'choice was not applied'): native.run()
        self.assertEqual(0, native.captures)
        self.assertTrue(native.reports[0]['normalCloseSucceeded'])

    def test_unreadable_popup_does_not_look_like_a_successfully_closed_tablet(self):
        instance, native = self.native('malformed-checked')
        with self.assertRaisesRegex(RuntimeError, 'checked state is malformed'): native.run()
        self.assertFalse(native.reports[0]['normalCloseSucceeded'])
        self.assertFalse(native.reports[0]['outputSequenceCompleted'])
        self.assertIsNotNone(instance.snapshot_store(identity.snapshot_boundary.SELECTOR).read())
        self.assertEqual(1, native.releases)


if __name__ == '__main__':
    unittest.main()
