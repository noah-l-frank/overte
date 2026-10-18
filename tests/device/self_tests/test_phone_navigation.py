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
from urllib.parse import parse_qs, urlsplit

DEVICE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DEVICE))
from adapters.normal_ui import NativeUI, NativeUIError, W3C_ELEMENT
from adapters.phone_navigation import PhoneNavigation, PROFILE, PACKAGE, validate_profile, validate_state
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
                return self.address_enabled if name == 'PhoneAddressField' else True
            if path.endswith('/clear'):
                self.field = ''
                return None
            if path.endswith('/value'):
                self.field = body['text']
                return None
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
