"""Actual iOS UI flow and journey oracle with explicit OS/UI/world boundaries."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import importlib.util
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import uuid

DEVICE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(DEVICE))
from adapters.normal_ui import NativeUIError
from ios.adapters import normal_input, normal_navigation
from ios.self_tests.test_ios_normal_input import Boundary

# Load this one shared native boundary by its exact source path. Adding the
# shared self-test directory globally makes its test_voice_roundtrip shadow the
# distinct iOS test of the same name during full unittest discovery.
_spec = importlib.util.spec_from_file_location('_overte_ios_phone_native_boundary',
    DEVICE / 'self_tests/test_phone_navigation.py')
_boundary_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_boundary_module)
NativePhone = _boundary_module.NativePhone


class IOSBoundary(NativePhone):
    """W3C controls/world have the shared boundary; real iOS Python logic is used."""
    MAPPING = {'OverteNavigation.hud.goto': 'Go to destination',
        'OverteNavigation.address.field': 'PhoneAddressField', 'OverteNavigation.address.go': 'PhoneAddressGoButton',
        'OverteNavigation.address.cancel': 'PhoneAddressCancelButton', 'OverteTabletOpen': 'tablet.open',
        'OverteTabletClose': 'nav.close', 'OverteNavigation.tablet.home': 'nav.home',
        'OverteNavigation.tablet.places': 'PLACES', 'OverteNavigation.places.back': 'goBack',
        'OverteNavigation.places.forward': 'goForward'}

    def __init__(self, mutation=''):
        super().__init__(mutation)
        self.native_boundary = Boundary(mutation)
        self.profile = {'contractVersion': 1, 'profile': normal_navigation.PROFILE, 'sceneUrl': self.scene}
        self.target = self.native_boundary.target | {'physical': True, 'normalNavigation': self.profile}
        self.sequence_native = 0

    def call(self, method, path, body=None):
        if path.endswith('/elements') and body['value'] in self.MAPPING:
            body = body | {'value': self.MAPPING[body['value']]}
        return super().call(method, path, body)

    def visible(self, name):
        if self.address_open and name in {'nav.close', 'nav.home', 'PLACES', 'goBack', 'goForward'}:
            return False
        return super().visible(name)

    def observed(self):
        value = self.native_boundary.observed()
        value['lastSequence'] = self.sequence_native
        value['tabletShown'] = self.screen is not None
        value['controls'] = []
        for identifier, name in self.MAPPING.items():
            if not self.visible(name):
                continue
            control = 'hud.tablet' if identifier == 'OverteTabletOpen' else (
                'tablet.close' if identifier == 'OverteTabletClose' else identifier.removeprefix('OverteNavigation.'))
            value['controls'].append({'id': control, 'token': str(uuid.uuid5(uuid.NAMESPACE_OID, identifier)),
                'enabled': True, 'focused': name == 'PhoneAddressField' and self.address_open,
                'frame': {'x': 10, 'y': 20, 'width': 120, 'height': 60}})
        return value

    def post(self, request, timeout):
        response = self.native_boundary.post(request, timeout)
        receipt = self.native_boundary.receipt
        if 'observation' in receipt:
            receipt['observation'] = self.observed()
        else:
            native = json.loads(request.data)['input']
            self.sequence_native = native['sequence']
            if native['operation'] == 'replace' and self.mutation != 'text-ignored':
                self.field = native['text']
        return response

    def flow(self):
        native = normal_input.NativeInput(self.native_boundary, 'owned-session', self.target,
            self.native_boundary.process, monotonic=lambda: self.clock, sleep=self.sleep)
        return normal_navigation.IOSNavigation(self.ui, native, self.profile, self.state, self.save)


class IOSNormalNavigation(unittest.TestCase):
    def run_flow(self, boundary):
        with patch.object(normal_input, 'urlopen', boundary.post):
            return boundary.run()

    def test_actual_ios_flow_runs_normal_w3c_inputs_and_independent_navigation_oracle(self):
        boundary = IOSBoundary()
        result = self.run_flow(boundary)
        self.assertEqual(len(result['phases']), 8)
        self.assertTrue(boundary.reports[0]['sequenceCompleted'])
        self.assertFalse(boundary.reports[0]['deviceAcceptance'])
        self.assertNotIn('iosNormalNavigation', boundary.state)
        self.assertFalse(boundary.address_open)
        self.assertIsNone(boundary.screen)
        self.assertEqual(boundary.inputs.count('goBack'), 2)
        self.assertEqual(boundary.inputs.count('goForward'), 2)
        self.assertFalse(any('/execute' in path for _, path, _ in boundary.calls))
        self.assertTrue(any(row.get('iosNormalNavigation', {}).get('context', {}).get('scope')
            == normal_navigation.SCOPE for row in boundary.saved))
        self.assertFalse(any('installedCandidateVerified' in row for row in boundary.saved))

    def test_acknowledged_but_ignored_navigation_or_history_does_not_pass(self):
        for mutation in ('goto-ignored', 'back-ignored', 'forward-ignored'):
            boundary = IOSBoundary(mutation)
            with self.subTest(mutation=mutation), self.assertRaises(AssertionError):
                self.run_flow(boundary)
            self.assertFalse(boundary.reports[0]['sequenceCompleted'])

    def test_foreign_panel_is_neither_taken_over_nor_closed(self):
        for panel in ('address', 'tablet'):
            boundary = IOSBoundary()
            if panel == 'address': boundary.address_open = True
            else: boundary.screen = 'settings'
            with self.subTest(panel=panel), patch.object(normal_input, 'urlopen', boundary.post):
                with self.assertRaisesRegex(NativeUIError, 'pre-existing'):
                    boundary.invoke('places.open', {})
            self.assertEqual(boundary.inputs, [])
            self.assertNotIn('iosNormalNavigation', boundary.state)

    def test_different_native_instance_cannot_adopt_saved_panel_ownership(self):
        boundary = IOSBoundary()
        with patch.object(normal_input, 'urlopen', boundary.post):
            boundary.invoke('places.open', {})
            before = list(boundary.inputs)
            boundary.native_boundary.instance = str(uuid.uuid4())
            with self.assertRaisesRegex(NativeUIError, 'different native UI session'):
                boundary.invoke('places.close', {})
        self.assertEqual(before, boundary.inputs)

    def test_modal_cover_cannot_be_mistaken_for_actual_owned_tablet_closure(self):
        boundary = IOSBoundary()
        with patch.object(normal_input, 'urlopen', boundary.post):
            boundary.flow().open_places()
            boundary.address_open = True  # A separate foreign modal covers the owned tablet.
            before = list(boundary.inputs)
            with self.assertRaisesRegex(NativeUIError, 'covered by another dialog'):
                boundary.flow().open_address()
        self.assertEqual(boundary.inputs, before)
        self.assertTrue(boundary.state['iosNormalNavigation']['tabletOwned'])
        self.assertTrue(boundary.address_open)
        self.assertEqual(boundary.screen, 'places')

    def test_partial_entry_persists_intent_for_idempotent_normal_cleanup(self):
        boundary = IOSBoundary('partial-entry-read-error')
        with patch.object(normal_input, 'urlopen', boundary.post):
            with self.assertRaises(NativeUIError):
                boundary.invoke('places.open', {})
            self.assertTrue(boundary.state['iosNormalNavigation']['addressOwned'])
            boundary.invoke('places.close', {})
            boundary.invoke('places.close', {})
        self.assertNotIn('iosNormalNavigation', boundary.state)
        self.assertFalse(boundary.address_open)

    def test_native_component_profile_remains_explicit_and_has_no_code_binding_claim(self):
        boundary = IOSBoundary()
        self.assertIsNone(normal_navigation.configuration({}))
        self.assertEqual(boundary.profile, normal_navigation.configuration(boundary.target))
        for override in ({'physical': False}, {'nativeUiObservation': {'kind': 'uikit-documents', 'version': True}},
                         {'normalNavigation': boundary.profile | {'installedCandidateVerified': True}}):
            with self.subTest(override=override), self.assertRaises(NativeUIError):
                normal_navigation.configuration(boundary.target | override)


if __name__ == '__main__':
    unittest.main()
