"""Real normal-input flow and journey engine at explicit native W3C/probe seams."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlencode, urlsplit

DEVICE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DEVICE))
sys.path.insert(0, str(DEVICE / 'adapters/android-phone'))
from overte_phone_navigation_scene import configuration as scene_configuration
from adapters.normal_ui import NativeUI, NativeUIError, W3C_ELEMENT
from adapters.phone_navigation import PhoneNavigation, PROFILE, PACKAGE, validate_profile, validate_state, controlled_domain_url
from adapters.shared_appium.adapter import AppiumAdapter
from navigation_journey import navigation_journey
from navigation_observation import project_probe


class NativePhone:
    """Only native W3C UI, world/probe reads, clock and guard are substituted."""
    def __init__(self, mutation=''):
        self.clock = 0.0
        self.mutation = mutation
        self.address_open = False
        self.address_enabled = True
        self.screen = None
        self.last_screen = 'settings'  # Reopening a tablet need not show Home.
        self.field = ''
        self.scene = 'http://controlled.test:18080/owned/scene.json'
        self.current = self.scene + '?location=/0,0,4/0,0,0,1'
        self.position = {'x': 0, 'y': 0, 'z': 4}
        self.history, self.cursor = [self.current], 0
        self.sequence = self.frame = 0
        self.calls, self.inputs, self.reports, self.saved = [], [], [], []
        self.fail_next_read = False
        self.state = {'sessionId': 'owned-session', 'generation': 1}
        self.identity = {'schemaVersion': 1, 'sourceRevision': '1' * 40,
                         'artifactSha256': '2' * 64, 'installedCandidateVerified': True}
        self.process = '31415:stable-process-start'
        self.profile = {'contractVersion': 1, 'profile': PROFILE, 'sceneUrl': self.scene}
        names = ['Go to destination', 'PLACES', 'PhoneAddressField', 'PhoneAddressGoButton',
                 'PhoneAddressCancelButton', 'tablet.open', 'nav.close', 'nav.home', 'goBack', 'goForward']
        self.references = {name: 'n' + str(index) for index, name in enumerate(names)}
        self.by_reference = {value: key for key, value in self.references.items()}
        self.ui = NativeUI(self, 'owned-session', lambda: None, timeout=0.8,
                           monotonic=lambda: self.clock, sleep=self.sleep)
        data = json.loads((DEVICE / 'fixture/scene.json').read_text())
        self.markers = sorted(row['name'] for row in data['Entities']
                              if row['name'] in {'OVERTE_E2E_COLLISION_WALL', 'OVERTE_E2E_EAST',
                                  'OVERTE_E2E_FLOOR', 'OVERTE_E2E_NORTH', 'OVERTE_E2E_ORIGIN'})

    def visible(self, name):
        if name in {'Go to destination', 'tablet.open'}:
            return not self.address_open and self.screen is None
        if name in {'PhoneAddressField', 'PhoneAddressGoButton', 'PhoneAddressCancelButton'}:
            return self.address_open
        if name == 'nav.close': return self.screen is not None
        if name == 'nav.home': return self.screen not in {None, 'home'}
        if name == 'PLACES': return self.screen == 'home'
        if name in {'goBack', 'goForward'}: return self.screen == 'places'
        return False

    def arrive(self, url):
        self.current = url
        path = parse_qs(urlsplit(url).query)['location'][0]
        coordinates = [float(item) for item in path.split('/')[1].split(',')]
        self.position = dict(zip(('x', 'y', 'z'), coordinates))

    def call(self, method, path, body=None):
        self.calls.append((method, path, copy.deepcopy(body)))
        if path.endswith('/elements'):
            if self.fail_next_read:
                self.fail_next_read = False
                raise RuntimeError('native page cache temporarily unavailable')
            value = body['value']
            name = value.removeprefix(PACKAGE + ':id/')
            if not self.visible(name): return []
            return [{W3C_ELEMENT: self.references[name]}]
        if '/element/' in path:
            reference = path.split('/element/', 1)[1].split('/')[0]
            name = self.by_reference[reference]
            if path.endswith('/displayed'): return self.visible(name)
            if path.endswith('/enabled'):
                if name == 'goBack': return self.cursor > 0
                if name == 'goForward': return self.cursor < len(self.history) - 1
                return self.address_enabled if name == 'PhoneAddressField' else True
            if path.endswith('/clear'):
                self.field = ''
                return None
            if path.endswith('/value'):
                if self.mutation != 'text-ignored':
                    self.field = body['text']
                return None
            if path.endswith('/text'):
                return self.field
            if path.endswith('/click'):
                self.inputs.append(name)
                if name == 'Go to destination':
                    self.address_open = self.mutation != 'entry-ignored'
                    if self.mutation == 'partial-entry-read-error': self.fail_next_read = True
                elif name == 'PhoneAddressCancelButton':
                    self.address_open = False
                elif name == 'PhoneAddressGoButton':
                    self.address_open = False
                    if self.mutation != 'goto-ignored':
                        self.history = self.history[:self.cursor + 1] + [self.field]
                        self.cursor += 1
                        self.arrive(self.field)
                elif name == 'tablet.open': self.screen = self.last_screen
                elif name == 'nav.close':
                    self.last_screen, self.screen = self.screen, None
                elif name == 'nav.home': self.screen = 'home'
                elif name == 'PLACES': self.screen = 'places'
                elif name == 'goBack' and self.mutation != 'back-ignored':
                    self.cursor = max(0, self.cursor - 1)
                    self.arrive(self.history[self.cursor])
                elif name == 'goForward' and self.mutation != 'forward-ignored':
                    self.cursor = min(len(self.history) - 1, self.cursor + 1)
                    self.arrive(self.history[self.cursor])
                return None
        if method == 'DELETE' and path.endswith('/actions'): return None
        raise AssertionError('Unexpected native W3C endpoint')

    def sleep(self, seconds): self.clock += seconds

    def save(self):
        # Model the real CLI's atomic JSON state handoff to its next process.
        self.saved.append(json.loads(json.dumps(self.state)))

    def flow(self):
        return PhoneNavigation(self.ui, self.profile, self.state,
                               self.identity, self.process, self.save)

    def invoke(self, operation, arguments):
        result = self.flow().invoke(operation, arguments)
        self.state = json.loads(json.dumps(self.state))
        return result

    def observe(self):
        self.sequence += 1
        self.frame += 1
        epoch = 100000 + int(self.clock * 1000)
        return project_probe({'sampleSequence': self.sequence, 'sampleEpochMs': epoch,
            'application': {'foreground': True},
            'domain': {'connected': False, 'serverless': True, 'protocol': 'http'},
            'scene': {'url': self.current, 'fixtureMarkers': self.markers, 'fixtureMarkerCount': len(self.markers)},
            'avatar': {'feetPosition': copy.deepcopy(self.position), 'velocity': {'x': 0, 'y': 0, 'z': 0},
                       'inAir': False, 'flying': False},
            'render': {'frameCount': self.frame, 'lastFrameEpochMs': epoch}})

    def run(self):
        return navigation_journey(self.scene, invoke=self.invoke, observe=self.observe,
            assert_session=lambda _phase: None, monotonic=lambda: self.clock,
            sleep=self.sleep, report=self.reports.append)


class PhoneNavigationTests(unittest.TestCase):
    DOMAIN = 'hifi://controlled.test:40102/0.0,0.0,4.0/0,0,0,1'

    def domain_adapter(self, native, *, changed_process=False):
        from appium_adapter import PhoneAppiumAdapter
        adapter = object.__new__(PhoneAppiumAdapter)
        adapter.candidate = object()  # Actual installed identity is an explicit host seam below.
        target = {'controls': {'normalNavigation': native.profile}, 'scene': {'kind': 'android-debug-e2e'}}
        native.state['targetFingerprint'] = 'actual-host-bound-fingerprint'
        adapter.target = lambda _selector: target
        adapter.advertised_capabilities = lambda _target: {'navigation.enter-domain'}
        adapter.controlled_android_client = lambda _target: True
        adapter.ensure_session = lambda _selector: (native, 'owned-session', native.state)
        adapter.installed_identity = lambda _selector: copy.deepcopy(native.identity)
        adapter.process_state = lambda *_args: {'running': True, 'identity':
            'changed-process' if changed_process and native.field else native.process}
        adapter.read_session = lambda _selector: native.state
        adapter.snapshot_fingerprint = lambda _target: 'actual-host-bound-fingerprint'
        adapter.query_app_state = lambda *_args: 4
        adapter.save_session = lambda _selector, _state: native.save()
        adapter.write_android_client_command = lambda *_args: self.fail('Private command channel must not receive domain input')
        return adapter

    def domain_environment(self):
        return {'OVERTE_E2E_DOMAIN_URL': self.DOMAIN, 'OVERTE_E2E_DOMAIN_HOST': 'controlled.test'}

    def test_controlled_domain_uses_actual_phone_dispatch_normal_editor_and_exact_text(self):
        native = NativePhone()
        native.arrive = lambda url: setattr(native, 'current', url)
        adapter = self.domain_adapter(native)
        with patch.dict(os.environ, self.domain_environment(), clear=True):
            result = adapter.invoke('owned-target', 'navigation.enter-domain', {'url': self.DOMAIN})
        self.assertEqual({'requested': True}, result)
        self.assertEqual(self.DOMAIN, native.field)
        self.assertEqual(['Go to destination', 'PhoneAddressGoButton'], native.inputs)
        self.assertFalse(native.address_open)
        self.assertFalse(native.state['normalNavigation']['addressOwned'])
        self.assertNotIn('connected', result)  # Input receipt is no connection measurement.

    def test_domain_foreign_malformed_and_unversioned_inputs_fail_before_sdk_or_input(self):
        bad = [self.DOMAIN.replace('controlled.test', 'foreign.test'), self.DOMAIN + '?foreign=1',
            self.DOMAIN + '#foreign', self.DOMAIN.replace('://', '://user@'),
            self.DOMAIN.replace(':40102', ''), self.DOMAIN.replace('hifi:', 'https:'),
            self.DOMAIN.replace(':40102', ':0'),
            self.DOMAIN + '\n', 'hifi://controlled.test:40102/' + 'a' * 2048]
        for url in bad:
            with self.subTest(url=url):
                native = NativePhone(); adapter = self.domain_adapter(native)
                adapter.ensure_session = lambda _selector: self.fail('Invalid domain input reached SDK session')
                with patch.dict(os.environ, self.domain_environment(), clear=True):
                    with self.assertRaises((NativeUIError, ValueError)):
                        adapter.invoke('owned-target', 'navigation.enter-domain', {'url': url})
                self.assertEqual([], native.calls)
        for changes in ({'OVERTE_E2E_DOMAIN_HOST': 'foreign.test'}, {'OVERTE_E2E_DOMAIN_URL': ''}):
            native = NativePhone(); adapter = self.domain_adapter(native)
            adapter.ensure_session = lambda _selector: self.fail('Unbound domain input reached SDK')
            with patch.dict(os.environ, self.domain_environment() | changes, clear=True):
                with self.assertRaises((NativeUIError, ValueError)):
                    adapter.invoke('owned-target', 'navigation.enter-domain', {'url': self.DOMAIN})
        native = NativePhone(); native.profile['contractVersion'] = 2
        adapter = self.domain_adapter(native)
        adapter.ensure_session = lambda _selector: self.fail('Foreign profile version reached SDK')
        with patch.dict(os.environ, self.domain_environment(), clear=True), self.assertRaises(ValueError):
            adapter.invoke('owned-target', 'navigation.enter-domain', {'url': self.DOMAIN})
        native = NativePhone(); adapter = self.domain_adapter(native); adapter.candidate = None
        adapter.ensure_session = lambda _selector: self.fail('Unbound domain input reached SDK')
        with patch.dict(os.environ, self.domain_environment(), clear=True), self.assertRaises(ValueError):
            adapter.invoke('owned-target', 'navigation.enter-domain', {'url': self.DOMAIN})

    def test_domain_ignored_text_foreign_editor_and_changed_process_never_press_go(self):
        for kind in ('text-ignored', 'foreign-editor', 'changed-process'):
            with self.subTest(kind=kind):
                native = NativePhone('text-ignored' if kind == 'text-ignored' else '')
                if kind == 'foreign-editor': native.address_open = True
                adapter = self.domain_adapter(native, changed_process=kind == 'changed-process')
                with patch.dict(os.environ, self.domain_environment(), clear=True), self.assertRaises(NativeUIError):
                    adapter.invoke('owned-target', 'navigation.enter-domain', {'url': self.DOMAIN})
                self.assertNotIn('PhoneAddressGoButton', native.inputs)
                if kind == 'foreign-editor': self.assertEqual([], native.inputs)
                else: self.assertTrue(native.state['normalNavigation']['addressOwned'])

    def test_ignored_domain_input_stays_red_in_original_independent_session_effect_check(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {
                'OVERTE_DEVICE_ADAPTER_MANIFEST': str(Path(directory) / 'host-seam-manifest.json'),
                'OVERTE_DEVICE_TARGET_SELECTOR': 'host-seam-target',
                'OVERTE_DEVICE_ARTIFACT_DIR': directory}):
            import overte_session
            from module_support import AssertionFailure
        native = NativePhone('goto-ignored'); adapter = self.domain_adapter(native)
        original_url = native.current
        session = overte_session.OverteSession.__new__(overte_session.OverteSession)
        session.timeout_seconds = .3; session.poll_seconds = .1
        samples = []
        def snapshot(_artifact=None):
            sample = {'sampleSequence': len(samples) + 1, 'sampleEpochMs': 100000 + len(samples) * 100,
                      'domain': {'connected': False, 'serverless': True, 'protocol': 'http'},
                      'scene': {'url': native.current, 'entityCount': 6, 'domainMarkers': [], 'domainMarkerCount': 0}}
            samples.append(copy.deepcopy(sample)); return sample
        session.snapshot = snapshot
        receipts = []
        def dispatch(operation, arguments):
            receipt = adapter.invoke('owned-target', operation, arguments)
            receipts.append(receipt); return receipt
        environment = self.domain_environment() | {
            'OVERTE_E2E_DOMAIN_ID': '12345678-1234-4234-9234-123456789012',
            'OVERTE_E2E_DOMAIN_MARKERS_JSON': '["OVERTE_E2E_DOMAIN_ORIGIN"]'}
        with patch.dict(os.environ, environment, clear=True), \
                patch.object(overte_session, 'process_identity', return_value=native.process), \
                patch.object(overte_session, 'assert_foreground'), \
                patch.object(overte_session, 'operation', side_effect=dispatch), \
                patch.object(overte_session, 'write_json'), \
                patch.object(overte_session.time, 'monotonic', side_effect=lambda: native.clock), \
                patch.object(overte_session.time, 'sleep', side_effect=native.sleep):
            with self.assertRaisesRegex(AssertionFailure, 'controlled domain did not become connected'):
                session.enter_controlled_domain()
        self.assertEqual([{'requested': True}], receipts)
        self.assertEqual(original_url, native.current)
        self.assertGreaterEqual(len(samples), 3)
        self.assertTrue(all(not value['domain']['connected'] for value in samples))

    def test_two_fresh_absence_reads_survive_slow_guards_only_with_supported_bound(self):
        class SlowClosePhone(NativePhone):
            # Explicit latency/visibility seam only, not a claim about Job15's
            # unretained response values. Each complete guard costs 1.5s;
            # the dialog closes within 8.5s of wait_absent starting.
            def __init__(self, timeout, ignored=False, foreign=False):
                super().__init__()
                self.close_at = None; self.lookups = []; self.ignored = ignored
                def guard():
                    self.clock += 1.5
                    if foreign and self.field: raise RuntimeError('Host process boundary changed')
                self.ui = NativeUI(self, 'owned-session', guard, timeout=timeout,
                    monotonic=lambda: self.clock, sleep=self.sleep)

            def call(self, method, path, body=None):
                if self.close_at is not None and self.clock >= self.close_at:
                    self.address_open = False
                if path.endswith('/click') and '/element/' in path:
                    name = self.by_reference[path.split('/element/', 1)[1].split('/')[0]]
                    if name == 'PhoneAddressGoButton':
                        self.inputs.append(name)
                        if not self.ignored: self.close_at = self.clock + 10.0
                        return None
                value = super().call(method, path, body)
                if path.endswith('/elements') and body['value'].endswith('PhoneAddressField') and 'PhoneAddressGoButton' in self.inputs:
                    self.lookups.append((self.clock, bool(value)))
                return value

        short = SlowClosePhone(10)
        with self.assertRaisesRegex(NativeUIError, 'control did not disappear'):
            short.flow().enter_domain(self.DOMAIN, self.DOMAIN, 'controlled.test')
        self.assertEqual(1, short.inputs.count('PhoneAddressGoButton'))
        self.assertFalse(short.address_open)
        self.assertEqual(1, len([clock for clock, present in short.lookups if not present]))
        self.assertTrue(short.state['normalNavigation']['addressOwned'])
        bounded = SlowClosePhone(20)
        self.assertEqual({'requested': True}, bounded.flow().enter_domain(self.DOMAIN, self.DOMAIN, 'controlled.test'))
        absent = [clock for clock, present in bounded.lookups if not present]
        self.assertEqual(2, len(absent)); self.assertGreaterEqual(absent[1] - absent[0], .3)
        self.assertEqual(1, bounded.inputs.count('PhoneAddressGoButton'))
        self.assertFalse(bounded.state['normalNavigation']['addressOwned'])
        self.assertNotEqual(self.DOMAIN, bounded.current)  # No world arrival was synthesized.
        ignored = SlowClosePhone(20, ignored=True)
        with self.assertRaises(NativeUIError): ignored.flow().enter_domain(self.DOMAIN, self.DOMAIN, 'controlled.test')
        self.assertTrue(ignored.address_open); self.assertTrue(ignored.state['normalNavigation']['addressOwned'])
        self.assertEqual(1, ignored.inputs.count('PhoneAddressGoButton'))
        changed = SlowClosePhone(20, foreign=True)
        with self.assertRaises(NativeUIError): changed.flow().enter_domain(self.DOMAIN, self.DOMAIN, 'controlled.test')
        self.assertNotIn('PhoneAddressGoButton', changed.inputs)

    def test_scene_input_accepts_the_exact_approved_controlled_spawn_query(self):
        from navigation_observation import arrived, VIEWPOINTS
        for label, location in VIEWPOINTS.items():
            with self.subTest(label=label):
                native = NativePhone()
                approved = native.scene + '?' + urlencode({'location': location})
                native.profile['sceneUrl'] = approved
                self.assertIs(native.profile, scene_configuration(native.profile, approved, approved))
                native.arrive(native.scene + '?location=/0,0,4/0,0,0,1'
                              if label != 'A' else native.scene + '?location=/2,0,4/0,0,0,1')
                self.assertFalse(arrived(native.observe(), approved, label))
                self.assertEqual({'requested': True}, native.flow().load_scene(approved))
                self.assertEqual(approved, native.field)
                self.assertEqual(['Go to destination', 'PhoneAddressGoButton'], native.inputs)
                self.assertTrue(arrived(native.observe(), approved, label))
                self.assertFalse(native.address_open)
                self.assertFalse(native.state['normalNavigation']['addressOwned'])

    def test_scene_input_keeps_foreign_query_and_ignored_input_counterexamples_red(self):
        from navigation_observation import arrived
        native = NativePhone()
        approved = native.scene + '?' + urlencode({'location': '/0,0,4/0,0,0,1'})
        native.profile['sceneUrl'] = approved
        for url in (native.scene, native.scene + '?location=/2,0,4/0,0,0,1',
                    approved + '&foreign=1', approved + '&location=/0,0,4/0,0,0,1',
                    approved + '#foreign', approved.replace('controlled.test', 'foreign.test'),
                    native.scene + '?' + urlencode({'location': '/0,0,99/0,0,0,1'})):
            with self.subTest(url=url):
                with self.assertRaises((NativeUIError, ValueError)):
                    scene_configuration(native.profile, url, approved)
                with self.assertRaises((NativeUIError, ValueError)):
                    native.flow().load_scene(url)
                self.assertEqual([], native.inputs)
        ignored = NativePhone('goto-ignored')
        ignored.profile['sceneUrl'] = approved
        ignored.arrive(ignored.scene + '?location=/2,0,4/0,0,0,1')
        self.assertEqual({'requested': True}, ignored.flow().load_scene(approved))
        self.assertFalse(arrived(ignored.observe(), approved, 'A'))
        ignored_text = NativePhone('text-ignored')
        ignored_text.profile['sceneUrl'] = approved
        with self.assertRaises(NativeUIError):
            ignored_text.flow().load_scene(approved)
        self.assertNotIn('PhoneAddressGoButton', ignored_text.inputs)
        self.assertTrue(ignored_text.state['normalNavigation']['addressOwned'])
        ignored_text.invoke('places.close', {})
        self.assertFalse(ignored_text.address_open)

    def test_scene_admission_requires_exact_independent_environment_binding(self):
        native = NativePhone()
        approved = native.scene + '?' + urlencode({'location': '/0,0,4/0,0,0,1'})
        native.profile['sceneUrl'] = approved
        for environment in ('', None, native.scene,
                            approved.replace('controlled.test', 'foreign.test'),
                            native.scene + '?' + urlencode({'location': '/2,0,4/0,0,0,1'})):
            with self.subTest(environment=environment), self.assertRaises((NativeUIError, ValueError)):
                scene_configuration(native.profile, approved, environment)
        self.assertEqual([], native.inputs)
        self.assertIs(native.profile, scene_configuration(native.profile, approved, approved))
        query_free = dict(native.profile, sceneUrl=native.scene)
        self.assertIs(query_free, scene_configuration(query_free, native.scene, native.scene))

    def test_real_w3c_normal_flow_drives_the_actual_journey_oracle_and_persists_ownership(self):
        native = NativePhone()
        result = native.run()
        self.assertEqual(8, len(result['phases']))
        self.assertTrue(native.reports[0]['sequenceCompleted'])
        self.assertFalse(native.reports[0]['deviceAcceptance'])
        self.assertIn('Go to destination', native.inputs)
        self.assertIn('PhoneAddressGoButton', native.inputs)
        self.assertIn('PLACES', native.inputs)
        self.assertEqual(2, native.inputs.count('goBack'))
        self.assertEqual(2, native.inputs.count('goForward'))
        self.assertIn('nav.home', native.inputs)  # Original closed Settings page.
        self.assertIsNone(native.screen)
        self.assertFalse(native.address_open)
        self.assertNotIn('normalNavigation', native.state)
        self.assertTrue(any(state.get('normalNavigation', {}).get('addressOwned') for state in native.saved))
        self.assertTrue(any(state.get('normalNavigation', {}).get('tabletOwned') for state in native.saved))
        self.assertFalse(any('/execute' in row[1] for row in native.calls))

    def test_history_endpoints_allow_only_the_selected_enabled_direction(self):
        native = NativePhone()
        # The normal public profile accepts exactly its independently defined viewpoints.
        from navigation_observation import viewpoint_urls
        destination = viewpoint_urls(native.scene)['B']
        native.invoke('places.goto', {'url': destination})
        native.invoke('places.back', {})  # Forward was disabled at the end.
        self.assertEqual(native.cursor, 0)
        native.invoke('places.forward', {})  # Back was disabled at the start.
        self.assertEqual(native.cursor, 1)
        count = native.inputs.count('goForward')
        with self.assertRaises(NativeUIError):
            native.invoke('places.forward', {})
        self.assertEqual(native.inputs.count('goForward'), count)
        native.invoke('places.close', {})
        self.assertNotIn('normalNavigation', native.state)

    def test_acknowledged_but_ignored_native_navigation_and_history_cannot_pass(self):
        for mutation in ('goto-ignored', 'back-ignored', 'forward-ignored'):
            with self.subTest(mutation=mutation):
                native = NativePhone(mutation)
                with self.assertRaises(AssertionError): native.run()
                self.assertFalse(native.reports[0]['sequenceCompleted'])
                self.assertIsNone(native.screen)
                self.assertFalse(native.address_open)

    def test_preexisting_address_or_tablet_is_never_taken_over_or_closed(self):
        for panel in ('address', 'tablet'):
            with self.subTest(panel=panel):
                native = NativePhone()
                if panel == 'address': native.address_open = True
                else: native.screen = 'settings'
                with self.assertRaises(NativeUIError): native.invoke('places.open', {})
                self.assertEqual({'performed': True}, native.invoke('places.close', {}))
                self.assertEqual([], native.inputs)
                self.assertEqual(panel == 'address', native.address_open)
                self.assertEqual('settings' if panel == 'tablet' else None, native.screen)

    def test_partial_entry_keeps_cleanup_intent_and_later_close_is_idempotent(self):
        native = NativePhone('partial-entry-read-error')
        with self.assertRaises(NativeUIError): native.invoke('places.open', {})
        self.assertTrue(native.state['normalNavigation']['addressOwned'])
        self.assertTrue(native.address_open)
        native.invoke('places.close', {})
        self.assertFalse(native.address_open)
        count = len(native.inputs)
        native.invoke('places.close', {})
        self.assertEqual(count, len(native.inputs))

    def test_disabled_owned_field_still_allows_its_real_cancel_cleanup(self):
        native = NativePhone()
        native.invoke('places.open', {})
        native.address_enabled = False
        native.invoke('places.close', {})
        self.assertIn('PhoneAddressCancelButton', native.inputs)
        self.assertFalse(native.address_open)

    def test_ignored_entry_fails_after_bounded_actual_ui_wait_and_retains_partial_cleanup(self):
        native = NativePhone('entry-ignored')
        with self.assertRaises(NativeUIError): native.invoke('places.open', {})
        self.assertTrue(native.state['normalNavigation']['addressOwned'])
        self.assertLessEqual(native.clock, 1)
        native.invoke('places.close', {})
        self.assertNotIn('normalNavigation', native.state)

    def test_changed_process_source_artifact_or_unverified_binding_is_rejected_before_ui(self):
        for field, replacement in (('processIdentity', 'other-process'),
                                    ('sourceRevision', '3' * 40), ('artifactSha256', '4' * 64)):
            with self.subTest(field=field):
                native = NativePhone()
                native.invoke('places.open', {})
                native.state['normalNavigation'][field] = replacement
                native.calls.clear()
                with self.assertRaises(NativeUIError): native.invoke('places.close', {})
                self.assertEqual([], native.calls)
        native = NativePhone()
        native.identity['installedCandidateVerified'] = False
        with self.assertRaises(NativeUIError): native.flow()
        self.assertEqual([], native.calls)

    def test_foreign_scene_and_invalid_profile_or_state_are_rejected_without_input(self):
        native = NativePhone()
        foreign = native.current.replace('controlled.test', 'foreign.test')
        with self.assertRaises(NativeUIError): native.invoke('places.goto', {'url': foreign})
        self.assertEqual([], native.inputs)
        for update in ({'contractVersion': True}, {'profile': 'arbitrary-script'}, {'script': 'execute'},
                       {'sceneUrl': 'file:///unowned/scene.json'}):
            with self.subTest(update=update), self.assertRaises(ValueError):
                validate_profile(native.profile | update)
        with self.assertRaises(ValueError):
            validate_state({'sourceRevision': '1' * 40})
        with self.assertRaisesRegex(RuntimeError, 'configuration is invalid'):
            AppiumAdapter.validate_controls({'normalNavigation': native.profile | {'script': 'execute'}})

    def test_real_shared_configuration_accepts_only_explicit_controlled_phone_profile_without_advertising_it(self):
        native = NativePhone()
        target = {'selector': 'synthetic-target', 'displayName': 'Synthetic native endpoint',
            'platform': 'android', 'physical': True, 'enabled': True,
            'serverUrl': 'http://127.0.0.1:4723', 'appId': PACKAGE,
            'capabilities': {'platformName': 'Android', 'appium:automationName': 'UiAutomator2',
                             'appium:appPackage': PACKAGE, 'appium:autoLaunch': False,
                             'appium:udid': 'synthetic-native-endpoint'},
            'process': {'kind': 'adb'}, 'scene': {'kind': 'android-debug-e2e'},
            'probe': {'kind': 'android-run-as', 'relativePath': AppiumAdapter.ANDROID_DEBUG_PROBE},
            'clientControl': {'kind': 'android-run-as-command',
                              'relativePath': AppiumAdapter.ANDROID_CLIENT_COMMAND},
            'controls': {'normalNavigation': native.profile}}
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'private-targets.json'
            path.write_text(json.dumps({'schemaVersion': 1, 'targets': [target]}))
            path.chmod(0o600)
            with patch.dict(os.environ, {'OVERTE_APPIUM_TARGETS': str(path)}):
                adapter = AppiumAdapter('android')  # Parsing only; no discovery/session.
                capabilities = adapter.advertised_capabilities(adapter.target('synthetic-target'))
                self.assertFalse(any(item.startswith('places.') for item in capabilities))
                for update in ({'appId': 'org.overte.unowned'}, {'clientControl': {}},
                               {'platform': 'ios'}, {'physical': False}):
                    with self.subTest(update=update):
                        changed = target | update
                        path.write_text(json.dumps({'schemaVersion': 1, 'targets': [changed]}))
                        # Select that platform so malformed peer data is not
                        # intentionally skipped by the existing parser.
                        with self.assertRaises(RuntimeError):
                            AppiumAdapter(changed['platform'])

    def test_real_private_session_reader_preserves_bound_ownership_and_rejects_malformed_flags(self):
        native = NativePhone()
        native.invoke('places.open', {})
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'session.json'
            adapter = object.__new__(AppiumAdapter)
            adapter.state_path = lambda _selector: path
            adapter.save_session('synthetic-target', native.state)
            self.assertEqual(0o600, path.stat().st_mode & 0o777)
            self.assertEqual(native.state, adapter.read_session('synthetic-target'))
            native.state['normalNavigation']['addressOwned'] = 'true'
            adapter.save_session('synthetic-target', native.state)
            with self.assertRaisesRegex(RuntimeError, 'ownership state is invalid'):
                adapter.read_session('synthetic-target')

    def test_secondary_input_release_failure_does_not_hide_primary_owned_panel_failure(self):
        native = NativePhone()
        native.invoke('places.open', {})
        native.fail_next_read = True
        def failed_release(): raise RuntimeError('secondary input release unavailable')
        native.ui.release_actions = failed_release
        with self.assertRaisesRegex(NativeUIError, 'native UI transport failed'):
            native.invoke('places.close', {})
        self.assertTrue(native.state['normalNavigation']['addressOwned'])


if __name__ == '__main__': unittest.main()
