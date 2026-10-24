"""Counterfactual native-capture journeys; no device or client claim is made."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from io import BytesIO
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image, ImageDraw

DEVICE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DEVICE))
from contracts import validate_operation_arguments, validate_operation_result
from web_video_journey import video_journey

spec = importlib.util.spec_from_file_location('owned_video_generator',
    DEVICE / 'fixture/parity/generate_video.py')
generator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(generator)
ROI = (80, 60, 464, 276)
SCRIPT = 'http://127.0.0.1:18080/parity/client.js'


class NativeBoundary:
    """Only native controls/capture and a deterministic clock are substituted."""
    def __init__(self, mutation=''):
        self.now = 0.0
        self.actions = []
        self.saved = []
        self.reports = []
        self.checks = []
        self.mutation = mutation
        self.playing = False
        self.media_seconds = 0.0
        self.play_count = 0
        self.late_paused_frame = False

    def invoke(self, name, arguments):
        self.actions.append((name, arguments))
        if self.mutation in {'open-error', 'open-and-close-error'} and name.endswith('.open'):
            raise RuntimeError('native entry unavailable')
        if self.mutation in {'close-error', 'open-and-close-error'} and name.endswith('.close'):
            raise RuntimeError('native close unavailable')
        if name.endswith('.play'):
            self.play_count += 1
            if self.mutation != 'resume-ignored' or self.play_count == 1:
                self.playing = True
        elif name.endswith('.pause') and self.mutation != 'pause-ignored':
            self.playing = False
            self.late_paused_frame = self.mutation == 'pause-in-flight-frame'
        elif name.endswith('.seek') and self.mutation != 'seek-ignored':
            self.media_seconds = arguments['seconds']
            if self.mutation == 'seek-still-playing':
                self.playing = True
        return {'performed': True}

    def assert_session(self, phase):
        self.checks.append(phase)
        if self.mutation == 'restarted' and self.saved:
            raise RuntimeError('observed process identity changed')

    def sleep(self, seconds):
        if self.mutation != 'replayed-clock':
            self.now += seconds
        if self.playing:
            self.media_seconds += seconds

    def capture(self):
        if self.mutation == 'capture-error':
            raise OSError('native capture unavailable')
        number = 0 if self.mutation == 'frozen' else int(self.media_seconds * 12) % 72
        if self.late_paused_frame:
            number = (number - 1) % 72
            self.late_paused_frame = False
        video = Image.frombytes('RGB', (192, 108), generator.frame(number))
        native = Image.new('RGB', (600, 340), 'black')
        native.paste(video.resize((384, 216)), ROI[:2])
        # Unrelated surrounding UI moves even when the native video is frozen.
        dom = int(self.now * 10) % 50
        ImageDraw.Draw(native).rectangle((dom, 0, dom + 20, 30), fill='white')
        output = BytesIO()
        native.save(output, format='PNG')
        return output.getvalue()

    def retain(self, index, content):
        self.saved.append((index, content))
        return f'native-{index}.png'

    def run(self, surface='world', roi=ROI):
        return video_journey(surface, SCRIPT, roi, invoke=self.invoke,
            capture=self.capture, retain=self.retain, assert_session=self.assert_session,
            monotonic=lambda: self.now, sleep=self.sleep, report=self.reports.append)


class WebVideoJourneyTests(unittest.TestCase):
    def test_both_normal_surfaces_use_independent_native_pixels_and_cleanup(self):
        for surface in ('world', 'tablet'):
            with self.subTest(surface=surface):
                native = NativeBoundary()
                observation = native.run(surface)
                self.assertTrue(observation['observations']['play']['movingReferenceVideoPixelsObserved'])
                self.assertTrue(observation['observations']['pause']['pausedReferenceVideoPixelsObserved'])
                self.assertTrue(observation['observations']['seek']['pausedReferenceVideoPixelsObserved'])
                self.assertTrue(observation['observations']['resume']['movingReferenceVideoPixelsObserved'])
                self.assertFalse(observation['deviceAcceptance'])
                self.assertEqual([x[0] for x in native.actions],
                    ['web.reference.open', 'web.reference.play', 'web.reference.pause',
                     'web.reference.seek', 'web.reference.play', 'web.reference.close'])
                self.assertEqual(46, len(native.saved))
                self.assertEqual(46, len(native.reports[0]['captures']))
                self.assertTrue(native.reports[0]['controlSequenceCompleted'])
                self.assertTrue(native.reports[0]['normalCloseSucceeded'])
                self.assertFalse(native.reports[0]['deviceAcceptance'])
                self.assertTrue(all('after' in p or 'before' in p for p in native.checks))

    def test_action_acknowledgments_and_surrounding_motion_cannot_pass_frozen_video(self):
        for surface in ('world', 'tablet'):
            with self.subTest(surface=surface):
                native = NativeBoundary('frozen')
                with self.assertRaisesRegex(AssertionError, 'moving encoded'):
                    native.run(surface)
                report = native.reports[0]
                self.assertFalse(report['observation']['movingReferenceVideoPixelsObserved'])
                self.assertTrue(report['normalCloseSucceeded'])
                self.assertEqual(17, len(report['captures']))

    def test_wrong_capture_rectangle_never_passes(self):
        native = NativeBoundary()
        with self.assertRaises(AssertionError):
            native.run(roi=(0, 0, 192, 108))
        self.assertTrue(native.reports[0]['normalCloseSucceeded'])

    def test_capture_process_and_clock_failures_have_no_success_fallback(self):
        for mutation, kind in [('capture-error', OSError), ('restarted', RuntimeError),
                               ('replayed-clock', ValueError)]:
            with self.subTest(mutation=mutation):
                native = NativeBoundary(mutation)
                with self.assertRaises(kind):
                    native.run()
                self.assertTrue(native.reports[0]['normalCloseSucceeded'])
                self.assertIsNone(native.reports[0]['observation'])

    def test_partial_open_is_closed_and_primary_error_is_preserved(self):
        native = NativeBoundary('open-and-close-error')
        with self.assertRaisesRegex(RuntimeError, 'entry unavailable'):
            native.run()
        self.assertEqual(0, len(native.saved))
        self.assertFalse(native.reports[0]['normalCloseSucceeded'])
        self.assertFalse(native.reports[0]['controlSequenceCompleted'])
        self.assertEqual('web.reference.close', native.actions[-1][0])

    def test_acknowledged_pause_seek_and_resume_must_change_actual_video_pixels(self):
        for mutation, expected in [('pause-ignored', 'stop at a stable'),
                                   ('seek-ignored', 'requested encoded frame'),
                                   ('resume-ignored', 'resume encoded motion'),
                                   ('seek-still-playing', 'retain the requested paused')]:
            with self.subTest(mutation=mutation):
                native = NativeBoundary(mutation)
                with self.assertRaisesRegex(AssertionError, expected):
                    native.run()
                self.assertTrue(native.reports[0]['normalCloseSucceeded'])
                self.assertFalse(native.reports[0]['controlSequenceCompleted'])

    def test_seek_precondition_chooses_a_different_target_for_either_starting_phase(self):
        for offset, target in [(0.0, 48), (3.6, 0)]:
            with self.subTest(offset=offset):
                native = NativeBoundary()
                native.media_seconds = offset
                result = native.run()
                self.assertEqual(target, result['observations']['seek']['encodedFrame'])

    def test_in_flight_frame_does_not_hide_a_correct_bounded_pause_transition(self):
        native = NativeBoundary('pause-in-flight-frame')
        native.run()
        self.assertTrue(native.reports[0]['controlSequenceCompleted'])
        self.assertEqual(7, sum(row['phase'] == 'pause' for row in native.reports[0]['captures']))

    def test_cleanup_failure_prevents_success_even_with_good_pixels(self):
        native = NativeBoundary('close-error')
        with self.assertRaisesRegex(RuntimeError, 'close unavailable'):
            native.run()
        self.assertTrue(native.reports[0]['observation']['movingReferenceVideoPixelsObserved'])
        self.assertFalse(native.reports[0]['normalCloseSucceeded'])
        self.assertFalse(native.reports[0]['controlSequenceCompleted'])

    def test_closed_action_contract_rejects_foreign_sources_and_verdicts(self):
        valid = {'surface': 'world', 'scriptUrl': SCRIPT}
        self.assertEqual(valid, validate_operation_arguments('web.reference.open', valid))
        for arguments in ({'surface': []}, {'surface': 'other'},
                          {'surface': 'world', 'expectedPass': True}):
            with self.assertRaises(ValueError):
                validate_operation_arguments('web.reference.play', arguments)
        for url in ('file:///parity/client.js', 'http://a:b@localhost/parity/client.js',
                    'http://localhost/unowned.js', SCRIPT + '?expected=pass', SCRIPT + '#x',
                    SCRIPT + '\n', 1):
            with self.subTest(url=url), self.assertRaises(ValueError):
                validate_operation_arguments('web.reference.open', valid | {'scriptUrl': url})
        with self.assertRaises(ValueError):
            validate_operation_result('web.reference.play', {'performed': True, 'playbackPassed': True})
        for seconds in (0, 4):
            self.assertEqual(seconds, validate_operation_arguments('web.reference.seek',
                {'surface': 'world', 'seconds': seconds})['seconds'])
        for seconds in (True, -1, 1, 6, '4', 4.0):
            with self.subTest(seconds=seconds), self.assertRaises(ValueError):
                validate_operation_arguments('web.reference.seek', {'surface': 'world', 'seconds': seconds})

    def test_actual_adapter_subprocesses_do_not_receive_assertion_geometry(self):
        from adapter_client import invoke
        spec = importlib.util.spec_from_file_location('web_journey_device_runner', DEVICE / 'run.py')
        runner = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(runner)
        with tempfile.TemporaryDirectory(prefix='overte-video-adapter-boundary-') as tmp:
            root = Path(tmp)
            adapter = root / 'adapter.py'
            adapter.write_text("import os,json\nprint(json.dumps({'visible': sorted(k for k in os.environ "
                "if k in {'OVERTE_E2E_WEB_VIDEO_ROIS','OVERTE_E2E_TABLET_POLICY'})}))\n")
            manifest = root / 'manifest.json'
            manifest.write_text(json.dumps({'schemaVersion': 1, 'command': [str(adapter)]}))
            with patch.dict(os.environ, {'OVERTE_E2E_WEB_VIDEO_ROIS': 'module-only-geometry',
                                       'OVERTE_E2E_TABLET_POLICY': 'module-only-policy'}):
                result = invoke(manifest, 'synthetic-target', 'web.reference.play', {'surface': 'world'})
                self.assertEqual([], result['visible'])
                result = runner.adapter_call([sys.executable, str(adapter)], 'describe',
                                             'synthetic-target', environment=os.environ.copy())
                self.assertEqual([], result['visible'])

    def test_execution_plan_requires_capture_geometry_and_fixture_before_discovery(self):
        from acceptance_policy import load_policy
        from execution_plan import compile_plan, load_profiles
        catalog = DEVICE / 'catalog.json'
        policy = load_policy(DEVICE / 'acceptance-policy.json', catalog)
        profiles = load_profiles(DEVICE / 'execution-profiles.json', catalog)
        environment = {'OVERTE_E2E_WEB_REFERENCE_SCRIPT_URL', 'OVERTE_E2E_WEB_VIDEO_ROIS'}
        for supplied in (set(), {'OVERTE_E2E_WEB_REFERENCE_SCRIPT_URL'}, environment):
            plan = compile_plan(policy, catalog, profiles, 'mock', ['web-video-parity'],
                                supplied, False, set(), 'external')
            self.assertEqual(supplied == environment, plan['ready'])
            self.assertEqual(sorted(environment - supplied), plan['missingInputs'])
            self.assertEqual(['launch-smoke', 'world-web-video', 'tablet-web-video'],
                             plan['suites'][0]['modules'])


if __name__ == '__main__':
    unittest.main()
