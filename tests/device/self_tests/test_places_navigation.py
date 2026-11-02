"""Counterfactual normal Go To/history tests at native UI/read/clock boundaries."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import copy
from pathlib import Path
import sys
import unittest

DEVICE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DEVICE))
from contracts import validate_operation_arguments, validate_operation_result
from navigation_journey import navigation_journey
from navigation_observation import FIXTURE_MARKERS, POSITIONS, project_probe, viewpoint_urls


class NativeBoundary:
    def __init__(self, mutation=''):
        self.scene = 'http://controlled.test:18080/owned/scene.json'
        self.urls = viewpoint_urls(self.scene)
        self.mutation = mutation
        self.now = 0.0
        self.current = self.urls['A']
        self.position = copy.deepcopy(POSITIONS['A'])
        self.history, self.cursor = [self.current], 0
        self.sequence = self.frame = self.go_count = 0
        self.actions, self.reports = [], []
        self.pending_position = None
        self.old_read = None

    def arrive(self, url):
        label = next(key for key, value in self.urls.items() if value == url)
        if self.mutation != 'address-ignored':
            self.current = url
        if self.mutation != 'address-echo-only':
            position = copy.deepcopy(POSITIONS[label])
            if self.mutation == 'arrival-in-flight':
                self.pending_position = (self.now + 0.75, position)
            else:
                self.position = position

    def invoke(self, operation, arguments):
        self.actions.append((operation, copy.deepcopy(arguments)))
        if operation == 'places.open' and self.mutation == 'open-close-error':
            raise RuntimeError('normal Go To entry unavailable')
        if operation == 'places.close' and self.mutation in {'open-close-error', 'close-error'}:
            raise RuntimeError('normal Go To close unavailable')
        if operation == 'places.goto':
            self.go_count += 1
            if self.mutation == 'goto-ignored' or self.mutation == 'restore-ignored' and self.go_count >= 4:
                return {'performed': True}
            self.history = self.history[:self.cursor + 1] + [arguments['url']]
            self.cursor += 1
            self.arrive(arguments['url'])
        if operation == 'places.back' and self.mutation != 'back-ignored':
            self.cursor = max(0, self.cursor - 1)
            self.arrive(self.history[self.cursor])
        if operation == 'places.forward' and self.mutation != 'forward-ignored':
            self.cursor = min(len(self.history) - 1, self.cursor + 1)
            self.arrive(self.history[self.cursor])
        if operation == 'places.goto' and self.mutation == 'extra-verdict':
            return {'performed': True, 'arrived': True}
        return {'performed': True}

    def observe(self):
        self.sequence += 1
        if self.mutation != 'renderer-stalled':
            self.frame += 1
        epoch = 100000 + int(self.now * 1000)
        raw = {'sampleSequence': self.sequence, 'sampleEpochMs': epoch,
            'application': {'foreground': self.mutation != 'background'},
            'domain': {'connected': False, 'serverless': True, 'protocol': 'http'},
            'scene': {'url': self.current, 'fixtureMarkers': list(FIXTURE_MARKERS),
                      'fixtureMarkerCount': len(FIXTURE_MARKERS)},
            'avatar': {'feetPosition': copy.deepcopy(self.position), 'velocity': {'x': 0, 'y': 0, 'z': 0},
                       'inAir': self.pending_position is not None, 'flying': False},
            'render': {'frameCount': self.frame,
                       'lastFrameEpochMs': epoch - (3001 if self.mutation == 'stale-presentation' else 0)}}
        if self.mutation == 'foreign-scene':
            raw['scene']['url'] = self.current.replace('controlled.test', 'unowned.test')
        if self.mutation == 'missing-geometry':
            raw['scene']['fixtureMarkers'].pop()
        if self.mutation == 'in-air':
            raw['avatar']['inAir'] = True
        if self.mutation == 'drifting-avatar':
            raw['avatar']['velocity']['x'] = 1.0
        if self.mutation == 'remote-domain':
            raw['domain'] = {'connected': True, 'serverless': False, 'protocol': 'hifi'}
        if self.mutation == 'nonfinite-position':
            raw['avatar']['feetPosition']['x'] = float('nan')
        if self.mutation == 'malformed-native-probe':
            raw['avatar'].pop('feetPosition')
        value = project_probe(raw)
        if self.mutation == 'replayed-probe':
            if self.old_read is None:
                self.old_read = copy.deepcopy(value)
            return copy.deepcopy(self.old_read)
        return value

    def sleep(self, seconds):
        self.now += -seconds if self.mutation == 'backwards-clock' else seconds
        if self.pending_position is not None and self.now >= self.pending_position[0]:
            self.position = self.pending_position[1]
            self.pending_position = None

    def continuity(self, _phase):
        if self.mutation == 'process-replaced' and self.go_count >= 2:
            raise AssertionError('native application process replaced')

    def run(self):
        return navigation_journey(self.scene, invoke=self.invoke, observe=self.observe,
            assert_session=self.continuity, monotonic=lambda: self.now, sleep=self.sleep,
            report=self.reports.append)


class PlacesNavigationTests(unittest.TestCase):
    def test_goto_and_history_require_actual_stable_scene_and_viewpoint_arrivals(self):
        native = NativeBoundary()
        result = native.run()
        self.assertEqual(['goto-A', 'goto-B', 'goto-C', 'back-to-B', 'back-to-A',
            'forward-to-B', 'forward-to-C', 'cleanup-restored-A'],
            [row['phase'] for row in result['phases']])
        self.assertTrue(native.reports[0]['sequenceCompleted'])
        self.assertTrue(native.reports[0]['cleanupSucceeded'])
        self.assertFalse(native.reports[0]['deviceAcceptance'])
        self.assertTrue(all(row['stableAdvancingSamples'] >= 3 for row in result['phases']))
        self.assertEqual(native.urls['A'], native.current)
        self.assertEqual('places.close', native.actions[-1][0])

    def test_arrival_waits_for_native_grounding_after_real_navigation_delay(self):
        native = NativeBoundary('arrival-in-flight')
        native.run()
        self.assertTrue(native.reports[0]['sequenceCompleted'])
        self.assertTrue(all(not row['lastObservation']['inAir'] for row in native.reports[0]['phases']))

    def test_acknowledged_but_ignored_goto_history_and_address_echo_cannot_pass(self):
        for mutation in ('goto-ignored', 'back-ignored', 'forward-ignored',
                         'address-echo-only', 'address-ignored', 'foreign-scene'):
            with self.subTest(mutation=mutation):
                native = NativeBoundary(mutation)
                with self.assertRaises(AssertionError):
                    native.run()
                self.assertFalse(native.reports[0]['sequenceCompleted'])
                self.assertEqual('places.close', native.actions[-1][0])

    def test_missing_native_geometry_or_unhealthy_presentation_does_not_qualify(self):
        for mutation in ('renderer-stalled', 'stale-presentation', 'missing-geometry',
                         'in-air', 'drifting-avatar', 'background', 'remote-domain'):
            with self.subTest(mutation=mutation):
                native = NativeBoundary(mutation)
                with self.assertRaises(AssertionError):
                    native.run()
                self.assertFalse(native.reports[0]['sequenceCompleted'])

    def test_frozen_malformed_native_reads_and_invalid_clock_fail(self):
        for mutation in ('replayed-probe', 'nonfinite-position', 'malformed-native-probe',
                         'backwards-clock', 'extra-verdict'):
            with self.subTest(mutation=mutation):
                native = NativeBoundary(mutation)
                with self.assertRaises(ValueError):
                    native.run()
                self.assertFalse(native.reports[0]['sequenceCompleted'])

    def test_cleanup_restore_is_independently_observed_and_ignored_restore_fails(self):
        native = NativeBoundary('restore-ignored')
        with self.assertRaisesRegex(AssertionError, 'cleanup-restored-A'):
            native.run()
        self.assertFalse(native.reports[0]['sequenceCompleted'])
        self.assertFalse(native.reports[0]['cleanupSucceeded'])
        self.assertEqual('places.close', native.actions[-1][0])

    def test_primary_error_and_process_replacement_still_attempt_owned_panel_cleanup(self):
        native = NativeBoundary('open-close-error')
        with self.assertRaisesRegex(RuntimeError, 'entry unavailable'):
            native.run()
        self.assertFalse(native.reports[0]['controlledRestoreEnabled'])
        self.assertEqual('places.close', native.actions[-1][0])
        native = NativeBoundary('process-replaced')
        with self.assertRaisesRegex(AssertionError, 'process replaced'):
            native.run()
        self.assertEqual('places.close', native.actions[-1][0])
        native = NativeBoundary('close-error')
        with self.assertRaisesRegex(RuntimeError, 'close unavailable'):
            native.run()
        self.assertFalse(native.reports[0]['sequenceCompleted'])

    def test_closed_inputs_reject_foreign_shapes_and_result_verdicts(self):
        url = NativeBoundary().urls['B']
        self.assertEqual({'url': url}, validate_operation_arguments('places.goto', {'url': url}))
        for candidate in (url + '&expected=pass', url + '&evil=', url + '#pass',
                          url.replace('/scene.json', '/private.json'),
                          url.replace('http:', 'file:'), url.replace('/2,0,4/', '/2000,0,4/')):
            with self.subTest(candidate=candidate), self.assertRaises(ValueError):
                validate_operation_arguments('places.goto', {'url': candidate})
        with self.assertRaises(ValueError):
            validate_operation_arguments('places.back', {'target': url})
        with self.assertRaises(ValueError):
            validate_operation_arguments('places.fake', {})
        with self.assertRaises(ValueError):
            validate_operation_result('places.goto', {'performed': True, 'arrived': True})

    def test_catalog_execution_profile_requires_a_scene_before_discovery(self):
        from acceptance_policy import load_policy
        from execution_plan import compile_plan, load_profiles
        catalog = DEVICE / 'catalog.json'
        policy = load_policy(DEVICE / 'acceptance-policy.json', catalog)
        profiles = load_profiles(DEVICE / 'execution-profiles.json', catalog)
        for provider, keys, missing in (('none', set(), ['fixture:scene']),
                ('external', set(), ['OVERTE_E2E_SCENE_URL']), ('auto', set(), []),
                ('external', {'OVERTE_E2E_SCENE_URL'}, [])):
            with self.subTest(provider=provider):
                plan = compile_plan(policy, catalog, profiles, 'mock', ['places-navigation-parity'],
                                    keys, False, set(), provider)
                self.assertEqual(not missing, plan['ready'])
                self.assertEqual(missing, plan['missingInputs'])
                self.assertEqual(['launch-smoke', 'places-navigation'], plan['suites'][0]['modules'])


if __name__ == '__main__':
    unittest.main()
